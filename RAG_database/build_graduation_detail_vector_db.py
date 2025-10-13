# build_graduation_detail_vector_db.py
"""
将 ../graduation_requests_data 下的 CSV/JSON 文本切分、生成 embeddings，
并保存到本地 FAISS 索引与 metadata.jsonl。

支持两种 embedding 模式（由 USE_API_EMBEDDING 控制）：
- 本地：sentence-transformers/all-mpnet-base-v2
- API：OpenAI 兼容百炼 API (text-embedding-v4)

使用前请安装：
pip install sentence-transformers faiss-cpu pandas tqdm numpy python-dotenv openai

并在环境变量中设置 DASHSCOPE_API_KEY（若使用 API 模式）。
"""
import os
import glob
import json
from typing import List, Tuple, Dict, Any
from tqdm import tqdm
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# ========== 配置（按需调整） ==========
DATA_DIR = "../graduation_requests_data"
VECTOR_STORE_DIR = "./vector_store"
os.makedirs(VECTOR_STORE_DIR, exist_ok=True)

FAISS_INDEX_PATH = os.path.join(VECTOR_STORE_DIR, "index_b.bin")
METADATA_PATH = os.path.join(VECTOR_STORE_DIR, "meta_b.jsonl")

load_dotenv()

# 切换：True 使用 API（百炼/兼容 OpenAI），False 使用本地 sentence-transformers
USE_API_EMBEDDING = True

# API 模型与客户端配置（百炼/兼容 OpenAI）
API_MODEL_NAME = "text-embedding-v4"
# 请确保环境变量中有 DASHSCOPE_API_KEY（或在下面直接填写，但不推荐明文写 key）
API_KEY_ENV_NAME = "DASHSCOPE_API_KEY"
API_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 本地模型配置（如果 USE_API_EMBEDDING=False）
LOCAL_MODEL_NAME = "all-mpnet-base-v2"
# 简写映射为 sentence-transformers 全名
_MODEL_MAP = {
    "all-mpnet-base-v2": "sentence-transformers/all-mpnet-base-v2",
    "mpnet": "sentence-transformers/all-mpnet-base-v2",
}

# 各种超参数
BATCH_TEXTS = 128
CHUNK_MAX_CHARS = 512
CHUNK_OVERLAP = 128
TOP_K = 10
# ======================================

# ---- 可选依赖导入 ----
if USE_API_EMBEDDING:
    try:
        from openai import OpenAI  # 百炼兼容 client
    except Exception:
        raise RuntimeError("请安装 openai: pip install openai （或使用你们提供的兼容库）")
else:
    try:
        from sentence_transformers import SentenceTransformer
    except Exception:
        raise RuntimeError("请先安装 sentence-transformers: pip install sentence-transformers")

try:
    import faiss
except Exception:
    raise RuntimeError("请先安装 faiss-cpu: pip install faiss-cpu")

# ---- 初始化 API client（若启用 API） ----
client = None
if USE_API_EMBEDDING:
    api_key = os.getenv(API_KEY_ENV_NAME) or ""
    if not api_key:
        raise RuntimeError(f"USE_API_EMBEDDING=True 时请在环境变量 {API_KEY_ENV_NAME} 中设置 API Key")
    client = OpenAI(api_key=api_key, base_url=API_BASE_URL)


# ---------------- 工具函数 ----------------
def get_model_name_map(name: str) -> str:
    return _MODEL_MAP.get(name, name)


def collect_files(data_dir: str) -> List[str]:
    """收集 csv / json 文件"""
    files = []
    for ext in ("*.json", "*.csv"):
        files.extend(glob.glob(os.path.join(data_dir, ext)))
    return sorted(files)


def extract_texts_from_json_obj(obj: Any) -> str:
    """递归提取 JSON 对象中的文本字段，合成单一长文本"""
    texts = []
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj.strip()
    if isinstance(obj, (int, float)):
        return str(obj)
    if isinstance(obj, dict):
        for k, v in obj.items():
            part = extract_texts_from_json_obj(v)
            if part:
                texts.append(part)
    elif isinstance(obj, list):
        for it in obj:
            part = extract_texts_from_json_obj(it)
            if part:
                texts.append(part)
    return "\n".join(texts)


def chunk_text(text: str, max_chars: int, overlap: int) -> List[Tuple[str, int, int]]:
    """把一段文本用滑动窗口切成多个 chunk，返回 (chunk, start, end) 列表"""
    if not text:
        return []
    text = text.strip()
    n = len(text)
    if n <= max_chars:
        return [(text, 0, n)]
    chunks = []
    start = 0
    step = max_chars - overlap
    while start < n:
        end = start + max_chars
        if end >= n:
            end = n
        chunk = text[start:end]
        chunks.append((chunk, start, end))
        if end == n:
            break
        start += step
    return chunks


