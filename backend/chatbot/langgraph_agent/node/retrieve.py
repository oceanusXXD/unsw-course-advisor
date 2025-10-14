# ./node/retrieve.py
import traceback
from typing import Dict, Any
from core import TOP_K, ENABLE_VERBOSE_LOGGING, RESPONSE_TEMPLATES

def node_retrieve(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        query = state.get("query", "")
        try:
            import rag_chain_qwen as rag
        except Exception:
            rag = None
        docs = []
        if rag:
            docs = rag.retrieve(query, top_k=TOP_K) or []
        if ENABLE_VERBOSE_LOGGING:
            print(f"📚 RETRIEVE: Found {len(docs)} documents")
        if not docs:
            return {"retrieved": [], "messages": [{"role": "system", "content": RESPONSE_TEMPLATES["fallback_no_rag_docs"]}]}
        return {"retrieved": docs}
    except Exception:
        traceback.print_exc()
        return {"retrieved": [], "answer": RESPONSE_TEMPLATES["error_rag"]}
