# RAG_database/parallel_search_and_rerank.py

import sys
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

# --- 1. 核心依赖 (Reranker) ---
import torch
from sentence_transformers import CrossEncoder

# --- 2. 导入你的类 ---

# 动态添加项目根目录到 sys.path，以解析 'backend' 和 'RAG_database'
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# 导入你的 VectorSearch 类（相对导入）
# (假设 vector_search.py 在同一目录 RAG_database 下)
try:
    from .vector_search import VectorSearch, SearchResult
except ImportError:
    print("WARNING: Could not use relative import for VectorSearch. Trying absolute.")
    # (如果从项目根目录运行，这个会生效)
    from RAG_database.vector_search import VectorSearch, SearchResult


# 导入你的 KnowledgeGraphQuery 类
# (需要 networkx 和 pickle 才能成功导入)
import networkx as nx
import pickle
from backend.chatbot.langgraph_agent.tools.knowledge_graph_query import KnowledgeGraphQuery


# --- 3. 路径和常量配置 ---
# (自动推断路径)
VECTOR_STORE_PATH = PROJECT_ROOT / "course_data" / "vector_store"
KG_PATH = PROJECT_ROOT / "course_data" / "knowledge_graph" / "course_kg.pkl"

# (用于匹配 COMP1511, COMP3900, COMPIH, GSOE9820 等)
ENTITY_REGEX = re.compile(
    r'\b([A-Z]{4}\d{4}|[A-Z]{4}[A-Z]{2,6})\b', 
    re.IGNORECASE
)

# (Reranker 使用的 K，我们会多检索一些给 Reranker 排序)
INITIAL_K_MULTIPLIER = 3 
# (Reranker 的最小分数，低于此分数的将被丢弃)
MIN_RERANK_SCORE = -5.0 

# --- 4. 全局初始化 (加载一次, 随处复用) ---

print("Initializing Hybrid Search Service...")

# 4.1. 加载重排器 (Reranker)
print("Loading Reranker model (BAAI/bge-reranker-base)...")
try:
    _RERANKER_DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
    _RERANKER_MODEL = CrossEncoder(
        'BAAI/bge-reranker-base',
        max_length=512,
        device=_RERANKER_DEVICE
    )
    print(f"[OK] Reranker loaded on device: {_RERANKER_DEVICE}")
except Exception as e:
    print(f"[WARN] Failed to load Reranker model: {e}")
    _RERANKER_MODEL = None

# 4.2. 加载 VectorSearch
print(f"Loading Vector Store from: {VECTOR_STORE_PATH}")
try:
    # (使用你的 vector_search.py 中的 main() 函数的配置)
    _SEARCHER = VectorSearch(
        persist_directory=str(VECTOR_STORE_PATH),
        model_name='BAAI/bge-small-en-v1.5', # 确保这与你 build 时一致
        collection_name="unsw_courses"
    )
    print("[OK] VectorSearch initialized.")
except Exception as e:
    print(f"[WARN] Failed to initialize VectorSearch: {e}")
    _SEARCHER = None

# 4.3. 加载 KnowledgeGraph
print(f"Loading Knowledge Graph from: {KG_PATH}")
try:
    _KG_QUERY = KnowledgeGraphQuery(graph_path=str(KG_PATH))
    print("[OK] KnowledgeGraphQuery initialized.")
except Exception as e:
    print(f"[WARN] Failed to initialize KnowledgeGraphQuery: {e}")
    _KG_QUERY = None

print("--- Hybrid Search Service Ready ---")


# --- 5. 标准化函数 (统一数据格式) ---

def _standardize_vector_doc(doc: SearchResult) -> Optional[Dict[str, Any]]:
    """
    将来自 VectorSearch 的 SearchResult *对象* 转换为统一的 dict 格式
    """
    try:
        meta = doc.metadata or {}
        text = doc.text or ""
        
        # 提取标题
        title = (
            meta.get("course_name") or 
            meta.get("major_title") or 
            meta.get("course_code") or 
            meta.get("group_title") or 
            "Vector Result"
        )
        
        # 提取 URL
        url = meta.get("url") or meta.get("source_url")
        
        # 提取 Snippet
        snippet = text
        if not snippet or len(snippet.split()) < 5:
            snippet = meta.get("description", text)

        return {
            "_text": text,
            "metadata": meta, # 保留原始 metadata
            "url": url,
            "title": f"{title}", # (VS)
            "snippet": snippet,
            "original_score": doc.score,
            "source_type": "vector_search"
        }
    except Exception as e:
        print(f"Error standardizing vector doc: {e}")
        return None