def csv_row_to_text_meta(row: pd.Series, source_file: str, row_index: int) -> Tuple[str, Dict]:
    """把 CSV 行转换为文本与元数据：长列拼接为描述，短列作为 meta"""
    text_parts = []
    meta = {"source_file": source_file, "row_index": row_index}
    for col, val in row.items():
        if pd.isna(val) or str(val).strip() == "":
            continue
        s = str(val).strip()
        if len(s) >= 40:
            text_parts.append(s)
        else:
            if col in meta:
                meta[col + "_extra"] = meta.get(col + "_extra", "") + " | " + s
            else:
                meta[col] = s
    text = "\n".join(text_parts).strip()
    if not text:
        text = " ".join([str(x).strip() for x in row.values if str(x).strip()])
    return text, meta


# ---------------- 主流程：构建向量库 ----------------
def build_vector_store():
    files = collect_files(DATA_DIR)
    if not files:
        raise RuntimeError(f"在 {DATA_DIR} 下未找到 json/csv 文件，请确认路径。")
    print(f"发现 {len(files)} 个文件，开始读取并切分文本（chunking）...")

    docs = []  # 每个项: {"text":..., "meta":{...}}
    for fp in files:
        name = os.path.basename(fp)
        if fp.lower().endswith(".csv"):
            df = pd.read_csv(fp, dtype=str, keep_default_na=False, na_values=[""])
            for i, row in df.iterrows():
                text, meta = csv_row_to_text_meta(row, name, int(i))
                if not text or text.strip() == "":
                    continue
                chunks = chunk_text(text, CHUNK_MAX_CHARS, CHUNK_OVERLAP)
                for idx, (chunk, s, e) in enumerate(chunks):
                    item_meta = dict(meta)
                    item_meta.update({
                        "chunk_id": f"{name}::row{i}::chunk{idx}",
                        "chunk_char_start": int(s),
                        "chunk_char_end": int(e),
                        "origin_type": "csv",
                        "origin_file": name
                    })
                    docs.append({"text": chunk, "meta": item_meta})
        elif fp.lower().endswith(".json"):
            with open(fp, "r", encoding="utf-8") as fr:
                try:
                    obj = json.load(fr)
                except Exception as e:
                    print(f"[警告] JSON 解析失败 {name}: {e}，跳过")
                    continue
            items = []
            if isinstance(obj, list):
                items = obj
            elif isinstance(obj, dict) and "pageContent" in obj:
                pc = obj["pageContent"]
                items = pc if isinstance(pc, list) else [pc]
            elif isinstance(obj, dict):
                items = [obj]
            else:
                continue

            for i, it in enumerate(items):
                text = extract_texts_from_json_obj(it)
                if not text or text.strip() == "":
                    continue
                chunks = chunk_text(text, CHUNK_MAX_CHARS, CHUNK_OVERLAP)
                base_meta = {"source_file": name, "item_index": i}
                if isinstance(it, dict):
                    if it.get("code"):
                        base_meta["code"] = it.get("code")
                    if it.get("title"):
                        base_meta["title"] = it.get("title")
                for idx, (chunk, s, e) in enumerate(chunks):
                    item_meta = dict(base_meta)
                    item_meta.update({
                        "chunk_id": f"{name}::item{i}::chunk{idx}",
                        "chunk_char_start": int(s),
                        "chunk_char_end": int(e),
                        "origin_type": "json",
                        "origin_file": name
                    })
                    docs.append({"text": chunk, "meta": item_meta})
        else:
            continue

    print(f"切分完成，总 chunk 数: {len(docs)}")
    if len(docs) == 0:
        raise RuntimeError("没有可用的文本 chunk。")

    texts = [d["text"] for d in docs]
    n = len(texts)

    # ---- 生成 embeddings（API 或 本地） ----
    embeddings = None
    if USE_API_EMBEDDING:
        # 使用批量 API（每次提交 BATCH_TEXTS 条文本）
        print(f"使用 API 模型 {API_MODEL_NAME} 生成 embeddings（批次大小 {BATCH_TEXTS}）...")
        embeddings_list = []
        for start in tqdm(range(0, n, BATCH_TEXTS), desc="embedding API"):
            batch = texts[start:start + BATCH_TEXTS]
            try:
                # 兼容性假设：client.embeddings.create 支持 input 为 list
                resp = client.embeddings.create(
                    model=API_MODEL_NAME,
                    input=batch,
                    dimensions=1024,
                    encoding_format="float"
                )
                # resp.data 对应每个输入
                for item in resp.data:
                    embeddings_list.append(item.embedding)
            except Exception as e:
                print(f"[embedding API 失败] {e} -- 为该批次逐条回退调用或填 0 向量")
                # 回退：逐条请求（更慢）或填 0 向量
                for text in batch:
                    try:
                        r2 = client.embeddings.create(model=API_MODEL_NAME, input=text, dimensions=1024, encoding_format="float")
                        embeddings_list.append(r2.data[0].embedding)
                    except Exception as e2:
                        print(f"[单条回退失败] {e2}，插入零向量")
                        embeddings_list.append([0.0] * 1024)
        embeddings = np.array(embeddings_list, dtype=np.float32)
    else:
        # 本地模型路径映射并载入
        model_id = get_model_name_map(LOCAL_MODEL_NAME)
        print(f"加载本地嵌入模型：{model_id} ...")
        model = SentenceTransformer(model_id)
        # 先推断维度
        sample = texts[:min(8, n)]
        sample_emb = model.encode(sample, show_progress_bar=False, convert_to_numpy=True)
        dim = sample_emb.shape[1]
        embeddings = np.zeros((n, dim), dtype=np.float32)
        print(f"开始使用本地模型批量生成 embeddings（批次大小 {BATCH_TEXTS}）...")
        for start in tqdm(range(0, n, BATCH_TEXTS), desc="embedding local"):
            end = min(n, start + BATCH_TEXTS)
            batch_emb = model.encode(texts[start:end], show_progress_bar=False, convert_to_numpy=True)
            if batch_emb.dtype != np.float32:
                batch_emb = batch_emb.astype(np.float32)
            embeddings[start:end] = batch_emb

    # 归一化（L2）以使用内积实现 cosine 相似度
    faiss.normalize_L2(embeddings)

    # ---- 保存 metadata.jsonl（与向量顺序一一对应） ----
    print(f"写入元数据到 {METADATA_PATH} ...")
    with open(METADATA_PATH, "w", encoding="utf-8") as mf:
        for d in docs:
            mf.write(json.dumps(d["meta"], ensure_ascii=False) + "\n")

    # ---- 构建 FAISS 索引（IndexFlatIP for cosine） ----
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # 使用内积（已归一化即为 cosine）
    index.add(embeddings)
    faiss.write_index(index, FAISS_INDEX_PATH)
    print(f"FAISS 索引已保存到 {FAISS_INDEX_PATH}")

    # ---- 保存 model info ----
    with open(os.path.join(VECTOR_STORE_DIR, "model_info.json"), "w", encoding="utf-8") as mf:
        mf.write(json.dumps({
            "embedding_model": API_MODEL_NAME if USE_API_EMBEDDING else get_model_name_map(LOCAL_MODEL_NAME),
            "dim": dim,
            "n_vectors": n
        }, ensure_ascii=False, indent=2))

    print("构建完成。可以使用 query_vector_store(query_text, top_k) 来检索。")


