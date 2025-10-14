# build_course_datail_vector_db.py
"""
用途：
- 从 ./crawler/subject.txt 读取 subject 列表
- 在 ./data 下查找以 subject 为前缀/包含 subject 的 *_course_detail.json 文件（更宽松匹配）
- 解析并提取指定字段，清洗 HTML
- 对长文本做切分（chunking）
- 用 sentence-transformers 或 百炼 API 生成 embedding（分批）
- 用 FAISS 增量建立向量索引，并保存索引 + metadata.jsonl
- 提供查询示例

输出：./vector_store/faiss_index.bin 和 ./vector_store/metadata.jsonl
"""

import os
import json
import glob
import re
from typing import List, Dict, Any, Tuple
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
from tqdm import tqdm
from openai import OpenAI
from dotenv import load_dotenv
import time
# ------------ 配置 ------------
SUBJECT_FILE = "../crawler/subject.txt"
DATA_DIR = "../course_detail_data"
VECTOR_STORE_DIR = "./vector_store"
FAISS_INDEX_PATH = os.path.join(VECTOR_STORE_DIR, "faiss_index.bin")
METADATA_PATH = os.path.join(VECTOR_STORE_DIR, "metadata.jsonl")
LOCAL_MODEL_NAME = "all-mpnet-base-v2"  # 本地模型名（如果使用本地）
BATCH_TEXTS = 128   # embedding 批次大小（入库批次）
CHUNK_MAX_CHARS = 512
CHUNK_OVERLAP = 128
TOP_K = 10
USE_API_EMBEDDING = True  # True 使用百炼兼容 API，False 使用本地 SentenceTransformer
API_MODEL_NAME = "text-embedding-v3"
API_DIMENSIONS = 1024  # 使用 text-embedding-v3 时常用维度
API_BATCH_SIZE = 10    # 对 API 的内部小批量（根据服务限制、建议10以内）
load_dotenv()

client = None
if USE_API_EMBEDDING:
    client = OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
# -----------------------------

os.makedirs(VECTOR_STORE_DIR, exist_ok=True)


