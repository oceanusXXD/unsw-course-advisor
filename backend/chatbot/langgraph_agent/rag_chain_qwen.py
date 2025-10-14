# backend/chatbot/rag_chain_qwen.py
# coding: utf-8
"""
检索模块（支持本地 / API 两种 embedding 模式）
- retrieve(query, top_k) 仅执行 embedding -> FAISS 检索并返回 JSON-可序列化的 docs 列表
- list_all_course_codes() 返回索引中所有 course_code（便于调试）
- extract_course_code_from_query / get_doc_by_course_code 辅助函数

新增：通过 USE_API_EMBEDDING 切换是否使用 OpenAI 兼容（百炼）API 生成 embedding。
默认 embedding API 使用 text-embedding-v3（可改为 v4，如需）。
注意：API 模式需要在环境变量中设置 DASHSCOPE_API_KEY。
"""

from typing import List, Dict, Any, Optional, Tuple
import os
import json
import faiss
import numpy as np
import re
from dotenv import load_dotenv

# ---------- 配置（按需修改） ----------
BASE_DIR = os.path.dirname(__file__)
FAISS_INDEX_PATH = os.path.join(BASE_DIR, "..", "..", "RAG_database", "vector_store", "faiss_index.bin")
METADATA_PATH = os.path.join(BASE_DIR, "..", "..", "RAG_database", "vector_store", "metadata.jsonl")

# 是否使用 API（True 使用 百炼/OpenAI 兼容 API；False 使用本地 SentenceTransformer）
USE_API_EMBEDDING = True

# API 相关配置（百炼 / OpenAI 兼容）
API_MODEL_NAME = "text-embedding-v3"   # 你要求使用 v3
API_DIMENSIONS = 1024                  # 与模型对应的维度（text-embedding-v3 常用 1024）
API_BATCH_SIZE = 10                    # API 单次请求最大条数（API 限制）
API_MAX_RETRIES = 3
API_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY_ENV_NAME = "DASHSCOPE_API_KEY"

# 本地模型（fallback）
EMBEDDING_MODEL_NAME_LOCAL = "all-MiniLM-L6-v2"
DEFAULT_TOP_K = 8
# -------------------------------------------------

# 内部缓存
_emb_model = None
_faiss_index = None
_metadata = None

# 仅在需要时导入 heavy deps
if not USE_API_EMBEDDING:
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as e:
        raise RuntimeError("请先安装 sentence-transformers: pip install sentence-transformers") from e
else:
    # 初始化 API client
    try:
        from openai import OpenAI
    except Exception:
        raise RuntimeError("请安装 openai SDK: pip install openai （或使用内部兼容库）")

load_dotenv()


# ----------------- API 封装器（与 SentenceTransformer.encode 接口兼容） -----------------
import time

class APIEmbeddingModel:
    """
    将 OpenAI 兼容 API 封装为 encode(texts, convert_to_numpy=True, batch_size=None) -> np.ndarray
    - client: OpenAI(...) 实例
    - model_name: API 上的模型名（如 text-embedding-v3/v4）
    - dim: 输出向量维度
    - call_batch: API 每次实际请求的最大条数（不要超过服务限制）
    - max_retries: 失败时重试次数
    """
    def __init__(self, client, model_name: str, dim: int = API_DIMENSIONS, call_batch: int = API_BATCH_SIZE, max_retries: int = API_MAX_RETRIES):
        self.client = client
        self.model_name = model_name
        self.dim = int(dim)
        self.call_batch = max(1, int(call_batch))
        self.max_retries = max(0, int(max_retries))

    def encode(self, texts, convert_to_numpy=True, show_progress_bar=False, batch_size=None):
        # 支持单字符串或字符串列表
        single = False
        if isinstance(texts, str):
            texts = [texts]
            single = True
        n = len(texts)
        if n == 0:
            return np.zeros((0, self.dim), dtype=np.float32) if convert_to_numpy else []

        # outer batch 尺寸由外部决定（用于控制内存），但我们会在内部把 outer_chunk 拆成 self.call_batch 大小向 API 请求
        outer_batch = int(batch_size) if batch_size else n

        embeddings = []
        for i in range(0, n, outer_batch):
            outer_chunk = texts[i:i + outer_batch]
            for j in range(0, len(outer_chunk), self.call_batch):
                sub = outer_chunk[j:j + self.call_batch]
                attempts = 0
                while True:
                    try:
                        resp = self.client.embeddings.create(
                            model=self.model_name,
                            input=sub,
                            dimensions=self.dim,
                            encoding_format="float"
                        )
                        # resp.data 对应 sub 中每一项
                        for item in resp.data:
                            embeddings.append(item.embedding)
                        break
                    except Exception as e:
                        attempts += 1
                        if attempts > self.max_retries:
                            print(f"[APIEmbeddingModel] 批量 embedding 调用失败（全局索引 {i + j}），重试 {attempts - 1} 次后放弃：{e}")
                            # 补零向量以保持长度一致
                            for _ in sub:
                                embeddings.append([0.0] * self.dim)
                            break
                        else:
                            backoff = 2 ** attempts
                            print(f"[APIEmbeddingModel] 调用失败（全局索引 {i + j}），第 {attempts} 次重试，backoff={backoff}s：{e}")
                            time.sleep(backoff)

        arr = np.array(embeddings, dtype=np.float32)
        if convert_to_numpy:
            return arr
        else:
            return arr.tolist()


