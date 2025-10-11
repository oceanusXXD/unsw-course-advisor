# coding: utf-8
"""
优化版 rag_chain_qwen.py

主要优化点（为了解决“已存在 metadata，但检索没命中特定课程”的问题）：
1. 如果用户问题中包含明确的课程代码（如 CHEM3041/ACCT2101），优先查找 metadata 中对应条目并把它置入检索结果顶部。
2. retrieve() 支持更大的 top_k（默认 8），并在 code 命中时尝试用 FAISS reconstruct 向量来计算真实相似度并作为排序依据（若 reconstruct 不可用则使用安全回退）。
3. 提供辅助函数 list_all_course_codes()，方便调试查看索引中有哪些课程。
4. 保持原有流式调用接口不变（answer_with_rag / stream_qwen_answer）。
"""

import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from typing import List, Dict, Generator, Optional, Any, Tuple
from dotenv import load_dotenv

# 自动加载 .env（可选）
load_dotenv()

# ---------------- 配置 ----------------
# 请根据你的实际目录调整这两项（最好用绝对路径以避免相对路径错误）
FAISS_INDEX_PATH = "../vector_store/faiss_index.bin"
METADATA_PATH = "../vector_store/metadata.jsonl"

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K = 8                # 默认检索数调大一些
MAX_CONTEXT_CHARS = 3000

API_KEY_ENV = "DASHSCOPE_API_KEY"
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_MODEL = "qwen3-max"
# --------------------------------------

_emb_model = None
_faiss_index = None
_metadata = None
_openai_client = None

def _load_embedding_model():
    global _emb_model
    if _emb_model is None:
        _emb_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _emb_model

def load_faiss_and_metadata(index_path=FAISS_INDEX_PATH, meta_path=METADATA_PATH) -> Tuple[faiss.Index, List[Dict[str,Any]]]:
    global _faiss_index, _metadata
    if _faiss_index is None:
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"Can't find FAISS index at {index_path}")
        _faiss_index = faiss.read_index(index_path)
    if _metadata is None:
        if not os.path.exists(meta_path):
            raise FileNotFoundError(f"Can't find metadata file at {meta_path}")
        _metadata = []
        with open(meta_path, "r", encoding="utf-8") as fr:
            for line in fr:
                try:
                    _metadata.append(json.loads(line))
                except Exception:
                    continue
    return _faiss_index, _metadata

def _init_openai_client(api_key: Optional[str] = None, base_url: Optional[str] = None):
    global _openai_client
    if _openai_client is None:
        apikey = api_key or os.getenv(API_KEY_ENV)
        if not apikey:
            raise ValueError(f"API key 未设置，请设置环境变量 {API_KEY_ENV} 或传入 api_key 参数。")
        _openai_client = OpenAI(api_key=apikey, base_url=(base_url or QWEN_BASE_URL))
    return _openai_client

def embed_query(query: str) -> np.ndarray:
    model = _load_embedding_model()
    emb = model.encode([query], convert_to_numpy=True)
    faiss.normalize_L2(emb)
    return emb  # shape (1, dim)

# -------- 辅助：从问题中提取课程代码 --------
import re
_course_code_re = re.compile(r'\b([A-Za-z]{2,5})\s*[-]?\s*(\d{3,4})\b')  # 如 ACCT2101 或 ACCT-2101 或 acct2101

def extract_course_code_from_query(query: str) -> Optional[str]:
    if not query:
        return None
    m = _course_code_re.search(query)
    if not m:
        return None
    code = (m.group(1) + m.group(2)).upper().replace(" ", "")
    return code

def get_doc_by_course_code(code: str, metadata: List[Dict[str,Any]]) -> Optional[Tuple[Dict[str,Any], int]]:
    """
    在 metadata 中查找 course_code 匹配的条目，返回 (doc, index)
    index 为该 doc 在 metadata 中的位置（对应 faiss 索引顺序）
    """
    if not code:
        return None
    norm = code.replace(" ", "").upper()
    for idx, d in enumerate(metadata):
        c = (d.get("course_code") or "").replace(" ", "").upper()
        if c == norm:
            return d, idx
    return None

