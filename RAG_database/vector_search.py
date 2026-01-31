"""
Vector Search Interface for UNSW Course Data
[MODIFIED] Uses local SentenceTransformer for queries
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import chromadb
from chromadb.config import Settings
# from openai import OpenAI # No longer needed
# from dotenv import load_dotenv # No longer needed
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
            # self.model.encode returns a list of numpy arrays
            embedding_array = self.model.encode([query], show_progress_bar=False)
            # Get the first (and only) embedding and convert to list
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
        
        # Major code filter
        if "major_code" in filters:
            major_code = filters["major_code"]
            if isinstance(major_code, list):
                where_list.append({"major_code": {"$in": major_code}})
            else:
                where["major_code"] = major_code
        
        # Offering term filter (for courses)
        if "offering_term" in filters:
            # Note: This will match if the term is in the array
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
        return self.search(query, top_k, source_type="major")

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


def main():
    """Test vector search"""
    
    # load_dotenv() # No longer needed for API keys

    # --- [MODIFIED] Configuration ---
    # !!! IMPORTANT: This MUST match the model used in build_vector_store.py !!!
    LOCAL_MODEL_NAME = 'BAAI/bge-small-en-v1.5' # Or 'bge-small-en-v1.5'
    COLLECTION_NAME = "unsw_courses"
    # --- End Configuration ---
    
    # Paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent # Assuming script is in RAG_database
    persist_directory = project_root / "course_data" / "vector_store"
    
    print("="*80)
    print("Vector Search Test (Local Model Mode)")
    print("="*80 + "\n")
    
    if not persist_directory.exists():
        print(f"[ERR] Vector store not found: {persist_directory}")
        print("   Please run build_vector_store.py first")
        return
    
    print(f"Using local model: {LOCAL_MODEL_NAME}")
    
    # Initialize search
    searcher = VectorSearch(
        persist_directory=str(persist_directory),
        model_name=LOCAL_MODEL_NAME,
        collection_name=COLLECTION_NAME
    )
    
    # Test 1: Search courses
    print("="*80)
    print("TEST 1: Search for AI/Machine Learning courses")
    print("="*80)
    response = searcher.search_courses(
        query="artificial intelligence machine learning neural networks",
        top_k=5
    )
    
    for i, result in enumerate(response.results, 1):
        print(f"\n{i}. {result.metadata.get('course_code')} (Score: {result.score:.3f})")
        print(f"   {result.text[:150]}...")
    
    # Test 2: Search majors
    print("\n\n" + "="*80)
    print("TEST 2: Search for Computer Science majors")
    print("="*80)
    response = searcher.search_majors(
        query="computer science programming software",
        top_k=3
    )
    
    for i, result in enumerate(response.results, 1):
        print(f"\n{i}. {result.metadata.get('major_code')} - {result.metadata.get('major_title')}")
        print(f"   Score: {result.score:.3f}")
    
    # Test 3: Find similar courses
    print("\n\n" + "="*80)
    print("TEST 3: Find courses similar to COMP3900")
    print("="*80)
    response = searcher.find_similar_courses("COMP3900", top_k=5)
    
    for i, result in enumerate(response.results, 1):
        print(f"\n{i}. {result.metadata.get('course_code')} (Score: {result.score:.3f})")
        print(f"   {result.text[:100]}...")
    
    # Test 4: Search with filters
    print("\n\n" + "="*80)
    print("TEST 4: Search Level 2-3 courses about databases")
    print("="*80)
    response = searcher.search_courses(
        query="database management systems SQL",
        min_level=2,
        max_level=3,
        top_k=5
    )
    
    for i, result in enumerate(response.results, 1):
        print(f"\n{i}. {result.metadata.get('course_code')} Level {result.metadata.get('level')} (Score: {result.score:.3f})")
    
    # Statistics
    print("\n\n" + "="*80)
    print("Collection Statistics")
    print("="*80)
    stats = searcher.get_collection_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()