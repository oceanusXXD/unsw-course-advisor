# backend/chatbot/rag_chain_qwen.py
# coding: utf-8
"""
检索模块
- retrieve(query, top_k) 仅执行本地 embedding -> FAISS 检索并返回 JSON-可序列化的 docs 列表
- list_all_course_codes() 返回索引中所有 course_code（便于调试）
- extract_course_code_from_query / get_doc_by_course_code 辅助函数
注意：**此文件不包含任何大模型/QWEN 调用或 prompt 逻辑**
"""

from typing import List, Dict, Any, Optional, Tuple
import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import re

# ---------- 配置（按需修改） ----------
FAISS_INDEX_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "RAG_database", "vector_store", "faiss_index.bin")
METADATA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "RAG_database", "vector_store", "metadata.jsonl")
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_TOP_K = 8
# -------------------------------------------------
# 内部缓存
_emb_model = None
_faiss_index = None
_metadata = None

def _load_embedding_model():
    global _emb_model
    if _emb_model is None:
        _emb_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _emb_model

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

def embed_query(query: str):
    """
    生成并归一化 embedding （返回 numpy array shape (1, dim)）
    """
    model = _load_embedding_model()
    emb = model.encode([query], convert_to_numpy=True)
    if emb.dtype != np.float32:
        emb = emb.astype(np.float32)
    faiss.normalize_L2(emb)
    return emb

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
    纯检索（本地）：
    - 使用 embedding + faiss.search 得到 top_k 索引
    - 如果 query 包含课程 code 且该 code 在 metadata 中但未命中 top_k，
      尝试 reconstruct 向量计算相似度并插入（回退为置顶）
    返回列表：每项为 dict，包含至少字段：
      {
        "course_code": str,
        "source_file": str,
        "_score": float,
        "_text": str,          # 用于展示/preview 的文本片段
        "_meta_index": int     # 原 metadata 索引，便于后续定位/增量更新
        ... 其他原始 metadata 字段（安全地拷贝）
      }
    注意：返回结果仅包含基础 Python 类型（float/str/bool/list/dict），可直接 json.dumps
    """
    index, metadata = load_faiss_and_metadata()
    q_emb = embed_query(query)

    try:
        D, I = index.search(q_emb, top_k)
    except Exception as e:
        # 若搜索失败，返回空列表
        print(f"[retrieve] FAISS search error: {e}")
        return []

    results = []
    seen_idx = set()
    for score, idx in zip(D[0], I[0]):
        if idx < 0 or idx >= len(metadata):
            continue
        m = metadata[idx].copy()
        # 转换 numpy 类型为基础类型
        try:
            score_f = float(score)
        except Exception:
            score_f = float(np.array(score).item()) if hasattr(score, 'item') else 0.0
        m["_score"] = score_f
        m["_text"] = m.get("_content") or m.get("content") or m.get("overview") or ""
        m["_meta_index"] = int(idx)
        # 确保所有可 JSON 序列化：将 numpy 标量转成 python 原生
        for k, v in list(m.items()):
            if isinstance(v, (np.integer, np.floating)):
                m[k] = v.item()
        results.append(m)
        seen_idx.add(idx)

    # code 优先：如 query 有课程 code 且该 doc 不在 results 中，尝试 reconstruct 插入
    code = extract_course_code_from_query(query)
    if code:
        found = get_doc_by_course_code(code, metadata)
        if found:
            doc, doc_idx = found
            if doc_idx in seen_idx:
                # 已存在 —— 将该条移到最前面
                for i, r in enumerate(results):
                    rc = (r.get("course_code") or "").replace(" ", "").upper()
                    if rc == code:
                        results.insert(0, results.pop(i))
                        break
            else:
                # 尝试 reconstruct 计算相似度并插入
                try:
                    vec = index.reconstruct(doc_idx).astype(np.float32)
                    vec_norm = vec / (np.linalg.norm(vec) + 1e-12)
                    score_val = float(np.dot(q_emb[0], vec_norm))
                    doc_copy = metadata[doc_idx].copy()
                    doc_copy["_score"] = float(score_val)
                    doc_copy["_text"] = doc_copy.get("_content") or doc_copy.get("content") or doc_copy.get("overview") or ""
                    doc_copy["_meta_index"] = int(doc_idx)
                    # 插入到按 score 降序的位置
                    pos = 0
                    while pos < len(results) and results[pos].get("_score", 0) >= score_val:
                        pos += 1
                    results.insert(pos, doc_copy)
                except Exception:
                    # reconstruct 失败 -> 强制置顶
                    doc_copy = metadata[doc_idx].copy()
                    doc_copy["_score"] = (results[0].get("_score", 0) + 0.01) if results else 1.0
                    doc_copy["_text"] = doc_copy.get("_content") or doc_copy.get("overview") or ""
                    doc_copy["_meta_index"] = int(doc_idx)
                    results.insert(0, doc_copy)

    # 去重（按 course_code 或片段首120字符）
    seen = set()
    final = []
    for r in results:
        key = ((r.get("course_code") or "").upper()) or (r.get("_text") or "")[:120]
        if key in seen:
            continue
        seen.add(key)
        # 清理内部可能的 numpy 标量
        for k, v in list(r.items()):
            if isinstance(v, (np.integer, np.floating)):
                r[k] = v.item()
        final.append(r)

    # 最终裁剪到合理长度（不强制 top_k，但通常接近）
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