# -------- 主检索函数（支持 code 优先） --------
def retrieve(query: str, top_k: int = TOP_K) -> List[Dict[str,Any]]:
    """
    检索逻辑：
    1) 尝试从 query 提取课程代码（如 CHEM3041）
    2) 用 FAISS 做常规搜索拿到 top_k
    3) 如果 code 在 metadata 中但未出现在 top_k 里，尝试 reconstruct 向量计算真实相似度并把该 doc 插入到最相关的位置（优先置顶）
    返回带 _score 与 _text 字段的 metadata 列表（按分数降序）
    """
    index, metadata = load_faiss_and_metadata()
    q_emb = embed_query(query)  # 形状 (1, dim)

    # 1. 常规检索
    try:
        D, I = index.search(q_emb, top_k)
    except Exception as e:
        # 若 index.search 失败，返回空
        print(f"[ERROR] FAISS search failed: {e}")
        return []

    results = []
    seen_idx = set()
    for score, idx in zip(D[0], I[0]):
        if idx < 0 or idx >= len(metadata):
            continue
        m = metadata[idx].copy()
        try:
            m["_score"] = float(score)
        except Exception:
            m["_score"] = score
        m["_text"] = m.get("_content") or m.get("content") or m.get("overview") or ""
        results.append(m)
        seen_idx.add(idx)

    # 2. code 优先策略
    code = extract_course_code_from_query(query)
    if code:
        found = get_doc_by_course_code(code, metadata)
        if found:
            doc, doc_idx = found
            # 如果在结果里已经存在则确保它置顶（按 score 排序）
            if doc_idx in seen_idx:
                # 已存在 —— 将该项移动到结果最前面（并保持分数）
                # 找对应条目并移动至首位
                for i, r in enumerate(results):
                    if (r.get("course_code") or "").replace(" ", "").upper() == code:
                        # move to front
                        results.insert(0, results.pop(i))
                        break
            else:
                # 不在 top_k 里，尝试 reconstruct 向量并计算相似度，再插入
                inserted = False
                try:
                    # reconstruct 向量（不是所有索引支持）
                    vec = index.reconstruct(doc_idx)  # shape (d,)
                    # 确保 q_emb 和 vec 都归一化（q_emb 已归一化）
                    # reconstruct 的向量未必归一化，归一化后计算内积
                    vec = vec.astype(np.float32)
                    vec_norm = vec / (np.linalg.norm(vec) + 1e-12)
                    score = float(np.dot(q_emb[0], vec_norm))
                    # 插入以保持排序（降序）
                    doc_copy = metadata[doc_idx].copy()
                    doc_copy["_score"] = score
                    doc_copy["_text"] = doc_copy.get("_content") or doc_copy.get("content") or doc_copy.get("overview") or ""
                    # 插入到结果中合适的位置（按 score 降序）
                    pos = 0
                    while pos < len(results) and results[pos].get("_score", 0) >= score:
                        pos += 1
                    results.insert(pos, doc_copy)
                    inserted = True
                except Exception:
                    # 无法 reconstruct（或中途失败），将该 doc 强置为首位（保守方式）
                    doc_copy = metadata[doc_idx].copy()
                    doc_copy["_score"] = results[0].get("_score", 1.0) + 0.01 if results else 1.0
                    doc_copy["_text"] = doc_copy.get("_content") or doc_copy.get("content") or doc_copy.get("overview") or ""
                    results.insert(0, doc_copy)
                    inserted = True
                if inserted:
                    # 确保不超过 top_k 长度（但返回可能稍多）
                    if len(results) > max(top_k, 16):
                        results = results[:max(top_k, 16)]
    # 最终去重（按 course_code 或 _text）
    seen = set()
    final = []
    for r in results:
        key = ((r.get("course_code") or "").upper()) or (r.get("_text") or "")[:120]
        if key in seen:
            continue
        seen.add(key)
        final.append(r)
    return final

# -------- 列出索引中所有课程代码（供调试） --------
def list_all_course_codes() -> List[str]:
    _, metadata = load_faiss_and_metadata()
    codes = []
    for d in metadata:
        c = d.get("course_code") or ""
        if c:
            codes.append(c)
    return codes

