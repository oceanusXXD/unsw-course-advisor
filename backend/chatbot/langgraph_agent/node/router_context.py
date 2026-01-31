# backend/chatbot/langgraph_agent/node/router_context.py

import json
from datetime import datetime
from typing import Dict, Any, List

# 导入强类型定义
from ..schemas import StudentInfo, Memory, SSEEvent, RouterTrail
from ..state import ChatState

# 导入核心功能和工具
from ..core import ENABLE_VERBOSE_LOGGING, build_history_str
from ..tools import get_tools, ROUTER_ONLY_SCHEMA


def _available_tools_summary() -> Dict[str, Any]:
    """获取可用工具的摘要信息"""
    router_functions = []
    for t in ROUTER_ONLY_SCHEMA:
        fn = t.get("function", {}) or {}
        router_functions.append({"name": fn.get("name"), "description": fn.get("description")})

    callable_tools = []
    for tool in get_tools():
        callable_tools.append({"name": tool.name, "description": getattr(tool, "description", "")})

    return {
        "router_functions": router_functions,
        "callable_tools": callable_tools,
    }


def _student_info_summary(si: StudentInfo) -> Dict[str, Any]:
    """从强类型的 StudentInfo 创建摘要"""
    completed_courses = si.get("completed_courses", [])
    all_major_courses = si.get("all_major_courses", [])
    
    return {
        "major_code": si.get("major_code", ""),
        "year": si.get("year"),
        "completed_count": len(completed_courses),
        "all_major_courses_count": len(all_major_courses),  # [OK] 新增
        "wam": si.get("wam"),
        "has_all_major_courses": bool(all_major_courses),  # [OK] 修复
        "target_term": si.get("target_term", ""),
        "current_uoc": si.get("current_uoc"),
        "degree_level": si.get("degree_level", "PG"),
    }


def node_router_context(state: ChatState) -> Dict[str, Any]:
    """
    [LangGraph 节点] - 构造路由上下文
    
    此节点收集所有相关信息（历史、记忆、学生状态等），
    为后续的路由决策节点提供一个全面的"快照"。
    """
    print(f"[Search] [node_router_context] 进入时:")
    print(f"   - pending_file_generation = {state.get('pending_file_generation')}")
    print(f"   - pending_plugin_install = {state.get('pending_plugin_install')}")
    
    # 1. 从强类型 ChatState 安全地获取数据
    query = state.get("query", "")
    messages = state.get("messages", [])
    memory: Memory = state.get("memory", {"long_term_summary": "", "recent_conversations": []})
    student_info: StudentInfo = state.get("student_info", {"major_code": "", "completed_courses": [], "all_major_courses": []})
    pending_file_generation = state.get("pending_file_generation")
    pending_plugin_install = state.get("pending_plugin_install")
    turn_id = state.get("turn_id", "")
    router_trail: List[RouterTrail] = state.get("router_trail", [])
    
    # [OK] 新增：调试 memory 内容
    if ENABLE_VERBOSE_LOGGING:
        print(f"\n[Router Context Debug]")
        print(f"  - memory.long_term_summary length: {len(memory.get('long_term_summary', ''))}")
        print(f"  - memory.long_term_summary preview: {memory.get('long_term_summary', '')[:200]}...")
        print(f"  - student_info.all_major_courses count: {len(student_info.get('all_major_courses', []))}")
        print(f"  - pending_file from state: {pending_file_generation}")
        print(f"  - pending_plugin from state: {pending_plugin_install}")
        print()
    
    # 2. 构建历史记录预览
    hist = build_history_str(messages, max_turns=5) or ""
    MAX_HIST = 1200
    hist_out = hist[:MAX_HIST] + ("..." if len(hist) > MAX_HIST else "")

    # 3. 获取工具摘要
    tools_summary = _available_tools_summary()

    # 4. 创建上下文快照
    snapshot = {
        "turn_id": turn_id,
        "query": query,
        "history_preview": hist_out,
        "memory_stats": {
            "long_term_len": len(memory.get("long_term_summary", "")),
            "recent_count": len(memory.get("recent_conversations", [])),
            # [OK] 新增：long_term_summary 预览（用于调试）
            "long_term_preview": memory.get("long_term_summary", "")[:300]
        },
        "student_info_summary": _student_info_summary(student_info),
        "pending": {
            "file": bool(pending_file_generation),
            "plugin": bool(pending_plugin_install),
        },
        "available_tools": {
            "router_functions": [f["name"] for f in tools_summary["router_functions"]],
            "callable_tools": [t["name"] for t in tools_summary["callable_tools"]],
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    if ENABLE_VERBOSE_LOGGING:
        print("\n" + "="*30 + " Router Context Snapshot " + "="*30)
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        print("="*85 + "\n")

    # 5. 创建 SSE 事件
    sse_event: SSEEvent = {
        "event": "status",
        "data": {
            "message": "Router context snapshot created.",
            "node": "router_context",
            "snapshot": snapshot,
        }
    }
    
    # 6. 创建 RouterTrail 条目
    trail_entry: RouterTrail = {
        "node": "router_context",
        "timestamp": datetime.utcnow().timestamp(),
        "metadata": {
            "action": "Context Aggregation",
            "query_length": len(query),
            "message_count": len(messages),
            # [OK] 新增：记录关键状态
            "has_long_term_summary": bool(memory.get("long_term_summary")),
            "has_all_major_courses": bool(student_info.get("all_major_courses"))
        }
    }
    
    # 7. 返回要更新到 ChatState 的字段
    print(f"[Search] [node_router_context] 返回时:")
    print(f"   - pending_file_generation = {pending_file_generation}")
    print(f"   - pending_plugin_install = {pending_plugin_install}")
    
    return {
        "context_snapshot": snapshot,
        "router_trail": router_trail + [trail_entry], 
        "sse_events": [sse_event],
        # [OK] 显式保留 pending 状态
        "pending_file_generation": pending_file_generation,
        "pending_plugin_install": pending_plugin_install,
        # [OK] 新增：显式传递 memory 和 student_info（确保不丢失）
        "memory": memory,
        "student_info": student_info,
    }