def load_subjects(subject_file: str) -> List[str]:
    subjects = []
    with open(subject_file, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                subjects.append(s)
    return subjects


def find_files_for_subject(subject: str, data_dir: str) -> List[str]:
    """
    更稳健的查找：列出 data_dir 内所有文件，按文件名小写匹配 subject 小写并包含 'course_detail.json'
    """
    subject_low = subject.lower()
    matches = []
    for root, _, files in os.walk(data_dir):
        for fn in files:
            fn_low = fn.lower()
            if subject_low in fn_low and "course_detail.json" in fn_low:
                matches.append(os.path.join(root, fn))
    # fallback: 简单 glob
    if not matches:
        pattern = os.path.join(data_dir, f"{subject}*course_detail.json")
        matches = glob.glob(pattern)
    return sorted(matches)


def strip_html(html_text: Any) -> str:
    if html_text is None:
        return ""
    if not isinstance(html_text, str):
        try:
            html_text = str(html_text)
        except Exception:
            return ""
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    return " ".join(text.split())


def delivery_to_text(delivery_list: Any) -> str:
    if not delivery_list:
        return ""
    if isinstance(delivery_list, str):
        return delivery_list
    parts = []
    for d in delivery_list:
        if isinstance(d, dict):
            disp = d.get("display") or d.get("delivery_mode") or d.get("mode") or json.dumps(d, ensure_ascii=False)
            ch = f"{disp}"
            if d.get("contact_hours"):
                ch += f" (contact_hours: {d.get('contact_hours')})"
            parts.append(ch)
        else:
            parts.append(str(d))
    return " | ".join(parts)


def normalize_equivalent(equiv: Any) -> str:
    if not equiv:
        return ""
    if isinstance(equiv, list):
        return ", ".join([str(x) for x in equiv])
    return str(equiv)


def record_to_content_and_meta(record: Dict[str, Any], source_file: str, subject: str) -> Tuple[str, Dict[str, Any]]:
    course_code = record.get("course_code") or record.get("CourseCode") or record.get("code") or ""
    title = strip_html(record.get("title") or record.get("name") or "")

    overview = strip_html(record.get("overview") or record.get("Overview") or record.get("description") or "")
    learning_outcomes = strip_html(record.get("learning_outcomes") or record.get("learningOutcomes") or "")
    assessment = strip_html(record.get("assessment") or record.get("assessmentMethods") or "")
    prerequisites = strip_html(record.get("prerequisites") or record.get("pre-requisites") or "")
    add_enrol = strip_html(record.get("additional_enrolment_constraints") or record.get("additionalEnrolmentConstraints") or "")
    equiv = normalize_equivalent(record.get("equivalent_courses") or record.get("equivalentCourses") or record.get("equivalents") or "")
    offering_terms = strip_html(record.get("offering_terms") or record.get("offeringTerms") or record.get("terms") or "")
    delivery = delivery_to_text(record.get("delivery") or record.get("delivery_modes") or record.get("deliveryMode"))

    content_parts = [
        f"# COURSE TITLE: {title}" if title else "",
        f"## COURSE CODE: {course_code}" if course_code else "",
        f"### SUBJECT: {subject}",
        f"#### OVERVIEW:\n{overview}" if overview else "",
        f"#### LEARNING OUTCOMES:\n{learning_outcomes}" if learning_outcomes else "",
        f"#### ASSESSMENT METHODS:\n{assessment}" if assessment else "",
        f"#### PREREQUISITES:\n{prerequisites}" if prerequisites else "",
        f"#### ADDITIONAL ENROLMENT CONSTRAINTS:\n{add_enrol}" if add_enrol else "",
        f"#### EQUIVALENT COURSES: {equiv}" if equiv else "",
        f"#### OFFERING TERMS: {offering_terms}" if offering_terms else "",
        f"#### DELIVERY MODES: {delivery}" if delivery else ""
    ]

    content = "\n\n".join([p for p in content_parts if p.strip() != ""])

    metadata = {
        "course_code": course_code,
        "title": title,
        "subject": subject,
        "source_file": os.path.basename(source_file),
        "offering_terms": offering_terms,
        "delivery": delivery,
        "equivalent_courses": equiv,
        "additional_enrolment_constraints": add_enrol,
        "learning_outcomes": learning_outcomes[:200] + "..." if learning_outcomes else "",
        "assessment": assessment[:200] + "..." if assessment else "",
        "prerequisites": prerequisites[:200] + "..." if prerequisites else ""
    }
    return content, metadata


def chunk_text(text: str, max_chars: int = CHUNK_MAX_CHARS, overlap: int = CHUNK_OVERLAP) -> List[str]:
    if not text:
        return []
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    L = len(text)

    while start < L:
        end = min(start + max_chars, L)

        if end < L:
            sentence_end = text.rfind('.', start, end) + 1
            if sentence_end > start and (sentence_end - start) > max_chars * 0.7:
                end = sentence_end
            else:
                paragraph_end = text.rfind('\n\n', start, end)
                if paragraph_end > start and (paragraph_end - start) > max_chars * 0.7:
                    end = paragraph_end

        chunk = text[start:end].strip()
        chunks.append(chunk)
        if end == L:
            break
        start = max(start, end - overlap)

    return chunks


def robust_load_json(path: str) -> Any:
    """
    尝试多种方式读取 JSON：utf-8 / utf-8-sig / jsonl
    """
    # normal utf-8
    try:
        with open(path, "r", encoding="utf-8") as fr:
            return json.load(fr)
    except Exception:
        pass
    try:
        with open(path, "r", encoding="utf-8-sig") as fr:
            return json.load(fr)
    except Exception:
        pass
    # json lines
    try:
        objs = []
        with open(path, "r", encoding="utf-8") as fr:
            for line in fr:
                line = line.strip()
                if not line:
                    continue
                objs.append(json.loads(line))
        return objs
    except Exception:
        pass
    raise RuntimeError(f"无法解析 JSON 文件: {path}")


class APIEmbeddingModel:
    """
    将百炼兼容 API 封装成与 SentenceTransformer.encode 接口兼容的 wrapper。
    encode(texts, convert_to_numpy=True, batch_size=None) -> np.ndarray(float32)
    """
    def __init__(self, client, model_name: str, dimensions: int = API_DIMENSIONS, batch_size: int = API_BATCH_SIZE, max_retries:int=3):
        self.client = client
        self.model_name = model_name
        self.dim = dimensions
        self.batch_size = max(1, int(batch_size))
        self.max_retries = int(max_retries)

    def encode(self, texts, convert_to_numpy=True, show_progress_bar=False, batch_size=None):
        # 兼容单字符串或字符串列表
        single = False
        if isinstance(texts, str):
            texts = [texts]
            single = True

        # 如果外部传了 batch_size，限制为 self.batch_size（避免传入过大值导致 API 报错）
        if batch_size is None:
            call_batch = self.batch_size
        else:
            call_batch = min(int(batch_size), self.batch_size)

        embeddings = []
        for i in range(0, len(texts), call_batch):
            sub = texts[i:i + call_batch]
            attempts = 0
            while True:
                try:
                    resp = self.client.embeddings.create(
                        model=self.model_name,
                        input=sub,
                        dimensions=self.dim,
                        encoding_format="float"
                    )
                    # resp.data 列表与输入顺序一致
                    for item in resp.data:
                        embeddings.append(item.embedding)
                    break
                except Exception as e:
                    attempts += 1
                    if attempts >= self.max_retries:
                        print(f"[APIEmbeddingModel] 批量 embedding 调用失败（索引 {i}，重试 {attempts} 次后）：{e}")
                        # 失败时补零向量，保证数量对齐
                        for _ in sub:
                            embeddings.append([0.0] * self.dim)
                        break
                    else:
                        backoff = 2 ** attempts
                        print(f"[APIEmbeddingModel] 调用失败（索引 {i}），第 {attempts} 次重试，backoff={backoff}s：{e}")
                        time.sleep(backoff)

        arr = np.array(embeddings, dtype=np.float32)
        if convert_to_numpy:
            return arr
        else:
            return arr.tolist()

def build_index_incremental(all_texts_iterable, model_name: str = LOCAL_MODEL_NAME):
    """
    all_texts_iterable: generator 或 iterable，yield (text, metadata)
    增量生成 embeddings 并构建 FAISS
    """
    print(f"加载 embedding 模型：{model_name if not USE_API_EMBEDDING else API_MODEL_NAME}")
    model = None
    if USE_API_EMBEDDING:
        if client is None:
            raise RuntimeError("USE_API_EMBEDDING=True，但未初始化 API client，请检查环境变量 DASHSCOPE_API_KEY")
        model = APIEmbeddingModel(client, model_name, dimensions=API_DIMENSIONS, batch_size=API_BATCH_SIZE)
    else:
        model = SentenceTransformer(model_name)

    index = None
    metadata_list = []
    total_vectors = 0
    batch_texts, batch_metas = [], []

    def flush_batch(batch_texts_local, batch_metas_local):
        nonlocal index, total_vectors
        if not batch_texts_local:
            return

        # 统一通过 model.encode 获取 embeddings（API 或本地模型）
        emb = model.encode(batch_texts_local, convert_to_numpy=True, show_progress_bar=False, batch_size=None)
        if not isinstance(emb, np.ndarray):
            emb = np.array(emb, dtype=np.float32)
        if emb.dtype != np.float32:
            emb = emb.astype(np.float32)

        # 归一化后用 IndexFlatIP（cosine via normalized vectors）
        faiss.normalize_L2(emb)
        if index is None:
            dim = emb.shape[1]
            index = faiss.IndexFlatIP(dim)
            print(f"创建 FAISS 索引，维度 = {dim}")
        index.add(emb)
        total_vectors += emb.shape[0]
        metadata_list.extend(batch_metas_local)
        print(f"[flush_batch] 添加 {emb.shape[0]} 个向量到索引，当前总向量数（近似）={total_vectors}")

    for text, meta in tqdm(all_texts_iterable, desc="处理文档"):
        batch_texts.append(text)
        batch_metas.append(meta)
        if len(batch_texts) >= BATCH_TEXTS:
            flush_batch(batch_texts, batch_metas)
            batch_texts, batch_metas = [], []

    if batch_texts:
        flush_batch(batch_texts, batch_metas)

    if index is None:
        raise RuntimeError("没有生成任何向量，无法创建索引，请检查数据来源。")
    print(f"总向量数：{total_vectors}")
    return index, metadata_list, model


def query_index(query: str, model, index: faiss.Index, metadata: List[Dict[str, Any]], top_k: int = 5, expand: bool = False):
    if expand:
        query = expand_query(query)

    # model.encode 返回 numpy array，形状 (1, dim)
    q_emb = model.encode([query], convert_to_numpy=True)
    if isinstance(q_emb, list):
        q_emb = np.array(q_emb, dtype=np.float32)
    if q_emb.dtype != np.float32:
        q_emb = q_emb.astype(np.float32)
    faiss.normalize_L2(q_emb)
    D, I = index.search(q_emb, top_k)
    results = []
    for score, idx in zip(D[0], I[0]):
        if idx < 0:
            continue
        m = metadata[idx].copy()
        m["score"] = float(score)
        results.append(m)
    return results


def expand_query(query: str) -> str:
    expansions = {
        "principles": ["fundamentals", "basics", "core concepts"],
        "methods": ["techniques", "approaches", "methodologies"],
        "analysis": ["evaluation", "assessment", "examination"],
        "introduction": ["overview", "foundation", "primer"]
    }

    expanded = []
    for word in query.split():
        word_lower = word.lower()
        if word_lower in expansions:
            expanded.append(word)
            expanded.extend(expansions[word_lower])
        else:
            expanded.append(word)

    return " ".join(expanded)


def evaluate_retrieval(model, index, metadata):
    """评估检索效果"""
    test_queries = [
        ("Introduction to programming", "COMP1000"),
        ("Advanced calculus", "MATH2001"),
        ("Financial accounting principles", "ACCT2010")
    ]

    print("\n检索效果评估:")
    for query, expected_code in test_queries:
        print(f"\n查询: '{query}'")
        print(f"预期课程: {expected_code}")

        results = query_index(query, model, index, metadata, top_k=3)
        found = any(r.get('course_code') == expected_code for r in results)
        print(f"普通查询 - 预期课程{'找到' if found else '未找到'}")
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r.get('course_code')} - {r.get('title')} (score: {r.get('score'):.4f})")

        results_exp = query_index(query, model, index, metadata, top_k=3, expand=True)
        found_exp = any(r.get('course_code') == expected_code for r in results_exp)
        print(f"扩展查询 - 预期课程{'找到' if found_exp else '未找到'}")
        for i, r in enumerate(results_exp, 1):
            print(f"  {i}. {r.get('course_code')} - {r.get('title')} (score: {r.get('score'):.4f})")


