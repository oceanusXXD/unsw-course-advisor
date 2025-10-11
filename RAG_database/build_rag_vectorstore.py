"""
build_rag_vectorstore.py

用途：
- 从 ./subject.txt 读取 subject 列表
- 在 ./data 下查找以 subject 为前缀的 *_course_detail.json 文件
- 解析并提取指定字段，清洗 HTML
- 用 sentence-transformers 生成 embedding
- 用 FAISS 建立向量索引，并保存索引 + metadata
- 提供查询示例

注意：
- 如果你希望使用 GPU 加速，请自行替换 faiss-cpu 与模型加载方式。
- 输出：./vector_store/faiss_index.bin 和 ./vector_store/metadata.jsonl
"""

import os
import glob
import json
from typing import List, Dict, Any
from bs4 import BeautifulSoup # type: ignore
from sentence_transformers import SentenceTransformer # type: ignore
import numpy as np
import faiss # type: ignore
from tqdm import tqdm

# ------------ 配置 ------------
SUBJECT_FILE = "./crawler/subject.txt"
DATA_DIR = "./data"
VECTOR_STORE_DIR = "./vector_store"
FAISS_INDEX_PATH = os.path.join(VECTOR_STORE_DIR, "faiss_index.bin")
METADATA_PATH = os.path.join(VECTOR_STORE_DIR, "metadata.jsonl")
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"  # 快速且效果不错的开源模型
EMBED_DIM = None  # 稍后由模型确定
TOP_K = 5
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
    # 查找以 subject 为前缀的所有文件（忽略大小写）
    pattern = os.path.join(data_dir, f"{subject}*_*course_detail.json")
    files = glob.glob(pattern)
    # 也尝试更简单的 pattern（若文件命名不同）
    if not files:
        pattern2 = os.path.join(data_dir, f"{subject}*_course_detail.json")
        files = glob.glob(pattern2)
    return sorted(files)

def strip_html(html_text: str) -> str:
    if html_text is None:
        return ""
    # 使用 BeautifulSoup 去除 HTML 标签
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    return text

def delivery_to_text(delivery_list: Any) -> str:
    # delivery 可能是 list of dicts
    if not delivery_list:
        return ""
    if isinstance(delivery_list, str):
        return delivery_list
    parts = []
    for d in delivery_list:
        if isinstance(d, dict):
            disp = d.get("display") or d.get("delivery_mode") or json.dumps(d, ensure_ascii=False)
            ch = f"{disp}"
            # 如果有 contact_hours 可附上
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

def record_to_content_and_meta(record: Dict[str, Any], source_file: str, subject: str) -> tuple[str, Dict[str, Any]]:
    # 提取字段并清洗
    course_code = record.get("course_code") or record.get("CourseCode") or ""
    overview = strip_html(record.get("overview") or record.get("Overview") or "")
    add_enrol = strip_html(record.get("additional_enrolment_constraints") or record.get("additionalEnrolmentConstraints") or "")
    equiv = normalize_equivalent(record.get("equivalent_courses") or record.get("equivalentCourses") or "")
    offering_terms = strip_html(record.get("offering_terms") or record.get("offeringTerms") or "")
    delivery = delivery_to_text(record.get("delivery"))
    # 合并成一个用于检索的文本（可根据需要调整字段顺序和标注）
    content_parts = [
        f"Course Code: {course_code}",
        f"Subject: {subject}",
        f"Overview: {overview}",
        f"Additional Enrolment Constraints: {add_enrol}",
        f"Equivalent Courses: {equiv}",
        f"Offering Terms: {offering_terms}",
        f"Delivery: {delivery}"
    ]
    content = "\n".join([p for p in content_parts if p.strip() != ""])
    metadata = {
        "course_code": course_code,
        "subject": subject,
        "source_file": os.path.basename(source_file),
        "offering_terms": offering_terms,
        "delivery": delivery,
        "equivalent_courses": equiv,
        "additional_enrolment_constraints": add_enrol,
        # 你可以在此加入更多元数据字段，方便后续过滤
    }
    return content, metadata

