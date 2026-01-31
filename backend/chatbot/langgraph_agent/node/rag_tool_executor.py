# backend/chatbot/langgraph_agent/node/rag_tool_executor.py

import json
import time
import traceback
from typing import Dict, Any, List

from langchain_core.tools import BaseTool

# 导入强类型定义
from ..schemas import ToolMessage, SSEEvent, RetrievedDocument # 确保导入 RetrievedDocument
from ..state import ChatState

# 导入核心功能和工具
from ..core import ENABLE_VERBOSE_LOGGING
try:
    from ..tools import get_rag_tools
    RAG_TOOLS_LIST: List[BaseTool] = get_rag_tools()
    RAG_TOOLS_MAP: Dict[str, BaseTool] = {t.name: t for t in RAG_TOOLS_LIST}
    
    if ENABLE_VERBOSE_LOGGING:
        print(f"[OK] [RAG Tool Executor] 成功加载 {len(RAG_TOOLS_MAP)} 个 RAG 工具: {list(RAG_TOOLS_MAP.keys())}")
except ImportError as e:
    if ENABLE_VERBOSE_LOGGING:
        print(f"[ERR] [RAG Tool Executor] 导入 RAG 工具失败: {e}")
    RAG_TOOLS_MAP = {}


def _format_tool_result_as_doc(
    tool_name: str, 
    tool_args: dict, 
    result: dict,
    original_query: str
) -> List[RetrievedDocument]:
    """
    将 KG 或 Filter 的查询结果包装成一个或多个 RetrievedDocument。
    这是实现“统一知识提供者”模型的关键。
    """
    docs: List[RetrievedDocument] = []
    
    if not isinstance(result, dict):
        return []
    
    result_data = result.get("result", result)
    
    try:
        content_str = json.dumps(result_data, ensure_ascii=False, indent=2)
    except:
        content_str = str(result_data)

    doc_text = (
        f"针对用户问题 '{original_query}', "
        f"系统调用了工具 '{tool_name}' (参数: {json.dumps(tool_args, ensure_ascii=False)}).\n"
        f"工具返回了以下结构化信息:\n\n"
        f"```json\n"
        f"{content_str}\n"
        f"```"
    )

    doc: RetrievedDocument = {
        "source_id": f"tool_{tool_name}_{int(time.time()*1000)}",
        "title": f"工具执行结果: {tool_name}",
        "source_url": f"tool://{tool_name}",
        "_text": doc_text,
        "metadata": {
            "source_type": "tool_result",
            "tool_name": tool_name,
            "tool_args": tool_args,
        }
    }
    docs.append(doc)
    
    return docs


