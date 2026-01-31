# backend/chatbot/langgraph_agent/parallel_search_and_rerank.py
# [单例模式版本] 确保只初始化一次

import os
import traceback
import sys
import re
import time
import pickle
import asyncio
import threading  # 新增
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

# --- 1. 核心依赖 ---
import torch
import chromadb
import networkx as nx
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer, CrossEncoder

# --- 2. 路径计算 ---
SCRIPT_DIR = Path(__file__).parent 
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent 
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# 导入 KnowledgeGraphQuery
try:
    from .tools.knowledge_graph_query import KnowledgeGraphQuery
except ImportError:
    print("WARNING: Could not use relative import for KGQuery. Trying absolute.")
    from backend.chatbot.langgraph_agent.tools.knowledge_graph_query import KnowledgeGraphQuery

# --- 3. VectorSearch 类（保持不变）---

@dataclass
class SearchResult:
    """Search result item"""
    id: str
    text: str
    metadata: Dict[str, Any]
    distance: float
    score: float
    source_type: str

@dataclass
class SearchResponse:
    """Search response with multiple results"""
    query: str
    results: List[SearchResult]
    total_results: int
    filters_applied: Dict[str, Any]

class VectorSearch:
    """Vector search interface for UNSW courses"""
    
    def __init__(self,
                 persist_directory: str,
                 model_name: str = 'BAAI/bge-large-en-v1.5',
                 collection_name: str = "unsw_courses"):
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name
        self.model_name = model_name

        print(f"Loading local embedding model: {self.model_name}...")
        device_to_use = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Using device: {device_to_use}")
        self.model = SentenceTransformer(self.model_name, device=device_to_use)
        self.dimensions = self.model.get_sentence_embedding_dimension()
        print(f"[OK] Local model loaded. Dimensions: {self.dimensions}")
        
        self.chroma_client = chromadb.PersistentClient(
            path=str(persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )
        
        try:
            self.collection = self.chroma_client.get_collection(name=collection_name)
            print(f"[OK] Loaded collection '{collection_name}' with {self.collection.count()} documents\n")
        except Exception as e:
            raise RuntimeError(f"Failed to load collection '{collection_name}': {e}")

    def _get_query_embedding(self, query: str) -> List[float]:
        try:
            embedding_array = self.model.encode([query], show_progress_bar=False)
            return embedding_array[0].tolist()
        except Exception as e:
            print(f"Error getting local query embedding: {e}")
            raise

    def _build_where_filter(self, **filters) -> Optional[Dict[str, Any]]:
        where = {}
        where_list = []
        
        if "source_type" in filters:
            source_type = filters["source_type"]
            if isinstance(source_type, list):
                where_list.append({"source_type": {"$in": source_type}})
            else:
                where["source_type"] = source_type
        if "study_level" in filters:
            level_tag = filters["study_level"]
            if isinstance(level_tag, list):
                where_list.append({"study_level": {"$in": level_tag}})
            else:
                where["study_level"] = level_tag
        if "level" in filters:
            level = filters["level"]
            if isinstance(level, list):
                where_list.append({"level": {"$in": level}})
            else:
                where["level"] = level
        if "min_level" in filters:
            where_list.append({"level": {"$gte": filters["min_level"]}})
        if "max_level" in filters:
            where_list.append({"level": {"$lte": filters["max_level"]}})
        if "major_code" in filters:
            major_code = filters["major_code"]
            if isinstance(major_code, list):
                where_list.append({"major_code": {"$in": major_code}})
            else:
                where["major_code"] = major_code
        if "offering_term" in filters:
            where_list.append({"offering_terms": {"$contains": filters["offering_term"]}})
        
        if where and where_list:
            where_list.append(where)
            return {"$and": where_list}
        elif where_list:
            return {"$and": where_list} if len(where_list) > 1 else where_list[0]
        elif where:
            return where
        return None

    def search(self,
               query: str,
               top_k: int = 5,
               **filters) -> SearchResponse:
        query_embedding = self._get_query_embedding(query)
        where_filter = self._build_where_filter(**filters)
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        search_results = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                result = SearchResult(
                    id=results['ids'][0][i],
                    text=results['documents'][0][i],
                    metadata=results['metadatas'][0][i],
                    distance=results['distances'][0][i],
                    score=1.0 - results['distances'][0][i],
                    source_type=results['metadatas'][0][i].get('source_type', 'unknown')
                )
                search_results.append(result)
        
        return SearchResponse(
            query=query,
            results=search_results,
            total_results=len(search_results),
            filters_applied=filters
        )
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection"""
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "total_documents": count,
                "persist_directory": str(self.persist_directory)
            }
        except Exception as e:
            print(f"Error getting collection stats: {e}")
            return {}
    
    def get_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by its ID"""
        try:
            result = self.collection.get(ids=[doc_id], include=["documents", "metadatas"])
            if result['ids']:
                return {
                    "id": result['ids'][0],
                    "text": result['documents'][0],
                    "metadata": result['metadatas'][0]
                }
        except Exception as e:
            print(f"Error getting document by ID: {e}")
        return None


# --- 4. 单例服务类 ---

class HybridSearchService:
    """
    混合检索服务的封装类
    - 包含 Reranker、VectorSearch、KnowledgeGraph
    - 线程安全的单例模式
    """
    
    def __init__(self):
        # 路径和常量
        self.vector_store_path = PROJECT_ROOT / "course_data" / "vector_store"
        self.kg_path = PROJECT_ROOT / "course_data" / "knowledge_graph" / "course_kg.pkl"
        
        self.entity_regex = re.compile(r'\b([A-Z]{4}\d{4}|[A-Z]{4}[A-Z]{2,6})\b', re.IGNORECASE)
        self.initial_k_multiplier = 3
        self.min_rerank_score = -5.0
        
        # 组件（延迟初始化）
        self.reranker = None
        self.searcher = None
        self.kg_query = None
        
        # 初始化标志
        self._initialized = False
        self._init_lock = threading.Lock()
    
    def _initialize(self):
        """内部初始化方法（只执行一次）"""
        if self._initialized:
            return
        
        with self._init_lock:
            if self._initialized:
                return
            
            print("Initializing Hybrid Search Service...")
            
            # 1. Reranker
            print("Loading Reranker model (BAAI/bge-reranker-base)...")
            try:
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
                self.reranker = CrossEncoder(
                    'BAAI/bge-reranker-base',
                    max_length=512,
                    device=device
                )
                print(f"[OK] Reranker loaded on device: {device}")
            except Exception as e:
                print(f"[WARN] Failed to load Reranker: {e}")
                self.reranker = None
            
            # 2. VectorSearch
            print(f"Loading Vector Store from: {self.vector_store_path}")
            try:
                self.searcher = VectorSearch(
                    persist_directory=str(self.vector_store_path),
                    model_name='BAAI/bge-small-en-v1.5',
                    collection_name="unsw_courses"
                )
                print("[OK] VectorSearch initialized.")
            except Exception as e:
                print(f"[WARN] Failed to initialize VectorSearch: {e}")
                traceback.print_exc()
                self.searcher = None
            
            # 3. KnowledgeGraph
            print(f"Loading Knowledge Graph from: {self.kg_path}")
            try:
                self.kg_query = KnowledgeGraphQuery(graph_path=str(self.kg_path))
                print("[OK] KnowledgeGraphQuery initialized.")
            except Exception as e:
                print(f"[WARN] Failed to initialize KnowledgeGraph: {e}")
                traceback.print_exc()
                self.kg_query = None
            
            self._initialized = True
            print("--- Hybrid Search Service Ready ---")
    
    def ensure_initialized(self):
        """确保服务已初始化（懒加载）"""
        if not self._initialized:
            self._initialize()
    
    def _standardize_vector_doc(self, doc: SearchResult) -> Optional[Dict[str, Any]]:
        """标准化 VectorSearch 结果"""
        try:
            meta = doc.metadata or {}
            text = doc.text or ""
            
            title = (
                meta.get("course_name") or 
                meta.get("major_title") or 
                meta.get("course_code") or 
                meta.get("group_title") or 
                "Vector Result"
            )
            url = meta.get("url") or meta.get("source_url") or ""
            snippet = text if text and len(text.split()) >= 5 else meta.get("description", text)

            return {
                "_text": text,
                "metadata": meta,
                "url": url,
                "title": title,
                "snippet": snippet,
                "original_score": doc.score,
                "source_type": "vector_search"
            }
        except Exception as e:
            print(f"Error standardizing vector doc: {e}")
            return None
    
    def _standardize_kg_doc(self, node_data: Dict[str, Any], entity_code: str) -> Optional[Dict[str, Any]]:
        """标准化 KnowledgeGraph 结果"""
        try:
            node_type = node_data.get("node_type")
            
            if node_type == "Course":
                name = node_data.get("name", "")
                title = f"{entity_code}: {name}"
                url = node_data.get("url") or ""
                snippet = node_data.get("overview") or node_data.get("description", "")
                text = f"Course Info: {title}. Overview: {snippet}"
            
            elif node_type == "major_code":
                name = node_data.get("title", "")
                title = f"{entity_code}: {name}"
                url = node_data.get("url") or ""
                snippet = node_data.get("description") or node_data.get("structure_summary", "")
                text = f"Major Info: {title}. Description: {snippet}"
            
            else:
                return None

            return {
                "_text": text,
                "metadata": node_data,
                "url": url,
                "title": title,
                "snippet": snippet,
                "original_score": 1.0,
                "source_type": "knowledge_graph"
            }
        except Exception as e:
            print(f"Error standardizing KG doc: {e}")
            return None
    
    def _extract_entities(self, query: str) -> List[str]:
        """从查询中提取实体"""
        if not query:
            return []
        matches = self.entity_regex.findall(query)
        return list(set([m.upper() for m in matches]))
    
    def _run_rerank(self, query: str, docs: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        """重排序文档"""
        if not self.reranker:
            print("[WARN] Reranker not available, returning original order.")
            return docs[:top_k]
        
        if not docs:
            return []

        pairs = [(query, d.get("snippet") or d.get("_text")) for d in docs]
        print(f"Reranking {len(pairs)} document pairs...")
        start_time = time.time()
        
        try:
            scores = self.reranker.predict(pairs, show_progress_bar=False)
            
            for doc, score in zip(docs, scores):
                doc["rerank_score"] = float(score)
            
            sorted_docs = sorted(docs, key=lambda x: x["rerank_score"], reverse=True)
            filtered_docs = [d for d in sorted_docs if d["rerank_score"] > self.min_rerank_score]
            
            end_time = time.time()
            print(f"[OK] Reranking finished in {end_time - start_time:.2f}s. "
                  f"Filtered {len(sorted_docs)} -> {len(filtered_docs)} docs.")
            
            return filtered_docs[:top_k]
        
        except Exception as e:
            print(f"[WARN] Reranking failed: {e}. Returning original order.")
            return docs[:top_k]
    
    def search(self, query: str, top_k: int = 8) -> List[Dict[str, Any]]:
        """
        核心混合检索方法
        
        Returns:
            List[Dict]: 标准化的文档列表，格式：
                {
                    "_text": str,
                    "_metadata": dict,
                    "_score": float
                }
        """
        self.ensure_initialized()  # 懒加载
        
        print(f"\n--- Starting Hybrid Search for query: '{query}' ---")
        
        initial_k = max(top_k * self.initial_k_multiplier, 15)
        standardized_docs = []
        seen = set()

        # 1. Vector Search
        if self.searcher:
            try:
                vs_response = self.searcher.search(query, top_k=initial_k)
                vs_results = vs_response.results
                print(f"Found {len(vs_results)} vector results.")

                for doc in vs_results:
                    s_doc = self._standardize_vector_doc(doc)
                    if not s_doc:
                        continue
                    
                    doc_id = s_doc.get('url') or s_doc.get('title')
                    if doc_id and doc_id not in seen:
                        standardized_docs.append(s_doc)
                        seen.add(doc_id)
            except Exception as e:
                print(f"[WARN] Vector Search failed: {e}")
        
        # 2. Knowledge Graph
        if self.kg_query:
            try:
                entities = self._extract_entities(query)
                if entities:
                    print(f"Found entities in query: {entities}")
                    
                    for entity in entities:
                        node_data = self.kg_query.get_course_info(entity)
                        if not node_data:
                            node_data = self.kg_query.get_major_info(entity)
                        
                        if node_data:
                            s_doc = self._standardize_kg_doc(node_data, entity)
                            if not s_doc:
                                continue
                            
                            doc_id = s_doc.get('url') or s_doc.get('title')
                            if doc_id and doc_id not in seen:
                                standardized_docs.append(s_doc)
                                seen.add(doc_id)
            except Exception as e:
                print(f"[WARN] Knowledge Graph Search failed: {e}")

        print(f"Total {len(standardized_docs)} unique documents merged.")

        # 3. Rerank
        reranked_docs = self._run_rerank(query, standardized_docs, top_k)
        
        # 4. 格式化为标准输出
        final_docs = []
        for doc in reranked_docs:
            final_docs.append({
                "_text": doc["snippet"],
                "_metadata": {
                    "title": doc["title"],
                    "url": doc["url"],
                    "snippet": doc["snippet"],
                    "source_type": doc["source_type"],
                    "original_score": doc.get("original_score"),
                    "rerank_score": doc.get("rerank_score"),
                    "original_metadata": doc.get("metadata")
                },
                "_score": doc.get("rerank_score", 0)
            })

        print(f"--- Hybrid Search finished, returning {len(final_docs)} docs ---")
        return final_docs
    
    def get_stats(self) -> Optional[Dict[str, Any]]:
        """获取服务统计信息"""
        self.ensure_initialized()
        if not self.searcher:
            return None
        try:
            return self.searcher.get_collection_stats()
        except Exception as e:
            print(f"Error in get_stats: {e}")
            return None
    
    def get_doc_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取文档"""
        self.ensure_initialized()
        if not self.searcher:
            return None
        try:
            return self.searcher.get_by_id(doc_id)
        except Exception as e:
            print(f"Error in get_doc_by_id: {e}")
            return None


# --- 5. 全局单例实例 ---

_HYBRID_SERVICE: Optional[HybridSearchService] = None
_SERVICE_LOCK = threading.Lock()

def get_hybrid_search_service() -> HybridSearchService:
    """
    获取混合检索服务的单例实例
    
    线程安全，确保只初始化一次
    """
    global _HYBRID_SERVICE
    
    if _HYBRID_SERVICE is not None:
        return _HYBRID_SERVICE
    
    with _SERVICE_LOCK:
        if _HYBRID_SERVICE is not None:
            return _HYBRID_SERVICE
        
        _HYBRID_SERVICE = HybridSearchService()
        return _HYBRID_SERVICE


# --- 6. 向后兼容的函数接口 ---

def parallel_search_and_rerank(query: str, top_k: int = 8) -> List[Dict[str, Any]]:
    """
    [主入口函数] 混合检索 + 重排序
    
    这是对外暴露的接口，保持向后兼容
    """
    service = get_hybrid_search_service()
    return service.search(query, top_k)

def get_stats() -> Optional[Dict[str, Any]]:
    """获取统计信息（向后兼容）"""
    service = get_hybrid_search_service()
    return service.get_stats()

def get_doc_by_id(doc_id: str) -> Optional[Dict[str, Any]]:
    """根据 ID 获取文档（向后兼容）"""
    service = get_hybrid_search_service()
    return service.get_doc_by_id(doc_id)


# --- 7. 本地测试 ---

def main_test():
    """本地测试函数"""
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


if __name__ == "__main__":
    main_test()