# ---------------- Embedding 模型加载 ----------------
def _load_embedding_model():
    """
    返回一个具有 .encode(texts, convert_to_numpy=True, batch_size=...) 方法的对象。
    在 API 模式下返回 APIEmbeddingModel；在本地模式下返回 SentenceTransformer 实例。
    """
    global _emb_model
    if _emb_model is not None:
        return _emb_model

    if USE_API_EMBEDDING:
        api_key = os.getenv(API_KEY_ENV_NAME) or ""
        if not api_key:
            raise RuntimeError(f"USE_API_EMBEDDING=True，但环境变量 {API_KEY_ENV_NAME} 未设置。")
        client = OpenAI(api_key=api_key, base_url=API_BASE_URL)
        _emb_model = APIEmbeddingModel(client, model_name=API_MODEL_NAME, dim=API_DIMENSIONS, call_batch=API_BATCH_SIZE, max_retries=API_MAX_RETRIES)
    else:
        # 本地模型懒加载
        from sentence_transformers import SentenceTransformer
        _emb_model = SentenceTransformer(EMBEDDING_MODEL_NAME_LOCAL)
    return _emb_model


# ---------------- FAISS 与 metadata 加载 ----------------
def load_faiss_and_metadata(index_path: str = FAISS_INDEX_PATH, meta_path: str = METADATA_PATH):
    """
    加载并缓存 FAISS 索引与 metadata jsonl（metadata 是 list of dict）
    """
    global _faiss_index, _metadata
    if _faiss_index is None:
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"FAISS 索引未找到: {index_path}")
        _faiss_index = faiss.read_index(index_path)
    if _metadata is None:
        if not os.path.exists(meta_path):
            raise FileNotFoundError(f"Metadata 文件未找到: {meta_path}")
        _metadata = []
        with open(meta_path, "r", encoding="utf-8") as fr:
            for line in fr:
                try:
                    _metadata.append(json.loads(line))
                except Exception:
                    # 忽略损坏行
                    continue
    return _faiss_index, _metadata


# ---------------- Query embedding 生成 ----------------
def embed_query(query: str) -> np.ndarray:
    """
    生成并归一化 embedding （返回 numpy array shape (1, dim) dtype float32）
    - 在 API 模式下使用 APIEmbeddingModel.encode
    - 在本地模式下使用 SentenceTransformer.encode
    """
    if not query:
        # 返回合适形状的零向量（尽量与索引维度匹配）
        index, _ = load_faiss_and_metadata()
        dim = index.d if index is not None else API_DIMENSIONS
        return np.zeros((1, dim), dtype=np.float32)

    model = _load_embedding_model()
    # 调用 encode（统一以列表输入）
    emb = model.encode([query], convert_to_numpy=True, batch_size=1)
    if not isinstance(emb, np.ndarray):
        emb = np.array(emb, dtype=np.float32)
    if emb.dtype != np.float32:
        emb = emb.astype(np.float32)

    # 如果返回 shape 为 (dim,) -> reshape
    if emb.ndim == 1:
        emb = emb.reshape(1, -1)
    # 如果返回多行，取第一行（因为我们只传入了一条）
    if emb.shape[0] >= 1:
        q_emb = emb[0:1]
    else:
        # 兜底
        index, _ = load_faiss_and_metadata()
        dim = index.d if index is not None else API_DIMENSIONS
        q_emb = np.zeros((1, dim), dtype=np.float32)

    # 归一化
    # 若索引维度与 q_emb 不匹配，尝试截断或填充零（防止 crash）
    index, _ = load_faiss_and_metadata()
    target_dim = index.d if index is not None else q_emb.shape[1]
    if q_emb.shape[1] != target_dim:
        if q_emb.shape[1] > target_dim:
            # 截断
            q_emb = q_emb[:, :target_dim]
        else:
            # 填充
            pad = np.zeros((q_emb.shape[0], target_dim - q_emb.shape[1]), dtype=np.float32)
            q_emb = np.hstack([q_emb, pad])

    faiss.normalize_L2(q_emb)
    return q_emb