def _standardize_kg_doc(node_data: Dict[str, Any], entity_code: str) -> Optional[Dict[str, Any]]:
    """
    将来自 KnowledgeGraphQuery 的*节点数据* (dict) 转换为统一的 dict 格式
    """
    try:
        node_type = node_data.get("node_type")
        title, url, snippet, text = None, None, None, None

        if node_type == "Course":
            name = node_data.get("name", "")
            title = f"{entity_code}: {name}"
            url = node_data.get("url")
            snippet = node_data.get("overview") or node_data.get("description", "")
            text = f"Course Info: {title}. Overview: {snippet}"
        
        elif node_type == "Major":
            name = node_data.get("title", "")
            title = f"{entity_code}: {name}"
            url = node_data.get("url") # 假设 Major 节点有 URL
            snippet = node_data.get("description") or node_data.get("structure_summary", "")
            text = f"Major Info: {title}. Description: {snippet}"
        
        else:
            # 暂不支持其他实体类型作为主要结果
            return None

        return {
            "_text": text,
            "metadata": node_data, # 保留原始 metadata
            "url": url,
            "title": f"{title}", # (KG)
            "snippet": snippet,
            "original_score": 1.0, # KG 实体匹配默认为满分
            "source_type": "knowledge_graph"
        }
    except Exception as e:
        print(f"Error standardizing KG doc: {e}")
        return None

# --- 6. 辅助函数 (提取与重排) ---

def _extract_entities(query: str) -> List[str]:
    """从查询中提取课程/专业代码"""
    if not query:
        return []
    matches = ENTITY_REGEX.findall(query)
    # 返回大写的、唯一的实体
    return list(set([m.upper() for m in matches]))

