# parallel_search_and_rerank.py
"""
并行检索 + 重排脚本（支持本地与 API 两种 embedding 模式）
- 先在两个 FAISS 索引分别检索 TOPK_PER_INDEX 候选
- 合并候选、去重
- 使用 embedding-based rerank（可选 cross-encoder）
- 最终返回 FINAL_TOPK 条结果

配置：
  USE_API_EMBEDDING = True  # 使用 OpenAI/百炼 兼容 API（text-embedding-v4）
  若为 True，请设置环境变量 DASHSCOPE_API_KEY，并确保 API_BASE_URL 正确
"""
import os
import json
import faiss
import numpy as np
from typing import List, Dict
from tqdm import tqdm
from dotenv import load_dotenv
load_dotenv() 
# ---- 配置 ----
INDEX_A = "vector_store/index_a.bin"
META_A = "vector_store/meta_a.jsonl"
INDEX_B = "vector_store/index_b.bin"
META_B = "vector_store/meta_b.jsonl"

TOPK_PER_INDEX = 20
FINAL_TOPK = 10
# embedding 模型配置
USE_API_EMBEDDING = False  # True 使用远端 API（text-embedding-v4），False 使用本地 sentence-transformers
API_MODEL_NAME = "text-embedding-v4"
API_KEY_ENV_NAME = "DASHSCOPE_API_KEY"
API_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

LOCAL_EMBED_MODEL = "sentence-transformers/all-mpnet-base-v2"
# 分批大小：用于对 candidate_texts 做批量 API 调用
EMBED_BATCH_SIZE = 64
USE_CROSS_ENCODER = False
CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
# ----------------

# 条件导入
if USE_API_EMBEDDING:
    try:
        from openai import OpenAI
    except Exception as e:
        raise RuntimeError("启用 API 模式时请安装 openai（或兼容百炼客户端）：pip install openai") from e

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("未找到 API Key，请在环境变量 DASHSCOPE_API_KEY 设置你的 key")
    API_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    client = OpenAI(api_key=api_key, base_url=API_BASE_URL)
else:
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as e:
        raise RuntimeError("请安装 sentence-transformers: pip install sentence-transformers") from e
    LOCAL_EMBED_MODEL = "sentence-transformers/all-mpnet-base-v2"
    embed_model = SentenceTransformer(LOCAL_EMBED_MODEL)

# 可选 cross-encoder
cross_model = None
if USE_CROSS_ENCODER:
    try:
        from sentence_transformers import CrossEncoder
        cross_model = CrossEncoder(CROSS_ENCODER_MODEL)
    except Exception:
        print("[warning] 无法加载 cross-encoder；将使用 embedding 再打分作为 rerank。")
        USE_CROSS_ENCODER = False

# ---------------- 辅助函数 ----------------
def load_meta(path: str) -> List[Dict]:
    meta = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            meta.append(json.loads(line.strip()))
    return meta

def search_index(index_path: str, q_emb: np.ndarray, topk: int):
    idx = faiss.read_index(index_path)
    D, I = idx.search(q_emb, topk)
    return D[0].tolist(), I[0].tolist(), idx

def api_embed_texts(texts: List[str]) -> np.ndarray:
    """
    使用远端 API 批量生成 embeddings。
    假设 client.embeddings.create 支持 input 为 list。
    返回 shape (len(texts), dim) 的 float32 numpy array（未归一化）。
    """
    all_emb = []
    # 按 EMBED_BATCH_SIZE 分批请求
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start:start+EMBED_BATCH_SIZE]
        try:
            resp = client.embeddings.create(
                model=API_MODEL_NAME,
                input=batch,
                dimensions=1024,
                encoding_format="float"
            )
            # resp.data 对应 batch 中每条输入
            for it in resp.data:
                all_emb.append(it.embedding)
        except Exception as e:
            # 如果批量请求失败，退化为逐条请求（更慢）
            print(f"[api_embed_texts] 批量请求失败: {e}，尝试逐条回退")
            for t in batch:
                try:
                    r = client.embeddings.create(model=API_MODEL_NAME, input=t, dimensions=1024, encoding_format="float")
                    all_emb.append(r.data[0].embedding)
                except Exception as e2:
                    print(f"[api_embed_texts] 单条请求失败: {e2}，插入零向量以占位")
                    all_emb.append([0.0] * 1024)
    arr = np.array(all_emb, dtype=np.float32)
    return arr