# --- 课程代码提取辅助 ---
_course_code_re = re.compile(r'\b([A-Za-z]{2,5})\s*[-]?\s*(\d{3,4})\b')

def extract_course_code_from_query(query: str) -> Optional[str]:
    if not query:
        return None
    m = _course_code_re.search(query)
    if not m:
        return None
    code = (m.group(1) + m.group(2)).upper().replace(" ", "")
    return code

def get_doc_by_course_code(code: str, metadata: List[Dict[str,Any]]) -> Optional[Tuple[Dict[str,Any], int]]:
    if not code:
        return None
    norm = code.replace(" ", "").upper()
    for idx, d in enumerate(metadata):
        c = (d.get("course_code") or "").replace(" ", "").upper()
        if c == norm:
            return d, idx
    return None


# ---------- 纯检索函数（返回 JSON-序列化友好的 dict） ----------
def retrieve(query: str, top_k: int = DEFAULT_TOP_K) -> List[Dict[str, Any]]:
    """
    纯检索（本地/API 皆可）：
    - 使用 embed_query -> faiss.search 得到 top_k 索引
    - 如果 query 包含课程 code 且该 code 在 metadata 中但未命中 top_k，
      尝试 reconstruct 向量计算相似度并插入（回退为置顶）
    返回列表：每项为 dict，包含至少字段：
      {
        "course_code": str,
        "source_file": str,
        "_score": float,
        "_text": str,
        "_meta_index": int,
        ... 其他原始 metadata 字段
      }
    """
    index, metadata = load_faiss_and_metadata()
    q_emb = embed_query(query)

    try:
        D, I = index.search(q_emb, top_k)
    except Exception as e:
        print(f"[retrieve] FAISS search error: {e}")
        return []

    results = []
    seen_idx = set()
    for score, idx in zip(D[0], I[0]):
        if idx < 0 or idx >= len(metadata):
            continue
        m = metadata[idx].copy()
        try:
            score_f = float(score)
        except Exception:
            score_f = float(np.array(score).item()) if hasattr(score, 'item') else 0.0
        m["_score"] = score_f
        m["_text"] = m.get("_content") or m.get("content") or m.get("overview") or ""
        m["_meta_index"] = int(idx)
        for k, v in list(m.items()):
            if isinstance(v, (np.integer, np.floating)):
                m[k] = v.item()
        results.append(m)
        seen_idx.add(idx)

    # code 优先插入逻辑（与原版一致）
    code = extract_course_code_from_query(query)
    if code:
        found = get_doc_by_course_code(code, metadata)
        if found:
            doc, doc_idx = found
            if doc_idx in seen_idx:
                for i, r in enumerate(results):
                    rc = (r.get("course_code") or "").replace(" ", "").upper()
                    if rc == code:
                        results.insert(0, results.pop(i))
                        break
            else:
                try:
                    vec = index.reconstruct(doc_idx).astype(np.float32)
                    vec_norm = vec / (np.linalg.norm(vec) + 1e-12)
                    score_val = float(np.dot(q_emb[0], vec_norm))
                    doc_copy = metadata[doc_idx].copy()
                    doc_copy["_score"] = float(score_val)
                    doc_copy["_text"] = doc_copy.get("_content") or doc_copy.get("content") or doc_copy.get("overview") or ""
                    doc_copy["_meta_index"] = int(doc_idx)
                    pos = 0
                    while pos < len(results) and results[pos].get("_score", 0) >= score_val:
                        pos += 1
                    results.insert(pos, doc_copy)
                except Exception:
                    doc_copy = metadata[doc_idx].copy()
                    doc_copy["_score"] = (results[0].get("_score", 0) + 0.01) if results else 1.0
                    doc_copy["_text"] = doc_copy.get("_content") or doc_copy.get("overview") or ""
                    doc_copy["_meta_index"] = int(doc_idx)
                    results.insert(0, doc_copy)

    # 去重并返回
    seen = set()
    final = []
    for r in results:
        key = ((r.get("course_code") or "").upper()) or (r.get("_text") or "")[:120]
        if key in seen:
            continue
        seen.add(key)
        for k, v in list(r.items()):
            if isinstance(v, (np.integer, np.floating)):
                r[k] = v.item()
        final.append(r)

    return final[: max(top_k, len(final))]


# ---------- 工具：列出索引内所有 course_code（调试用） ----------
def list_all_course_codes() -> List[str]:
    _, metadata = load_faiss_and_metadata()
    codes = []
    for d in metadata:
        c = d.get("course_code") or ""
        if c:
            codes.append(c)
    return codes
