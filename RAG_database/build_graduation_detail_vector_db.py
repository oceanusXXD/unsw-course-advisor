# build_graduation_detail_vector_db.py
"""
将 ../parsed_graduation_requests_data" 下的 CSV/JSON 文本切分、生成 embeddings，
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
import time
from typing import List, Tuple, Dict, Any
from tqdm import tqdm
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# ========== 配置（按需调整） ==========
DATA_DIR = "../parsed_graduation_requests_data"
VECTOR_STORE_DIR = "./vector_store"
os.makedirs(VECTOR_STORE_DIR, exist_ok=True)

FAISS_INDEX_PATH = os.path.join(VECTOR_STORE_DIR, "index_b.bin")
METADATA_PATH = os.path.join(VECTOR_STORE_DIR, "meta_b.jsonl")

load_dotenv()

# 切换：True 使用 API（百炼/兼容 OpenAI），False 使用本地 sentence-transformers
USE_API_EMBEDDING = True

# API 模型与客户端配置（百炼/兼容 OpenAI）
API_MODEL_NAME = "text-embedding-v3"
API_DIMENSIONS = 1024  # 可选 64/128/256/.../1024/1536/2048（以服务支持为准）
API_BATCH_SIZE = 10    # **关键**：API 每次实际请求的最大条数（不要超过服务限制）
API_MAX_RETRIES = 3    # API 请求失败时重试次数
API_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY_ENV_NAME = "DASHSCOPE_API_KEY"

# 本地模型配置（如果 USE_API_EMBEDDING=False）
LOCAL_MODEL_NAME = "all-mpnet-base-v2"
_MODEL_MAP = {
    "all-mpnet-base-v2": "sentence-transformers/all-mpnet-base-v2",
    "mpnet": "sentence-transformers/all-mpnet-base-v2",
}

# 各种超参数
BATCH_TEXTS = 128      # 外层批次（内存控制），内部 API 会再分成 API_BATCH_SIZE
CHUNK_MAX_CHARS = 512
CHUNK_OVERLAP = 128
TOP_K = 10
# ======================================

# ---- 依赖导入 ----
if USE_API_EMBEDDING:
    try:
        from openai import OpenAI  # 百炼兼容 client
    except Exception:
        raise RuntimeError("请安装 openai: pip install openai")
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


# ----------------- API 封装器 -----------------
class APIEmbeddingModel:
    """
    封装百炼 / OpenAI 兼容 API，使其接口与 SentenceTransformer.encode 兼容：
    encode(texts, convert_to_numpy=True, batch_size=None) -> np.ndarray (n, dim) dtype=float32
    内部会把 texts 分成 self.call_batch 小块（<= API_BATCH_SIZE）提交到 API。
    """
    def __init__(self, client, model_name: str, dimensions: int = API_DIMENSIONS, call_batch: int = API_BATCH_SIZE, max_retries: int = API_MAX_RETRIES):
        self.client = client
        self.model_name = model_name
        self.dim = int(dimensions)
        self.call_batch = max(1, int(call_batch))
        self.max_retries = max(0, int(max_retries))

    def encode(self, texts, convert_to_numpy=True, show_progress_bar=False, batch_size=None):
        # 兼容单字符串和字符串列表
        single = False
        if isinstance(texts, str):
            texts = [texts]
            single = True
        n = len(texts)
        if n == 0:
            if convert_to_numpy:
                return np.zeros((0, self.dim), dtype=np.float32)
            else:
                return []

        # 外部可以传 batch_size（表示外层希望每次 encode 的数量），但我们内部仍然会按 self.call_batch 分割请求
        outer_batch = int(batch_size) if batch_size else n

        embeddings = []
        for i in range(0, n, outer_batch):
            outer_chunk = texts[i:i + outer_batch]
            # 再在 outer_chunk 内按 self.call_batch 请求 API
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
                            # 用零向量占位，保证返回数量不变
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
        # 使用封装器，内部会把每次请求分成 API_BATCH_SIZE 大小
        print(f"使用 API 模型 {API_MODEL_NAME} 生成 embeddings（外层批次 {BATCH_TEXTS}，API 内部批次 {API_BATCH_SIZE}）...")
        api_model = APIEmbeddingModel(client, API_MODEL_NAME, dimensions=API_DIMENSIONS, call_batch=API_BATCH_SIZE, max_retries=API_MAX_RETRIES)
        embeddings_list = []
        dim = None
        for start in tqdm(range(0, n, BATCH_TEXTS), desc="embedding API (outer)"):
            batch = texts[start:start + BATCH_TEXTS]
            # 交给封装器处理（封装器会在内部分小批调用 API）
            emb_batch = api_model.encode(batch, convert_to_numpy=True, batch_size=len(batch))
            if emb_batch is None or emb_batch.shape[0] != len(batch):
                # 不匹配时填零或调整
                print(f"[警告] API 返回 embedding 数量与请求数量不匹配（start={start}），进行对齐处理")
                # 强制成 (len(batch), dim) 结构
                if emb_batch is None:
                    emb_batch = np.zeros((len(batch), API_DIMENSIONS), dtype=np.float32)
                else:
                    # 如果 dim 尚未知，尝试推断
                    if emb_batch.ndim == 1:
                        emb_batch = emb_batch.reshape(1, -1)
                    # 如果长度小于请求数，用零向量补齐
                    if emb_batch.shape[0] < len(batch):
                        d = emb_batch.shape[1]
                        pad = np.zeros((len(batch) - emb_batch.shape[0], d), dtype=np.float32)
                        emb_batch = np.vstack([emb_batch, pad])
            if dim is None:
                dim = emb_batch.shape[1]
            embeddings_list.append(emb_batch)
        # 合并
        embeddings = np.vstack(embeddings_list).astype(np.float32)
    else:
        # 本地模型路径映射并载入
        model_id = get_model_name_map(LOCAL_MODEL_NAME)
        print(f"加载本地嵌入模型：{model_id} ...")
        model = __import__("sentence_transformers", fromlist=["SentenceTransformer"]).SentenceTransformer(model_id)
        # 先推断维度（用少量样本）
        sample = texts[:min(8, n)]
        sample_emb = model.encode(sample, show_progress_bar=False, convert_to_numpy=True)
        dim = sample_emb.shape[1]
        embeddings = np.zeros((n, dim), dtype=np.float32)
        print(f"开始使用本地模型批量生成 embeddings（外层批次 {BATCH_TEXTS}）...")
        for start in tqdm(range(0, n, BATCH_TEXTS), desc="embedding local"):
            end = min(n, start + BATCH_TEXTS)
            batch_emb = model.encode(texts[start:end], show_progress_bar=False, convert_to_numpy=True)
            if batch_emb.dtype != np.float32:
                batch_emb = batch_emb.astype(np.float32)
            embeddings[start:end] = batch_emb

    # 检查 embeddings 形状
    if embeddings is None or embeddings.shape[0] != n:
        raise RuntimeError("生成的 embeddings 数量与文本数量不一致，请检查 API 调用或模型。")
    dim = embeddings.shape[1]
    print(f"生成 embeddings 完成，向量维度 = {dim}，向量数量 = {embeddings.shape[0]}")

    # 归一化（L2）以使用内积实现 cosine 相似度
    faiss.normalize_L2(embeddings)

    # ---- 保存 metadata.jsonl（与向量顺序一一对应） ----
    print(f"写入元数据到 {METADATA_PATH} ...")
    with open(METADATA_PATH, "w", encoding="utf-8") as mf:
        for d in docs:
            mf.write(json.dumps(d["meta"], ensure_ascii=False) + "\n")

    # ---- 构建 FAISS 索引（IndexFlatIP for cosine） ----
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
        model = __import__("sentence_transformers", fromlist=["SentenceTransformer"]).SentenceTransformer(get_model_name_map(LOCAL_MODEL_NAME))
    else:
        # 如果 API 模式，使用同样的封装器来生成 query embedding
        model = APIEmbeddingModel(client, API_MODEL_NAME, dimensions=API_DIMENSIONS, call_batch=API_BATCH_SIZE, max_retries=API_MAX_RETRIES)
    return index, metas, model


def query_vector_store(query: str, top_k: int = TOP_K) -> List[Dict]:
    index, metas, model = load_index_and_meta()
    # 生成 query embedding（API 或 本地） - 统一使用 model.encode
    if model is None:
        raise RuntimeError("查询时未能加载 embedding model")
    try:
        q_emb = model.encode([query], convert_to_numpy=True, show_progress_bar=False)
        if q_emb.dtype != np.float32:
            q_emb = q_emb.astype(np.float32)
        if q_emb.ndim == 1:
            q_emb = q_emb.reshape(1, -1)
    except Exception as e:
        print(f"[query embedding 生成失败] {e}，使用零向量替代")
        q_emb = np.zeros((1, API_DIMENSIONS if USE_API_EMBEDDING else 768), dtype=np.float32)

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