def node_rag_tool_executor(state: ChatState) -> Dict[str, Any]:
    """
    [LangGraph 节点] - RAG 专用工具执行器 (修复版)
    
    - 执行 RAG 工具 (KG, Filter)。
    - 返回标准的 ToolMessage 用于对话历史。
    -  新增：将工具结果包装成 RetrievedDocument 并更新到 state，打破信息孤岛。
    """
    # 1. 从 ChatState 获取所需信息
    tool_name = state.get("tool_name", "")
    tool_args = state.get("tool_args", {})
    tool_call_id = state.get("tool_call_id") or f"call_{int(time.time()*1000)}"
    # 获取旧文档列表，以便追加
    old_docs: List[RetrievedDocument] = state.get("retrieved_docs", [])
    # 获取原始查询，用于丰富文档内容
    original_query = state.get("query", "")

    if ENABLE_VERBOSE_LOGGING:
        print("\n" + "="*30 + " RAG Tool Executor " + "="*30)
        print(f"  Executing: {tool_name}")
        print(f"  Args: {json.dumps(tool_args, ensure_ascii=False)}")
        print("="*80 + "\n")

    # 2. SSE 事件 (不变)
    start_event: SSEEvent = { "event": "tool", "data": { "tool_name": tool_name, "status": "running" } }
    sse_events: List[SSEEvent] = [start_event]

    # 3. 检查工具是否存在 (不变)
    if tool_name not in RAG_TOOLS_MAP:
        error_content = json.dumps({"status": "error", "error": f"未知的 RAG 工具: {tool_name}"}, ensure_ascii=False)
        tool_msg: ToolMessage = {"role": "tool", "content": error_content, "tool_call_id": tool_call_id, "name": tool_name, "error": f"Unknown RAG tool: {tool_name}"}
        error_event: SSEEvent = {"event": "error", "data": {"message": f"工具执行失败: {tool_msg.get('error')}"}}
        sse_events.append(error_event)
        return {"messages": [tool_msg], "sse_events": sse_events}

    # 4. 执行工具
    try:
        tool_to_call = RAG_TOOLS_MAP[tool_name]
        result: Dict[str, Any] = tool_to_call.invoke(tool_args)
        
        result_str = json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result)

        # 创建 ToolMessage (不变)
        tool_msg: ToolMessage = {"role": "tool", "content": result_str, "tool_call_id": tool_call_id, "name": tool_name}
        if tool_name == "rewrite_query" and isinstance(result, dict) and result.get("status") == "ok":
            rewritten_data = result.get("result", {})
            rewritten_query = rewritten_data.get("rewritten_query")
            
            if rewritten_query:
                if ENABLE_VERBOSE_LOGGING:
                    print(f"  [START] [RAG Tool Executor] 捕获到重写的查询，将更新 state.rewritten_query。")
                
                # rewrite_query 不产出文档，只产出新查询和消息
                return {
                    "messages": [tool_msg],
                    "rewritten_query": rewritten_query, # <- 将新查询写入 state
                    "sse_events": sse_events,
                }
        new_docs: List[RetrievedDocument] = []
        # 只有当工具成功执行时，才将其结果转换为文档
        if isinstance(result, dict) and result.get("status") == "ok":
            new_docs = _format_tool_result_as_doc(tool_name, tool_args, result, original_query)
        
        # 合并新旧文档
        all_docs = old_docs + new_docs
        
        if ENABLE_VERBOSE_LOGGING and new_docs:
            print(f"  [OK] [RAG Tool Executor] 已将工具结果包装为 {len(new_docs)} 个新文档。")

        # 创建 SSE 成功事件 (不变)
        complete_event: SSEEvent = { "event": "tool", "data": { "tool_name": tool_name, "status": "complete", "result_preview": result_str[:200] } }
        sse_events.append(complete_event)

        if tool_name == "rewrite_query":
            if isinstance(result, dict) and result.get("status") == "ok":
                rewritten_data = result.get("result", {})
                rewritten_query = rewritten_data.get("rewritten_query")
                if rewritten_query:
                    if ENABLE_VERBOSE_LOGGING:
                        print(f"  [START] [RAG Tool Executor] 捕获到重写查询，更新 state.rewritten_query。")
                    # rewrite_query 只产出新查询，不产出文档
                    return {
                        "messages": [tool_msg],
                        "rewritten_query": rewritten_query, # <- 将新查询写入 state
                        "sse_events": sse_events,
                    }
            # 如果 rewrite_query 失败或未返回新查询，则走通用逻辑（即不更新 rewritten_query）
            return {"messages": [tool_msg], "sse_events": sse_events}

        # 分支 2: 如果是其他 RAG 工具 (KG, Filter)
        else:
            new_docs: List[RetrievedDocument] = []
            if isinstance(result, dict) and result.get("status") == "ok":
                new_docs = _format_tool_result_as_doc(tool_name, tool_args, result, original_query)
            
            all_docs = old_docs + new_docs
            
            if ENABLE_VERBOSE_LOGGING and new_docs:
                print(f"  [OK] [RAG Tool Executor] 已将 '{tool_name}' 的结果包装为 {len(new_docs)} 个新文档。")

            return {
                "messages": [tool_msg],
                "retrieved_docs": all_docs, # <- 更新文档列表
                "sse_events": sse_events,
            }
    except Exception as e:
        # 5. 异常处理 (不变)
        if ENABLE_VERBOSE_LOGGING: traceback.print_exc()
        error_content = json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)
        tool_msg: ToolMessage = {"role": "tool", "content": error_content, "tool_call_id": tool_call_id, "name": tool_name, "error": str(e)}
        exception_event: SSEEvent = {"event": "error", "data": {"message": f"工具 {tool_name} 执行异常: {str(e)}"}}
        sse_events.append(exception_event)
        # 即使异常，也只返回消息，不更新文档
        return {"messages": [tool_msg], "sse_events": sse_events}