def main():
    subjects = load_subjects(SUBJECT_FILE)
    print(f"从 {SUBJECT_FILE} 加载了 {len(subjects)} 个 subject")

    def texts_generator():
        for subject in subjects:
            files = find_files_for_subject(subject, DATA_DIR)
            if not files:
                print(f"[WARN] 未在 {DATA_DIR} 找到与 subject '{subject}' 匹配的文件")
                continue
            for fpath in files:
                try:
                    data = robust_load_json(fpath)
                except Exception as e:
                    print(f"[ERROR] 读取/解析 文件 {fpath} 失败: {e}")
                    continue

                records = []
                if isinstance(data, dict):
                    if any(k in data for k in ("data", "courses", "records")):
                        for k in ("data", "courses", "records"):
                            if k in data and isinstance(data[k], list):
                                records = data[k]
                                break
                    else:
                        records = [data]
                elif isinstance(data, list):
                    records = data
                else:
                    print(f"[WARN] 文件 {fpath} 内容格式非 dict/list，跳过。")
                    continue

                for rec in records:
                    if not isinstance(rec, dict):
                        rec = {"raw": rec}
                    content, meta = record_to_content_and_meta(rec, fpath, subject)
                    if not content.strip():
                        continue
                    chunks = chunk_text(content)
                    for i, c in enumerate(chunks):
                        meta_copy = meta.copy()
                        meta_copy["_content"] = c
                        meta_copy["chunk_index"] = i
                        meta_copy["chunk_count"] = len(chunks)
                        yield c, meta_copy

    index, metadata_list, model = build_index_incremental(texts_generator(), API_MODEL_NAME if USE_API_EMBEDDING else LOCAL_MODEL_NAME)

    # 保存索引
    faiss.write_index(index, FAISS_INDEX_PATH)
    print(f"FAISS index saved to {FAISS_INDEX_PATH}")

    # 保存 metadata jsonl
    with open(METADATA_PATH, "w", encoding="utf-8") as fw:
        for m in metadata_list:
            fw.write(json.dumps(m, ensure_ascii=False) + "\n")
    print(f"Metadata saved to {METADATA_PATH}")

    # 示例查询
    print("\n示例查询：")
    q = "financial accounting principles and methods"
    res = query_index(q, model, index, metadata_list, top_k=TOP_K)
    for i, r in enumerate(res, 1):
        print(f"Top {i}: course_code={r.get('course_code')}, title={r.get('title')}, subject={r.get('subject')}, score={r.get('score'):.4f}")

    # 评估检索效果
    evaluate_retrieval(model, index, metadata_list)


if __name__ == "__main__":
    main()