def build_vectors_and_index(all_texts: List[str], model_name: str):
    print(f"Loading embedding model: {model_name}")
    model = SentenceTransformer(model_name)
    # 生成 embeddings（batch）
    batch_size = 64
    embeddings = model.encode(all_texts, batch_size=batch_size, show_progress_bar=True, convert_to_numpy=True)
    global EMBED_DIM
    EMBED_DIM = embeddings.shape[1]
    print(f"Embedding dimension: {EMBED_DIM}, total vectors: {len(embeddings)}")
    # 使用内积相似度前先做向量归一化 -> 等价于 cosine 相似度
    faiss.normalize_L2(embeddings)
    # 建立索引（IndexFlatIP 适合做规范化后内积检索）
    index = faiss.IndexFlatIP(EMBED_DIM)
    index.add(embeddings)
    return index, embeddings, model

def save_index_and_metadata(index: faiss.Index, metadata_list: List[Dict[str, Any]], index_path: str, meta_path: str):
    # 保存 faiss 索引
    faiss.write_index(index, index_path)
    print(f"FAISS index saved to {index_path}")
    # 保存 metadata（jsonl）
    with open(meta_path, "w", encoding="utf-8") as fw:
        for m in metadata_list:
            fw.write(json.dumps(m, ensure_ascii=False) + "\n")
    print(f"Metadata saved to {meta_path}")

def load_index_and_metadata(index_path: str, meta_path: str):
    if not os.path.exists(index_path) or not os.path.exists(meta_path):
        raise FileNotFoundError("Index 或 metadata 文件不存在，请先运行 build 步骤。")
    index = faiss.read_index(index_path)
    metadata = []
    with open(meta_path, "r", encoding="utf-8") as fr:
        for line in fr:
            metadata.append(json.loads(line))
    return index, metadata

def query_index(query: str, model: SentenceTransformer, index: faiss.Index, metadata: List[Dict[str, Any]], top_k: int = 5):
    # 将查询转成 embedding，归一化，检索
    q_emb = model.encode([query], convert_to_numpy=True)
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

def main():
    subjects = load_subjects(SUBJECT_FILE)
    print(f"Loaded {len(subjects)} subjects from {SUBJECT_FILE}")

    all_texts = []
    all_metadata = []

    # 遍历每个 subject，查找匹配文件并解析
    for subject in subjects:
        files = find_files_for_subject(subject, DATA_DIR)
        if not files:
            print(f"[WARN] 未找到与 subject '{subject}' 匹配的文件（在 {DATA_DIR} 下）。")
            continue
        for fpath in files:
            try:
                with open(fpath, "r", encoding="utf-8") as fr:
                    data = json.load(fr)
                if isinstance(data, dict):
                    # 某些文件可能不是列表而是单个对象
                    data = [data]
                # 遍历数组记录
                for rec in data:
                    content, meta = record_to_content_and_meta(rec, fpath, subject)
                    if not content.strip():
                        continue
                    all_texts.append(content)
                    # 额外把原始 content 也存到 metadata 中，便于返回（可选）
                    meta["_content"] = content
                    all_metadata.append(meta)
            except Exception as e:
                print(f"[ERROR] 解析文件 {fpath} 出错: {e}")

    if not all_texts:
        print("没有找到任何可用文本，脚本结束。请检查数据文件。")
        return

    # 建立向量与索引
    index, embeddings, model = build_vectors_and_index(all_texts, EMBEDDING_MODEL_NAME)

    # 保存索引和 metadata
    save_index_and_metadata(index, all_metadata, FAISS_INDEX_PATH, METADATA_PATH)

    # 示范查询
    print("\n示例查询：")
    q = "financial accounting principles and methods"  # 你可以换成中文或其它英文/中文查询
    res = query_index(q, model, index, all_metadata, top_k=TOP_K)
    for i, r in enumerate(res, 1):
        print(f"Top {i}: course_code={r.get('course_code')}, subject={r.get('subject')}, score={r.get('score'):.4f}")
        # 如需打印 content，可用 r.get('_content')

if __name__ == "__main__":
    main()
