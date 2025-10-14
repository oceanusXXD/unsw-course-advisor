# ./node/retrieve.py
import traceback
from typing import Dict, Any
from core import TOP_K, ENABLE_VERBOSE_LOGGING, RESPONSE_TEMPLATES
from chatbot.langgraph_agent import rag_chain_qwen as rag
def node_retrieve(state: Dict[str, Any]) -> Dict[str, Any]:
    """执行 RAG 检索"""
    try:
        query = state.get("query", "")
        docs = rag.retrieve(query, top_k=TOP_K) or []
        
        if ENABLE_VERBOSE_LOGGING:
            print(f"📚 RETRIEVE: Found {len(docs)} documents")
        
        if not docs:
            no_docs_msg = {"role": "system", "content": RESPONSE_TEMPLATES["fallback_no_rag_docs"]}
            return {"retrieved": [], "messages": [no_docs_msg]}
        
        return {"retrieved": docs}
        
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"⚠️  RETRIEVE ERROR: {e}")
            traceback.print_exc()
        return {"retrieved": [], "answer": RESPONSE_TEMPLATES["error_rag"]}