def embed_texts(texts: List[str]) -> np.ndarray:
    """
    抽象接口：根据 USE_API_EMBEDDING 返回 embeddings numpy array
    """
    if USE_API_EMBEDDING:
        return api_embed_texts(texts)
    else:
        emb = embed_model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        if emb.dtype != np.float32:
            emb = emb.astype(np.float32)
        return emb

def embed_query_text(query: str) -> np.ndarray:
    if USE_API_EMBEDDING:
        try:
            resp = client.embeddings.create(model=API_MODEL_NAME, input=query, dimensions=1024, encoding_format="float")
            emb = np.array(resp.data[0].embedding, dtype=np.float32).reshape(1, -1)
            return emb
        except Exception as e:
            print(f"[embed_query_text] API 生成 query embedding 失败: {e}")
            # 返回零向量作为退路（之后会被 normalize）
            return np.zeros((1, 1024), dtype=np.float32)
    else:
        emb = embed_model.encode([query], convert_to_numpy=True)
        if emb.dtype != np.float32:
            emb = emb.astype(np.float32)
        return emb

# ----------------- 主流程：并行检索与重排 -----------------
def parallel_search(query: str) -> List[Dict]:
    """
    并行检索两个索引并重排返回 top results。
    返回每个 candidate 的 dict:
      {"source": "A"|"B", "meta": {...}, "orig_score": float, "rerank_score": float}
    """
    # 生成 query embedding（并归一化）
    q_emb = embed_query_text(query)
    faiss.normalize_L2(q_emb)

    # 在两个索引分别搜索
    Da, Ia, _ = search_index(INDEX_A, q_emb, TOPK_PER_INDEX)
    Db, Ib, _ = search_index(INDEX_B, q_emb, TOPK_PER_INDEX)

    metas_a = load_meta(META_A)
    metas_b = load_meta(META_B)

    candidates = []
    for score, idx in zip(Da, Ia):
        if idx < 0:
            continue
        m = metas_a[idx]
        candidates.append({"orig_score": float(score), "meta": m, "source": "A", "id": idx})
    for score, idx in zip(Db, Ib):
        if idx < 0:
            continue
        m = metas_b[idx]
        candidates.append({"orig_score": float(score), "meta": m, "source": "B", "id": idx})

    # 去重（依据 chunk_id 或 source+id）
    seen = set()
    unique_cands = []
    for c in candidates:
        uid = c["meta"].get("chunk_id") or f"{c['source']}_{c['id']}"
        if uid in seen:
            continue
        seen.add(uid)
        unique_cands.append(c)

    if not unique_cands:
        return []

    # 准备 candidate_texts：优先从 meta 中取 'text'、'_text'、'content'、'overview'
    candidate_texts = []
    for c in unique_cands:
        m = c["meta"]
        text = m.get("text") or m.get("_text") or m.get("content") or m.get("overview") or ""
        candidate_texts.append(text)

    # 如果没有可用文本用于重排，直接按 orig_score 返回（降序）
    if not any(candidate_texts):
        unique_cands.sort(key=lambda x: x.get("orig_score", 0), reverse=True)
        return unique_cands[:FINAL_TOPK]

    # 用 embedding（API 或本地）对 candidate_texts 编码并重排
    # 注意：candidate_texts 可能比 emb batch 大，但 embed_texts 支持分批
    cand_embs = embed_texts(candidate_texts)
    # 归一化
    faiss.normalize_L2(cand_embs)

    # 确保 q_emb 是归一化的一维向量
    q_vec = q_emb[0]
    # 计算余弦相似度 scores = cand_embs @ q_vec
    scores = (cand_embs @ q_vec.reshape(-1, 1)).squeeze()
    # 将得分写回并排序
    for i, s in enumerate(scores.tolist()):
        unique_cands[i]["rerank_score"] = float(s)
    unique_cands.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)

    # 最终取 FINAL_TOPK
    return unique_cands[:FINAL_TOPK]


# --------------- 主程序示例 ---------------
if __name__ == "__main__":
    q = "the main content of COMP9814"
    print("查询:", q)
    results = parallel_search(q)
    for i, r in enumerate(results, 1):
        rerank_score = r.get('rerank_score', 0.0)
        orig_score = r.get('orig_score', 0.0)
        meta_preview = {k:v for k,v in r['meta'].items() if k in ('chunk_id','code','title','source_file')}
        print(f"{i}. source={r['source']} rerank_score={rerank_score:.4f} orig_score={orig_score:.4f} meta_preview={meta_preview}")
    print(f"共返回 {len(results)} 条结果。")
# --------------- 主程序示例 ---------------