def _run_rerank(query: str, docs: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    """
    使用 CrossEncoder 对合并后的文档进行重排
    """
    if not _RERANKER_MODEL:
        print("[WARN] Reranker model not loaded, returning original order.")
        return docs[:top_k]

    if not docs:
        return []

    # Reranker 需要的是 (query, passage) 对
    # 我们使用 'snippet'，因为它更简洁
    pairs = [(query, d.get("snippet") or d.get("_text")) for d in docs]
    
    print(f"Reranking {len(pairs)} document pairs...")
    start_time = time.time()
    
    try:
        # 1. 计算分数
        scores = _RERANKER_MODEL.predict(pairs, show_progress_bar=False)
        
        # 2. 将分数附加到原始文档
        for doc, score in zip(docs, scores):
            doc["rerank_score"] = float(score)
            
        # 3. 按重排分数降序排序
        sorted_docs = sorted(docs, key=lambda x: x["rerank_score"], reverse=True)
        
        # 4. (关键) 过滤掉分数太低的结果
        # (bge-reranker 的分数范围很大, 负分是完全不相关)
        filtered_docs = [
            d for d in sorted_docs 
            if d["rerank_score"] > MIN_RERANK_SCORE
        ]
        
        end_time = time.time()
        print(f"[OK] Reranking finished in {end_time - start_time:.2f}s. Filtered {len(sorted_docs)} -> {len(filtered_docs)} docs.")
        
        # 5. 返回重排后的 top_k 个结果
        return filtered_docs[:top_k]
    
    except Exception as e:
        print(f"[WARN] Reranking failed: {e}. Returning original order.")
        return docs[:top_k]


# --- 7. 主入口函数 ---

def parallel_search_and_rerank(query: str, top_k: int = 8) -> List[Dict[str, Any]]:
    """
    [核心函数] (同步版本)
    1. 调用 Vector Search (语义)
    2. 调用 Knowledge Graph (实体)
    3. 标准化、合并、去重
    4. 使用 Reranker 重新排序
    5. 返回 Top-K 结果 (以 retrieve.py 期望的格式)
    """
    print(f"\n--- Starting Hybrid Search for query: '{query}' ---")
    
    # 我们多检索一些，给重排器留足选择空间
    initial_k = max(top_k * INITIAL_K_MULTIPLIER, 15)
    
    standardized_docs = []
    seen = set() # 用于去重

    # --- 1. 语义检索 (Vector Search) ---
    if _SEARCHER:
        try:
            # 1a. 调用 search
            vs_response = _SEARCHER.search(query, top_k=initial_k)
            vs_results = vs_response.results
            print(f"Found {len(vs_results)} vector results.")

            # 1b. 标准化
            for doc in vs_results:
                s_doc = _standardize_vector_doc(doc)
                if not s_doc:
                    continue
                
                # 去重 (基于 URL 或 Title)
                doc_id = s_doc.get('url') or s_doc.get('title')
                if doc_id and doc_id not in seen:
                    standardized_docs.append(s_doc)
                    seen.add(doc_id)
        except Exception as e:
            print(f"[WARN] Vector Search failed: {e}")
            
    # --- 2. 实体检索 (Knowledge Graph) ---
    if _KG_QUERY:
        try:
            # 2a. 提取实体
            entities = _extract_entities(query)
            if entities:
                print(f"Found entities in query: {entities}")
                
                # 2b. 查询 KG
                for entity in entities:
                    node_data = _KG_QUERY.get_course_info(entity)
                    if not node_data:
                        node_data = _KG_QUERY.get_major_info(entity)
                    
                    if node_data:
                        # 2c. 标准化
                        s_doc = _standardize_kg_doc(node_data, entity)
                        if not s_doc:
                            continue
                        
                        # 去重
                        doc_id = s_doc.get('url') or s_doc.get('title')
                        if doc_id and doc_id not in seen:
                            standardized_docs.append(s_doc)
                            seen.add(doc_id)
                        else:
                            print(f" (KG result '{doc_id}' already found by vector search, skipping) ")
        except Exception as e:
            print(f"[WARN] Knowledge Graph Search failed: {e}")

    print(f"Total {len(standardized_docs)} unique documents merged.")

    # --- 3. 重排 ---
    reranked_docs = _run_rerank(query, standardized_docs, top_k)
    
    # --- 4. 最终格式化 (以匹配 retrieve.py 的需求) ---
    final_docs = []
    for doc in reranked_docs:
        # 我们将所有标准化字段塞回 _metadata, 
        # 并将 snippet 作为 _text
        final_docs.append({
            "_text": doc["snippet"], # 使用标准化的 snippet 作为 _text
            "_metadata": {
                "title": doc["title"],
                "url": doc["url"],
                "snippet": doc["snippet"],
                "source_type": doc["source_type"],
                "original_score": doc.get("original_score"),
                "rerank_score": doc.get("rerank_score"),
                
                # 保留原始 metadata, 以防 _doc_to_source 需要
                "original_metadata": doc.get("metadata") 
            },
            "_score": doc.get("rerank_score", 0) # 使用 rerank_score 作为主分数
        })

    print(f"--- Hybrid Search finished, returning {len(final_docs)} docs ---")
    return final_docs


# --- 8. (可选) 本地测试 ---
def main_test():
    """
    运行此文件以测试: 
    `python RAG_database/parallel_search_and_rerank.py`
    """
    
    print("\n" + "="*80)
    print("RUNNING HYBRID SEARCH TEST 1: Semantic Query")
    print("="*80)
    test_query_1 = "What AI courses are available for postgraduate?"
    results_1 = parallel_search_and_rerank(test_query_1, top_k=5)
    
    for i, doc in enumerate(results_1, 1):
        meta = doc.get("_metadata", {})
        print(f"\n{i}. {meta.get('title')} (Score: {doc.get('_score'):.4f})")
        print(f"   Source: {meta.get('source_type')}")
        print(f"   Snippet: {meta.get('snippet', 'N/A')[:150]}...")
        
    print("\n" + "="*80)
    print("RUNNING HYBRID SEARCH TEST 2: Entity Query")
    print("="*80)
    test_query_2 = "Tell me about COMP3900"
    results_2 = parallel_search_and_rerank(test_query_2, top_k=5)

    for i, doc in enumerate(results_2, 1):
        meta = doc.get("_metadata", {})
        print(f"\n{i}. {meta.get('title')} (Score: {doc.get('_score'):.4f})")
        print(f"   Source: {meta.get('source_type')}")
        print(f"   Snippet: {meta.get('snippet', 'N/A')[:150]}...")

    print("\n" + "="*80)
    print("RUNNING HYBRID SEARCH TEST 3: Hybrid (Semantic + Entity)")
    print("="*80)
    test_query_3 = "What are the prerequisites for COMP9417 machine learning?"
    results_3 = parallel_search_and_rerank(test_query_3, top_k=5)

    for i, doc in enumerate(results_3, 1):
        meta = doc.get("_metadata", {})
        print(f"\n{i}. {meta.get('title')} (Score: {doc.get('_score'):.4f})")
        print(f"   Source: {meta.get('source_type')}")
        print(f"   Snippet: {meta.get('snippet', 'N/A')[:150]}...")


if __name__ == "__main__":
    # (注意: 第一次运行此文件时，会需要几秒钟来加载所有模型)
    main_test()