# ---------------- 查询函数 ----------------
def load_index_and_meta():
    if not os.path.exists(FAISS_INDEX_PATH) or not os.path.exists(METADATA_PATH):
        raise RuntimeError("索引或元数据不存在，请先运行 build_vector_store()")
    index = faiss.read_index(FAISS_INDEX_PATH)
    metas = []
    with open(METADATA_PATH, "r", encoding="utf-8") as mf:
        for line in mf:
            metas.append(json.loads(line.strip()))
    # 如果使用本地模式，加载本地模型（供 query 时使用）
    model = None
    if not USE_API_EMBEDDING:
        model = SentenceTransformer(get_model_name_map(LOCAL_MODEL_NAME))
    return index, metas, model


def query_vector_store(query: str, top_k: int = TOP_K) -> List[Dict]:
    index, metas, model = load_index_and_meta()
    # 生成 query embedding（API 或 本地）
    if USE_API_EMBEDDING:
        try:
            resp = client.embeddings.create(
                model=API_MODEL_NAME,
                input=query,
                dimensions=1024,
                encoding_format="float"
            )
            q_emb = np.array(resp.data[0].embedding, dtype=np.float32).reshape(1, -1)
        except Exception as e:
            print(f"[query embedding API 失败] {e}")
            q_emb = np.zeros((1, 1024), dtype=np.float32)
    else:
        q_emb = model.encode([query], convert_to_numpy=True, show_progress_bar=False)
        if q_emb.dtype != np.float32:
            q_emb = q_emb.astype(np.float32)

    faiss.normalize_L2(q_emb)
    D, I = index.search(q_emb, top_k)
    D = D[0].tolist()
    I = I[0].tolist()
    results = []
    for score, idx in zip(D, I):
        if idx < 0 or idx >= len(metas):
            continue
        meta = metas[idx]
        results.append({"score_cosine": float(score), "meta": meta})
    return results


# -------------- main --------------
if __name__ == "__main__":
    build_vector_store()

    # 简单演示查询（运行脚本后可注释掉）
    q = "核心课程与论文要求"
    print("查询示例：", q)
    res = query_vector_store(q, top_k=TOP_K)
    for i, r in enumerate(res):
        print(f"{i+1}. score={r['score_cosine']:.4f} meta={r['meta']}")
