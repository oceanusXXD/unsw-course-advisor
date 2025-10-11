# backend/chatbot/langgraph_integration.py
import traceback
import json
from typing import Dict, Any, Optional, List
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END # type: ignore
from . import rag_chain_qwen as rag

# --- 核心修改：使用 TypedDict 定义 State 的完整结构 ---
# 这让 LangGraph 知道如何累积和更新状态，而不是替换它。
# Optional 表示这个字段在流程的某些阶段可能不存在。
class ChatState(TypedDict):
    query: str
    retrieved: Optional[List[dict]]
    answer: Optional[str]
    sources_brief: Optional[List[dict]]

# --- 节点函数保持不变：只返回它们负责生成的数据 ---
def node_retrieve(state: ChatState) -> Dict[str, Any]:
    """节点1：根据 query 检索文档。"""
    print("--- Running Node: retrieve ---")
    query = state["query"] # 现在可以直接访问，因为 TypedDict 保证了它的存在
    retrieved_docs = rag.retrieve(query, top_k=rag.TOP_K)
    return {"retrieved": retrieved_docs}

def node_generate(state: ChatState, **kwargs) -> Dict[str, Any]:
    """节点2：生成答案。"""
    print("--- Running Node: generate ---")
    try:
        query = state["query"]
        # 注意：这里我们不再需要 _extract_query_from_state 函数，因为状态结构是固定的。

        api_key = kwargs.get("api_key", None)
        base_url = kwargs.get("base_url", None)
        top_k = kwargs.get("top_k", 4)
        
        # answer_with_rag 内部会自己做检索，所以我们甚至不需要传递 state["retrieved"]
        # 如果你的 answer_with_rag 可以接受已检索的文档以避免重复检索，那会是更好的优化。
        result = rag.answer_with_rag(query, stream=False, api_key=api_key, base_url=base_url, top_k=top_k)

        if isinstance(result, (tuple, list)) and len(result) >= 2:
            answer, docs = result[0], result[1]
        else:
            answer = str(result)
            docs = []

        # 返回生成的答案和本次生成所依据的文档
        return {"answer": answer, "retrieved": docs}

    except Exception:
        traceback.print_exc()
        raise

def node_finalize(state: ChatState) -> Dict[str, Any]:
    """节点3：整理最终输出的来源信息。"""
    print("--- Running Node: finalize ---")
    docs = state.get("retrieved") or []
    sources_brief = [
        {"course_code": d.get("course_code"), "source": d.get("source_file") or d.get("source")}
        for d in docs
    ]
    return {"sources_brief": sources_brief}

# --- 图的构建和编译保持不变 ---
graph = StateGraph(ChatState)

graph.add_node("retrieve", node_retrieve)
graph.add_node("generate", node_generate)
graph.add_node("finalize", node_finalize)

graph.set_entry_point("retrieve")
graph.add_edge("retrieve", "generate")
graph.add_edge("generate", "finalize")
graph.add_edge("finalize", END)

rag_graph = graph.compile()

# --- 入口函数也保持不变 ---
def run_chat(query: str) -> Dict[str, Any]:
    initial_state: ChatState = {
        "query": query,
        "retrieved": None,
        "answer": None,
        "sources_brief": None
    }
    return rag_graph.invoke(initial_state)