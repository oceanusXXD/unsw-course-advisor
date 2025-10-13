# build_course_datail_vector_db.py
"""
用途：
- 从 ./crawler/subject.txt 读取 subject 列表
- 在 ./data 下查找以 subject 为前缀/包含 subject 的 *_course_detail.json 文件（更宽松匹配）
- 解析并提取指定字段，清洗 HTML
- 对长文本做切分（chunking）
- 用 sentence-transformers 生成 embedding（分批）
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
# ------------ 配置 ------------
SUBJECT_FILE = "../crawler/subject.txt"
DATA_DIR = "../course_detail_data"
VECTOR_STORE_DIR = "./vector_store"
FAISS_INDEX_PATH = os.path.join(VECTOR_STORE_DIR, "faiss_index.bin")
METADATA_PATH = os.path.join(VECTOR_STORE_DIR, "metadata.jsonl")
LOCAL_MODEL_NAME = "all-mpnet-base-v2"  # 升级到更强大的模型
BATCH_TEXTS = 128   # 更小的批次大小以适应更大的模型
CHUNK_MAX_CHARS = 512  # 更小的块大小
CHUNK_OVERLAP = 128    # 适当的重叠
TOP_K = 10             # 返回更多结果用于评估
USE_API_EMBEDDING = True  # True 使用百炼 API，False 使用本地模型
API_MODEL_NAME = "text-embedding-v4"
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
    这样能覆盖多种命名变体。
    """
    subject_low = subject.lower()
    matches = []
    for root, _, files in os.walk(data_dir):
        for fn in files:
            fn_low = fn.lower()
            if subject_low in fn_low and "course_detail.json" in fn_low:
                matches.append(os.path.join(root, fn))
    # 作为 fallback，也尝试 glob 的简单模式
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
        except:
            return ""
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    # 简单去除多余空白
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
    # 兼容多种命名字段
    course_code = record.get("course_code") or record.get("CourseCode") or record.get("code") or ""
    title = strip_html(record.get("title") or record.get("name") or "")
    
    # 提取更多可能包含关键信息的字段
    overview = strip_html(record.get("overview") or record.get("Overview") or record.get("description") or "")
    learning_outcomes = strip_html(record.get("learning_outcomes") or record.get("learningOutcomes") or "")
    assessment = strip_html(record.get("assessment") or record.get("assessmentMethods") or "")
    prerequisites = strip_html(record.get("prerequisites") or record.get("pre-requisites") or "")
    add_enrol = strip_html(record.get("additional_enrolment_constraints") or record.get("additionalEnrolmentConstraints") or "")
    equiv = normalize_equivalent(record.get("equivalent_courses") or record.get("equivalentCourses") or record.get("equivalents") or "")
    offering_terms = strip_html(record.get("offering_terms") or record.get("offeringTerms") or record.get("terms") or "")
    delivery = delivery_to_text(record.get("delivery") or record.get("delivery_modes") or record.get("deliveryMode"))
    
    # 合并文本 - 使用结构化格式
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
    
    # 过滤空内容并连接
    content = "\n\n".join([p for p in content_parts if p.strip() != ""])
    
    # 增强元数据
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
    
    # 尝试使用句子边界进行分块
    chunks = []
    start = 0
    L = len(text)
    
    while start < L:
        end = min(start + max_chars, L)
        
        # 尝试在句子边界处结束
        if end < L:
            # 找到最近的句子结束点
            sentence_end = text.rfind('.', start, end) + 1
            if sentence_end > start and (sentence_end - start) > max_chars * 0.7:
                end = sentence_end
            else:
                # 如果没有找到合适的句子结束点，尝试在段落边界处结束
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
    尝试多种方式读取 JSON：
    - 普通 utf-8/utf-8-sig
    - jsonl：每行一个 json
    返回：python 对象 或 raise
    """
    # 首先尝试正常读取
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
    # 尝试 json lines
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
    # 最后抛错
    raise RuntimeError(f"无法解析 JSON 文件: {path}")

def build_index_incremental(all_texts_iterable, model_name: str = LOCAL_MODEL_NAME):
    """
    all_texts_iterable: generator 或 iterable，yield (text, metadata)
    增量生成 embeddings 并构建 FAISS
    """
    print(f"加载 embedding 模型：{model_name if not USE_API_EMBEDDING else API_MODEL_NAME}")
    model = None
    if not USE_API_EMBEDDING:
        model = SentenceTransformer(model_name)

    index = None
    metadata_list = []
    total_vectors = 0
    batch_texts, batch_metas = [], []

    def flush_batch(batch_texts, batch_metas):
        nonlocal index, total_vectors
        if not batch_texts:
            return

        if USE_API_EMBEDDING:
            emb_list = []
            for text in batch_texts:
                try:
                    resp = client.embeddings.create(
                        model=API_MODEL_NAME,
                        input=text,
                        dimensions=1024,
                        encoding_format="float"
                    )
                    emb_list.append(resp.data[0].embedding)
                except Exception as e:
                    print(f"[flush_batch] embedding 调用失败: {e}")
                    emb_list.append([0.0]*1024)
            emb = np.array(emb_list, dtype=np.float32)
        else:
            emb = model.encode(batch_texts, batch_size=BATCH_TEXTS, show_progress_bar=False, convert_to_numpy=True)
            if emb.dtype != np.float32:
                emb = emb.astype(np.float32)

        faiss.normalize_L2(emb)
        if index is None:
            dim = emb.shape[1]
            index = faiss.IndexFlatIP(dim)
            print(f"创建 FAISS 索引，维度 = {dim}")
        index.add(emb)
        total_vectors += emb.shape[0]
        metadata_list.extend(batch_metas)

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

def query_index(query: str, model: SentenceTransformer, index: faiss.Index, metadata: List[Dict[str, Any]], top_k: int = 5, expand: bool = False):
    # 查询扩展
    if expand:
        query = expand_query(query)
    
    q_emb = model.encode([query], convert_to_numpy=True)
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
    """添加相关术语扩展查询"""
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
        
        # 普通查询
        results = query_index(query, model, index, metadata, top_k=3)
        found = any(r.get('course_code') == expected_code for r in results)
        print(f"普通查询 - 预期课程{'找到' if found else '未找到'}")
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r.get('course_code')} - {r.get('title')} (score: {r.get('score'):.4f})")
        
        # 扩展查询
        results_exp = query_index(query, model, index, metadata, top_k=3, expand=True)
        found_exp = any(r.get('course_code') == expected_code for r in results_exp)
        print(f"扩展查询 - 预期课程{'找到' if found_exp else '未找到'}")
        for i, r in enumerate(results_exp, 1):
            print(f"  {i}. {r.get('course_code')} - {r.get('title')} (score: {r.get('score'):.4f})")

def main():
    subjects = load_subjects(SUBJECT_FILE)
    print(f"从 {SUBJECT_FILE} 加载了 {len(subjects)} 个 subject")
    # 生成一个 generator，逐条产出 (text, meta)
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
                # 支持几种常见包装形式
                records = []
                if isinstance(data, dict):
                    # 常见：{ "data": [...]} 或 {"courses": [...]} 或直接就是一个记录
                    if any(k in data for k in ("data", "courses", "records")):
                        for k in ("data", "courses", "records"):
                            if k in data and isinstance(data[k], list):
                                records = data[k]
                                break
                    else:
                        # 把 dict 当作单条记录
                        records = [data]
                elif isinstance(data, list):
                    records = data
                else:
                    print(f"[WARN] 文件 {fpath} 内容格式非 dict/list，跳过。")
                    continue

                # 遍历 records
                for rec in records:
                    if not isinstance(rec, dict):
                        # 如果是字符串或其他，尝试包装
                        rec = {"raw": rec}
                    content, meta = record_to_content_and_meta(rec, fpath, subject)
                    if not content.strip():
                        # 没有可检索文本则跳过
                        continue
                    # 切分成 chunk
                    chunks = chunk_text(content)
                    for i, c in enumerate(chunks):
                        meta_copy = meta.copy()
                        meta_copy["_content"] = c
                        meta_copy["chunk_index"] = i
                        meta_copy["chunk_count"] = len(chunks)
                        yield c, meta_copy

    # 构建索引（增量）
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
        # 如果你想查看 content，可以打印 r.get('_content')[:500]
    
    # 评估检索效果
    evaluate_retrieval(model, index, metadata_list)

if __name__ == "__main__":
    main()