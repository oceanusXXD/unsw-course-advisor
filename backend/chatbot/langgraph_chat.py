# backend/chatbot/langgraph_chat.py
import traceback
from typing import Dict, Any, Optional, List
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END  # type: ignore
from . import rag_chain_qwen as rag

class ChatState(TypedDict):
    query: str
    retrieved: Optional[List[dict]]
    answer: Optional[str]
    sources_brief: Optional[List[dict]]
    history: Optional[List[Dict[str, str]]]  # 新增多轮历史

# ---------------- 节点 ----------------
def node_retrieve(state: ChatState) -> Dict[str, Any]:
    """检索节点"""
    query = state["query"]
    retrieved_docs = rag.retrieve(query, top_k=rag.TOP_K)
    return {"retrieved": retrieved_docs}

def node_generate(state: ChatState, **kwargs) -> Dict[str, Any]:
    """生成答案节点，带历史上下文"""
    try:
        query = state["query"]
        history = state.get("history") or []
        # 拼接历史上下文
        context = "\n".join(f"User: {h['user']}\nBot: {h['bot']}" for h in history)
        prompt = f"{context}\nUser: {query}\nBot:"

        result = rag.answer_with_rag(prompt, stream=False, **kwargs)
        if isinstance(result, (tuple, list)) and len(result) >= 2:
            answer, docs = result[0], result[1]
        else:
            answer = str(result)
            docs = []

        # 更新 history
        new_history = history + [{"user": query, "bot": answer}]
        return {"answer": answer, "retrieved": docs, "history": new_history}

    except Exception:
        traceback.print_exc()
        raise

def node_finalize(state: ChatState) -> Dict[str, Any]:
    """整理输出来源信息"""
    docs = state.get("retrieved") or []
    sources_brief = [
        {"course_code": d.get("course_code"), "source": d.get("source_file") or d.get("source")}
        for d in docs
    ]
    return {"sources_brief": sources_brief}

# ---------------- 构建图 ----------------
graph = StateGraph(ChatState)
graph.add_node("retrieve", node_retrieve)
graph.add_node("generate", node_generate)
graph.add_node("finalize", node_finalize)
graph.set_entry_point("retrieve")
graph.add_edge("retrieve", "generate")
graph.add_edge("generate", "finalize")
graph.add_edge("finalize", END)

rag_graph = graph.compile()

# ---------------- 入口函数 ----------------
def run_chat(query: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    initial_state: ChatState = {
        "query": query,
        "retrieved": None,
        "answer": None,
        "sources_brief": None,
        "history": history or []
    }
    return rag_graph.invoke(initial_state)
