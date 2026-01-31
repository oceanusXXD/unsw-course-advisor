# backend/chatbot/langgraph_agent/node/tool_executor.py

import json
import time
import traceback
from typing import Dict, Any, List

from langchain_core.tools import BaseTool

# 导入强类型定义
from ..schemas import ToolMessage, SSEEvent
from ..state import ChatState

# 导入核心功能和工具
from ..core import ENABLE_VERBOSE_LOGGING
try:
    from ..tools import get_tools
    GENERAL_TOOLS_LIST: List[BaseTool] = get_tools()
    GENERAL_TOOLS_MAP: Dict[str, BaseTool] = {t.name: t for t in GENERAL_TOOLS_LIST}
    
    if ENABLE_VERBOSE_LOGGING:
        print(f"[OK] [General Tool Executor] 成功加载 {len(GENERAL_TOOLS_MAP)} 个通用工具: {list(GENERAL_TOOLS_MAP.keys())}")
except ImportError as e:
    if ENABLE_VERBOSE_LOGGING:
        print(f"[ERR] [General Tool Executor] 导入通用工具失败: {e}")
    GENERAL_TOOLS_MAP = {}


def node_tool_executor(state: ChatState) -> Dict[str, Any]:
    """
    [LangGraph 节点] - 通用工具执行器
    
    - 仅执行通用工具 (如文件生成, 插件安装)。
    - 执行后仅返回消息，不决定下一步路由。
    - 使用强类型数据契约。
    """
    # 1. 从强类型 ChatState 安全地获取数据
    tool_name = state.get("tool_name", "")
    tool_args = state.get("tool_args", {})
    # 如果 state 中没有 tool_call_id，生成一个
    tool_call_id = state.get("tool_call_id") or f"call_{int(time.time()*1000)}"

    if ENABLE_VERBOSE_LOGGING:
        print("\n" + "="*30 + " General Tool Executor " + "="*30)
        print(f"  Executing: {tool_name}")
        print(f"  Args: {json.dumps(tool_args, ensure_ascii=False)}")
        print("="*80 + "\n")

    # 2. 创建 SSE 事件通知前端
    start_event: SSEEvent = {
        "event": "tool",
        "data": {
            "tool_name": tool_name,
            "tool_args": tool_args,
            "status": "running",
            "message": f"正在执行通用工具: {tool_name}...",
        }
    }
    sse_events: List[SSEEvent] = [start_event]

    # 3. 检查工具是否存在
    if tool_name not in GENERAL_TOOLS_MAP:
        error_content = json.dumps({"status": "error", "error": f"未知的通用工具: {tool_name}"}, ensure_ascii=False)
        
        # 创建符合 ToolMessage 契约的错误消息
        tool_msg: ToolMessage = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": error_content,
            "error": f"Unknown general tool: {tool_name}"
        }
        
        # 创建 SSE 错误事件
        error_event: SSEEvent = {
            "event": "error",
            "data": { "message": f"工具执行失败: {tool_msg['error']}" }
        }
        sse_events.append(error_event)
        
        return {"messages": [tool_msg], "sse_events": sse_events}

    # 4. 执行工具
    try:
        tool_to_call = GENERAL_TOOLS_MAP[tool_name]
        result = tool_to_call.invoke(tool_args)
        
        # 将结果转换为字符串
        result_str = json.dumps(result, ensure_ascii=False) if isinstance(result, (dict, list)) else str(result)

        # 创建符合 ToolMessage 契约的成功消息
        tool_msg: ToolMessage = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result_str,
        }
        
        # 创建 SSE 成功事件
        complete_event: SSEEvent = {
            "event": "tool",
            "data": {
                "tool_name": tool_name,
                "status": "complete",
                "message": f"工具 {tool_name} 执行完成。",
                "result_preview": result_str[:200] + "..." if len(result_str) > 200 else result_str,
            }
        }
        sse_events.append(complete_event)

        # 仅返回消息，不设置 "route"
        return {
            "messages": [tool_msg],
            "sse_events": sse_events,
        }

    except Exception as e:
        # 5. 处理执行异常
        if ENABLE_VERBOSE_LOGGING:
            traceback.print_exc()
            
        error_content = json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)
        
        # 创建符合 ToolMessage 契约的异常消息
        tool_msg: ToolMessage = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": error_content,
            "error": str(e)
        }
        
        # 创建 SSE 异常事件
        exception_event: SSEEvent = {
            "event": "error",
            "data": { "message": f"工具 {tool_name} 执行异常: {str(e)}" }
        }
        sse_events.append(exception_event)

        return {"messages": [tool_msg], "sse_events": sse_events}