# ---------------- Prompt（不变，可在此微调） ----------------
BASE_PROMPT_INSTRUCTIONS = """
你是 UNSW 课程资料助手（中文）。你**仅能**基于下面的【检索到的课程資料】作答，必须：
1) 使用中文，回答清晰、简洁（適合学生快速阅读）。
2) 优先引用检索到的具体课程（用方括号标注课程代码，例如 [ACCT2101]），若信息来自多个课程可并列标注。
3) 对于课程先修、入学约束、开课学期、教学方式等事实性問題，应直接给出明确答案并在结尾列出来源课程代码与来源类型（embedded_json/dom）。
4) 如果检索上下文不包含相关信息，应明确说明：我无法在检索到的資料中找到相关信息，并建议检查课程代码或到 UNSW Handbook 官网查询。
5) 禁止凭空编造；若必须推断，請注明“推断：...”，并降低置信度。
"""

RESPONSE_WRAPPER = """
请用不超过 300 字的中文回答用户問題，并在最後一行 `来源：` 列出使用到的课程代码及其来源类型（示例：来源：[ACCT2101 - embedded_json], [ACCT2511 - dom]）。
如果没有找到相关信息，请返回：“未在检索到的资料中找到相关信息。建议：确认课程代码或访问 UNSW Handbook 原文。”
"""

def _truncate_context(parts: List[str], max_chars: int = MAX_CONTEXT_CHARS) -> str:
    out = []
    cur_len = 0
    for p in parts:
        if not p:
            continue
        if cur_len + len(p) + 2 > max_chars:
            if not out:
                out.append(p[:max_chars - 10] + "...")
            break
        out.append(p)
        cur_len += len(p) + 2
    return "\n\n".join(out)

def build_prompt(query: str, retrieved_docs: List[Dict[str,Any]]) -> str:
    parts = []
    for doc in retrieved_docs:
        code = doc.get("course_code") or ""
        source = doc.get("source", doc.get("source_file", "unknown"))
        text = doc.get("_text") or ""
        header = f"[{code}] ({source})" if code or source else ""
        parts.append(f"{header}\n{text}".strip())
    context = _truncate_context(parts, MAX_CONTEXT_CHARS)
    prompt = BASE_PROMPT_INSTRUCTIONS.strip() + "\n\n" \
             + "【检索到的课程资料（用户问题应基于此）】:\n" + context + "\n\n" \
             + "【用户问题】:\n" + query.strip() + "\n\n" \
             + RESPONSE_WRAPPER.strip()
    return prompt

# ---------------- QWEN 调用（流式） ----------------
def stream_qwen_answer(prompt: str,
                       model: str = QWEN_MODEL,
                       api_key: Optional[str] = None,
                       base_url: Optional[str] = None,
                       temperature: float = 0.0,
                       max_tokens: int = 512) -> Generator[str, None, None]:
    client = _init_openai_client(api_key=api_key, base_url=base_url)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt}
    ]
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True
    )
    try:
        for chunk in completion:
            content = None
            try:
                content = chunk.choices[0].delta.content
            except Exception:
                try:
                    delta = getattr(chunk.choices[0], "delta", None)
                    if isinstance(delta, dict):
                        content = delta.get("content")
                except Exception:
                    pass
            if not content:
                try:
                    content = chunk.choices[0].text
                except Exception:
                    pass
            if content:
                yield content
    except Exception as e:
        yield f"\n\n[错误] 模型返回异常：{e}"

# ---------------- 高层调用 ----------------
def answer_with_rag(query: str,
                    top_k: int = TOP_K,
                    stream: bool = True,
                    api_key: Optional[str] = None,
                    base_url: Optional[str] = None,
                    **model_kwargs):
    # 先检索（retrieve 会处理 code 优先）
    docs = retrieve(query, top_k=top_k)
    prompt = build_prompt(query, docs)
    if stream:
        return stream_qwen_answer(prompt, api_key=api_key, base_url=base_url, **model_kwargs)
    else:
        parts = []
        for chunk in stream_qwen_answer(prompt, api_key=api_key, base_url=base_url, **model_kwargs):
            parts.append(chunk)
        return "".join(parts), docs

# ---------------- CLI 调试 ----------------
if __name__ == "__main__":
    q = input("请输入问题（中文）：").strip()
    # 小工具：如果想查看索引中是否含有某 code，可用 list_all_course_codes()
    print("检索 top_k 文档：")
    res = retrieve(q, top_k=8)
    for r in res:
        print(r.get("course_code"), r.get("_score"))
    gen = answer_with_rag(q, stream=True)
    for t in gen:
        print(t, end="", flush=True)
    print("\n\n=== END ===")
