# unsw-course-advisor/backend/chatbot/langgraph_agent/rag.py 废弃
import os
import traceback
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import torch



@dataclass
class SearchResult:
    """Search result item"""
    id: str
    text: str
    metadata: Dict[str, Any]
    distance: float
    score: float  # Similarity score (1 - distance)
    source_type: str

@dataclass
class SearchResponse:
    """Search response with multiple results"""
    query: str
    results: List[SearchResult]
    total_results: int
    filters_applied: Dict[str, Any]

# --- [2] VectorSearch 核心类 (来自原始代码) ---

class VectorSearch:
    """Vector search interface for UNSW courses"""

    def __init__(self,
                 persist_directory: str,
                 model_name: str = 'BAAI/bge-large-en-v1.5',
                 collection_name: str = "unsw_courses"):
        """
        [MODIFIED] Initialize vector search with local SentenceTransformer
        
        Args:
            persist_directory: Chroma database directory
            model_name: Local embedding model name (must match builder)
            collection_name: Collection name
        """
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name
        self.model_name = model_name

        # Initialize local model
        print(f"Loading local embedding model: {self.model_name}...")
        device_to_use = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Using device: {device_to_use}")
        self.model = SentenceTransformer(self.model_name, device=device_to_use)
        self.dimensions = self.model.get_sentence_embedding_dimension()
        print(f"[OK] Local model loaded. Dimensions: {self.dimensions}")
        
        # Initialize Chroma client
        self.chroma_client = chromadb.PersistentClient(
            path=str(persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Load collection
        try:
            self.collection = self.chroma_client.get_collection(name=collection_name)
            print(f"[OK] Loaded collection '{collection_name}' with {self.collection.count()} documents\n")
        except Exception as e:
            raise RuntimeError(f"Failed to load collection '{collection_name}': {e}")

    def _get_query_embedding(self, query: str) -> List[float]:
        """[MODIFIED] Get embedding for query text using local model"""
        try:
            embedding_array = self.model.encode([query], show_progress_bar=False)
            return embedding_array[0].tolist()
        except Exception as e:
            print(f"Error getting local query embedding: {e}")
            raise

    def _build_where_filter(self, **filters) -> Optional[Dict[str, Any]]:
        """
        Build Chroma where filter from kwargs
        (This function is unchanged)
        """
        where = {}
        where_list = []
        
        # Source type filter
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
        # Level filters
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
        
        # major_code code filter
        if "major_code" in filters:
            major_code = filters["major_code"]
            if isinstance(major_code, list):
                where_list.append({"major_code": {"$in": major_code}})
            else:
                where["major_code"] = major_code
        
        # Offering term filter (for courses)
        if "offering_term" in filters:
            where_list.append({"offering_terms": {"$contains": filters["offering_term"]}})
        
        # Combine filters
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
        """
        Semantic search across all documents
        (This function is unchanged)
        """
        # Get query embedding
        query_embedding = self._get_query_embedding(query)
        
        # Build filter
        where_filter = self._build_where_filter(**filters)
        
        # Query Chroma
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        # Parse results
        search_results = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                result = SearchResult(
                    id=results['ids'][0][i],
                    text=results['documents'][0][i],
                    metadata=results['metadatas'][0][i],
                    distance=results['distances'][0][i],
                    score=1.0 - results['distances'][0][i],  # Convert distance to similarity
                    source_type=results['metadatas'][0][i].get('source_type', 'unknown')
                )
                search_results.append(result)
        
        return SearchResponse(
            query=query,
            results=search_results,
            total_results=len(search_results),
            filters_applied=filters
        )

    def search_courses(self,
                       query: str,
                       top_k: int = 5,
                       level: Optional[int] = None,
                       min_level: Optional[int] = None,
                       max_level: Optional[int] = None,
                       offering_term: Optional[str] = None) -> SearchResponse:
        """
        Search only courses
        (This function is unchanged)
        """
        filters = {"source_type": "course"}
        
        if level is not None:
            filters["level"] = level
        if min_level is not None:
            filters["min_level"] = min_level
        if max_level is not None:
            filters["max_level"] = max_level
        if offering_term:
            filters["offering_term"] = offering_term
        
        return self.search(query, top_k, **filters)

    def search_majors(self,
                      query: str,
                      top_k: int = 5) -> SearchResponse:
        """
        Search only majors/specialisations
        (This function is unchanged)
        """
        return self.search(query, top_k, source_type="major_code")

    def search_requirement_groups(self,
                                  query: str,
                                  major_code: Optional[str] = None,
                                  top_k: int = 5) -> SearchResponse:
        """
        Search requirement groups
        (This function is unchanged)
        """
        filters = {"source_type": "requirement_group"}
        if major_code:
            filters["major_code"] = major_code
        
        return self.search(query, top_k, **filters)

    def find_similar_courses(self,
                             course_code: str,
                             top_k: int = 5,
                             exclude_self: bool = True,
                             study_level: Optional[str] = None) -> SearchResponse:
        """
        [已修复] Find courses similar to a given course
        - 修复: 使用 $and 操作符来构建 where 过滤器，以兼容ChromaDB
        - 新增: 允许按 study_level (UG/PG) 筛选
        """
        try:
            # [!!] 修复：为ChromaDB构建一个 $and 过滤器 [!!]
            get_where_list = [
                {"course_code": course_code},
                {"source_type": "course"}
            ]
            
            if study_level:
                # e.g., "UG" or "PG"
                get_where_list.append({"study_level": study_level})
            
            # 最终的过滤器必须是单个字典
            get_where = {"$and": get_where_list}

            result = self.collection.get(
                where=get_where, # <-- [!!] 使用新的 $and 过滤器
                limit=1, # 只取第一个匹配项 (例如 UG 的)
                include=["documents", "metadatas"]
            )
            
            if not result['ids']:
                error_msg = f"Course {course_code}"
                if study_level:
                    error_msg += f" (Level: {study_level})"
                error_msg += " not found"
                
                return SearchResponse(
                    query=f"Similar to {course_code}",
                    results=[], total_results=0,
                    filters_applied={"error": error_msg}
                )
            
            # 使用找到的第一个课程的文本作为查询
            course_text = result['documents'][0]
            
            # Search for similar
            response = self.search_courses(
                query=course_text,
                top_k=top_k + (1 if exclude_self else 0)
            )
            
            # Filter out self if needed
            if exclude_self:
                # (这个逻辑是正确的，基于 course_code 排除)
                response.results = [r for r in response.results if r.metadata.get("course_code") != course_code][:top_k]
                response.total_results = len(response.results)
            
            response.query = f"Similar to {course_code}"
            return response
            
        except Exception as e:
            print(f"Error finding similar courses: {e}")
            return SearchResponse(
                query=f"Similar to {course_code}",
                results=[], total_results=0,
                filters_applied={"error": str(e)}
            )
            
    def get_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        try:
            result = self.collection.get(
                ids=[doc_id],
                include=["documents", "metadatas"]
            )
            
            if result['ids']:
                return {
                    "id": result['ids'][0],
                    "text": result['documents'][0],
                    "metadata": result['metadatas'][0]
                }
        except:
            pass
        
        return None

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        total = self.collection.count()
        
        return {
            "collection_name": self.collection_name,
            "total_documents": total,
            "persist_directory": str(self.persist_directory)
        }
vector_searcher: Optional[VectorSearch] = None

def retrieve(query: str, top_k: int = 5, **filters) -> Optional[List[Dict[str, Any]]]:
    """
    [NEW] Main retrieval function for the LangGraph agent.
    
    This function interfaces with the VectorSearch class and formats
    the output (List[Dict]) for consumption by the agent nodes.
    
    Args:
        query: The search query string.
        top_k: The number of results to return.
        **filters: Additional metadata filters (e.g., source_type="course").
        
    Returns:
        A list of dictionaries, each representing a retrieved document,
        or None if an error occurs.
    """
    if not vector_searcher:
        print("[WARN]  ERROR: vector_searcher is not initialized. Cannot retrieve.")
        return None
    
    try:
        # 1. 使用通用的 search 方法
        response: SearchResponse = vector_searcher.search(
            query=query,
            top_k=top_k,
            **filters
        )
        
        # 2. 将 List[SearchResult] 转换为 List[Dict]
        #    (Agent 节点期望的是字典列表)
        formatted_results = []
        for res in response.results:
            formatted_results.append({
                "_id": res.id,
                "_text": res.text,
                "_score": res.score,
                "_distance": res.distance,
                "_metadata": res.metadata,
                "source_type": res.source_type
            })
        
        return formatted_results
        
    except Exception as e:
        print(f"Error during RAG retrieval: {e}")
        traceback.print_exc()
        return None

# --- [5] [!!] 其他辅助函数 (可选) [!!] ---
# (这些函数返回完整的 SearchResponse 对象，可能对其他非 agent 任务有用)

def search_courses_full(query: str, top_k: int = 5, **kwargs) -> Optional[SearchResponse]:
    """Helper to search only courses, returns full SearchResponse"""
    if not vector_searcher: return None
    try:
        return vector_searcher.search_courses(query, top_k, **kwargs)
    except Exception as e:
        print(f"Error in search_courses_full: {e}")
        return None

def find_similar_courses_full(course_code: str, top_k: int = 5, **kwargs) -> Optional[SearchResponse]:
    """Helper to find similar courses, returns full SearchResponse"""
    if not vector_searcher: return None
    try:
        return vector_searcher.find_similar_courses(course_code, top_k, **kwargs)
    except Exception as e:
        print(f"Error in find_similar_courses_full: {e}")
        return None

def get_doc_by_id(doc_id: str) -> Optional[Dict[str, Any]]:
    """Helper to get a document by its ID"""
    if not vector_searcher: return None
    try:
        return vector_searcher.get_by_id(doc_id)
    except Exception as e:
        print(f"Error in get_doc_by_id: {e}")
        return None

def get_stats() -> Optional[Dict[str, Any]]:
    """Helper to get collection stats"""
    if not vector_searcher: return None
    try:
        return vector_searcher.get_collection_stats()
    except Exception as e:
        print(f"Error in get_stats: {e}")
        return None
    
def initialize_vector_search(
    persist_directory: str,
    model_name: str = 'BAAI/bge-small-en-v1.5',
    collection_name: str = "unsw_courses"
) -> bool:
    """
    初始化全局 vector_searcher
    
    Args:
        persist_directory: Chroma 数据库路径
        model_name: 嵌入模型名称
        collection_name: 集合名称
        
    Returns:
        是否初始化成功
    """
    global vector_searcher
    
    try:
        print(f"\n[BUILD] Initializing VectorSearch...")
        print(f"   Directory: {persist_directory}")
        print(f"   Model: {model_name}")
        print(f"   Collection: {collection_name}")
        
        vector_searcher = VectorSearch(
            persist_directory=persist_directory,
            model_name=model_name,
            collection_name=collection_name
        )
        
        print(f"[OK] VectorSearch initialized successfully!")
        return True
        
    except Exception as e:
        print(f"[ERR] Failed to initialize VectorSearch: {e}")
        traceback.print_exc()
        vector_searcher = None
        return False


def is_initialized() -> bool:
    """检查 vector_searcher 是否已初始化"""
    return vector_searcher is not None


def get_vector_searcher() -> Optional[VectorSearch]:
    """获取全局 vector_searcher 实例"""
    return vector_searcher