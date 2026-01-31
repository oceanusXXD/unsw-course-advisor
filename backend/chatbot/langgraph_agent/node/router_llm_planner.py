# backend/chatbot/langgraph_agent/node/router_llm_planner.py

import json
import asyncio  # [OK] 新增
from datetime import datetime
from typing import Dict, Any, List, Optional, cast

# 导入强类型定义
from ..schemas import (
    StudentInfo, SSEEvent, RouterDecision, RouterTrail, ToolCall,
    Memory, get_default_memory, get_default_student_info
)
from ..state import ChatState

# 导入核心功能和工具
from ..core import (
    ROUTER_MODEL, ENABLE_VERBOSE_LOGGING, 
    call_qwen,  # [OK] 保留（给其他地方用）
    call_qwen_httpx,  # [OK] 新增异步版本
    _messages_to_dicts, parse_tool_arguments, build_history_str
)
from ..tools import get_tools, ROUTER_ONLY_SCHEMA


def _tools_desc_str() -> str:
    """生成可用工具的描述字符串"""
    lines = []
    for t in ROUTER_ONLY_SCHEMA:
        f = t.get("function", {})
        lines.append(f"- {f.get('name')}: {f.get('description')}")
    for tool in get_tools():
        lines.append(f"- {tool.name} (通过 'call_tool' 调用): {getattr(tool, 'description', '')}")
    return "\n".join(lines)


def _map_function_to_route(function_name: Optional[str]) -> str:
    """将 LLM 调用的函数名映射到 ChatState 的 route 字段"""
    if function_name in ("retrieve_rag", "call_tool", "general_chat"):
        return function_name
    return "general_chat"


async def node_router_llm_planner(state: ChatState) -> Dict[str, Any]:  # [OK] async def
    """
    [路由节点] 使用 LLM 做智能路由决策
    - 分析用户查询、历史对话、学生档案
    - 决定下一步操作：RAG 检索 / 工具调用 / 通用对话
    """
    # 1) 取 state
    query = state.get("query", "")
    messages = state.get("messages", [])
    student_info: StudentInfo = state.get("student_info", get_default_student_info())
    memory: Memory = state.get("memory", get_default_memory())
    pending_file_generation = state.get("pending_file_generation")
    pending_plugin_install = state.get("pending_plugin_install")
    turn_id = state.get("turn_id", "")
    router_trail: List[RouterTrail] = state.get("router_trail", [])
    
    # [OK] 使用正确的字段名 long_term_summary
    profile_context = memory.get("long_term_summary", "")
    if not profile_context:
        profile_context_str = "(无学生档案。这可能是新用户，或用户未提交档案。)"
    else:
        profile_context_str = profile_context
        
    # 2. 来自当前请求的 student_info 摘要
    current_student_info_summary = {
        "major_code": student_info.get("major_code"),
        "completed_courses": student_info.get("completed_courses"),
        "wam": student_info.get("wam"),
        "goals": student_info.get("goals"),
        "degree_level": student_info.get("degree_level")
    }
    student_info_str = json.dumps(
        {k: v for k, v in current_student_info_summary.items() if v}, 
        ensure_ascii=False
    )
    
    if ENABLE_VERBOSE_LOGGING:
        print(f"\n{'='*80}")
        print(f"[DEBUG Router Planner] 关键变量检查:")
        print(f"  - student_info type: {type(student_info)}")
        print(f"  - student_info keys: {list(student_info.keys()) if isinstance(student_info, dict) else 'N/A'}")
        print(f"  - all_major_courses: {student_info.get('all_major_courses', [])}")
        print(f"  - all_major_courses length: {len(student_info.get('all_major_courses', []))}")
        print(f"  - current_enable_choose_courses: {student_info.get('current_enable_choose_courses', [])}")
        print(f"  - profile_context_str length: {len(profile_context_str)}")
        print(f"  - profile_context_str 前 500 字符:")
        print(f"{profile_context_str[:500]}")
        print(f"{'='*80}\n")

    # 2) 历史与上一轮助手消息
    dict_messages = _messages_to_dicts(messages)
    last_assistant_message = ""
    if dict_messages:
        end = len(dict_messages) - 1
        if dict_messages[end].get("role") == "user":
            end -= 1
        for i in range(end, -1, -1):
            m = dict_messages[i]
            if m.get("role") == "assistant":
                content = m.get("content")
                last_assistant_message = "" if content is None else str(content)
                break
    history_str = build_history_str(messages, max_turns=4)
    
    # [OK] 更严格的判断逻辑
    has_all_courses = len(student_info.get("all_major_courses", [])) > 0
    
    # [OK] 从文本中提取数字来判断（更可靠）
    has_all_courses_in_text = False
    if "【专业课程全集】" in profile_context_str:
        import re
        match = re.search(r'【专业课程全集】\s*\n\s*共\s*(\d+)\s*门', profile_context_str)
        if match:
            course_count = int(match.group(1))
            has_all_courses_in_text = course_count > 0
            if ENABLE_VERBOSE_LOGGING:
                print(f"[DEBUG] 从文本中提取到专业课程数: {course_count}")
    
    # [OK] 综合判断
    has_all_courses_final = has_all_courses or has_all_courses_in_text
    
    has_enrollable_courses = (
        "【当前可选课程】" in profile_context_str or
        has_all_courses_final
    )
    
    if ENABLE_VERBOSE_LOGGING:
        print(f"[DEBUG] has_all_courses (from data): {has_all_courses}")
        print(f"[DEBUG] has_all_courses_in_text: {has_all_courses_in_text}")
        print(f"[DEBUG] has_all_courses_final: {has_all_courses_final}")
        print(f"[DEBUG] has_enrollable_courses: {has_enrollable_courses}\n")
    
    # 3) Prompt
    prompt = f"""你是一个顶级智能路由助手。分析用户最新查询并结合所有上下文决定下一步操作。

【学生档案 (来自硬规则/记忆)】
{profile_context_str}

【档案状态】
[OK] 是否已获取专业课程信息: {"是" if has_all_courses_final else "否"}
   {f"-> 专业共 {len(student_info.get('all_major_courses', []))} 门课程" if has_all_courses else "-> 硬规则未运行，需调用工具获取"}
[OK] 是否包含可选课程筛选结果: {"是" if has_enrollable_courses else "否"}

【当前学生信息 (来自本次请求)】
{student_info_str}

【上一轮助手的提问】
{last_assistant_message or "(无)"}

【最近对话片段】
{history_str}

【待处理任务】
- 待处理文件生成任务: {json.dumps(pending_file_generation, ensure_ascii=False) if pending_file_generation else "(无)"}
- 待处理插件安装任务: {json.dumps(pending_plugin_install, ensure_ascii=False) if pending_plugin_install else "(无)"}

【用户最新查询】
"{query}"

【决策规则 (严格执行)】

1. **规划/咨询类问句** (例如 "我该选什么课", "帮我规划", "下学期选什么"):
   
   a) 如果【档案状态】显示"是否已获取专业课程信息: 是"
      -> **必须选择 `general_chat`**
      -> 理由: 硬规则已运行，专业课程信息已存在，直接使用基础模型回答即可
   
   b) 如果【档案状态】显示"是否已获取专业课程信息: 否"
      -> 检查【当前学生信息】是否包含 `major_code` 和 `target_term`
      -> 如果有，调用 `call_tool` -> `filter_compiled_courses`
      -> 如果没有，选择 `general_chat` 引导用户提供信息

2. **信息检索 (RAG)**：
   - 仅当问题是关于课程的*通用*信息（如 "COMP1511 难吗？"、"这门课讲什么"）时
   - 使用 `retrieve_rag`

3. **回应待处理任务**：
   - 如果用户在回应【上一轮助手的提问】或【待处理任务】
   - 优先处理待处理任务

4. **工具调用规范**：
   - `filter_compiled_courses`: 仅在规划类问句 + 无专业课程信息 + 有 major_code/target_term 时调用
   - `generate_selection`: 仅在用户明确提出"生成文件/导出/一键"时才提议

5. **输出格式**：
   - 你的回答**必须是工具调用（tool_calls）**，不要输出自然语言

【可用操作/工具】
{_tools_desc_str()}

---
现在请做出你的决策。记住：如果专业课程信息已存在，规划类问题必须选择 general_chat！
"""

    if ENABLE_VERBOSE_LOGGING:
        print("\n" + "="*30 + " LLM Router Planner " + "="*30)
        print(f"   - Turn ID: {turn_id}")
        print(f"   - Has All Courses (data): {has_all_courses}")
        print(f"   - Has All Courses (text): {has_all_courses_in_text}")
        print(f"   - Has All Courses (final): {has_all_courses_final}")
        print(f"   - Has Enrollable Courses: {has_enrollable_courses}")
        print(f"   - Last Assistant Msg: '{last_assistant_message[:50]}...'")
        print(f"   - Pending File: {pending_file_generation}")
        print(f"   - Profile Context Length: {len(profile_context_str)} chars")
        print(f"   - Profile Context Preview:\n{profile_context_str[:300]}...")
        print("="*85 + "\n")
    
    # 4) [OK] 调用异步 LLM
    final_llm_messages = _messages_to_dicts([
        {"role": "system", "content": prompt},
        {"role": "user", "content": query}
    ])

    planner_decision: Optional[RouterDecision] = None
    llm_raw_response: Dict[str, Any] = {}
    error_message: Optional[str] = None
    route: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Dict[str, Any] = {}
    
    try:
        resp = await call_qwen_httpx(  # [OK] await call_qwen_httpx
            final_llm_messages, 
            model=ROUTER_MODEL, 
            temperature=0.0, 
            stream=False,
            tools=ROUTER_ONLY_SCHEMA, 
            tool_choice="auto", 
            purpose="router_planner_native",
        )
        llm_raw_response = resp
        if ENABLE_VERBOSE_LOGGING:
            print("[router_llm_planner] raw response:", json.dumps(resp, ensure_ascii=False)[:1200])

        if isinstance(resp, dict) and resp.get("tool_calls"):
            tc = resp["tool_calls"][0]
            fn = tc.get("function", {})
            fn_name = fn.get("name")
            fn_args = parse_tool_arguments(fn.get("arguments"))
            raw_route = _map_function_to_route(fn_name)

            reason = fn_args.get("reasoning", "LLM planner decision")
            confidence = fn_args.get("confidence", 1.0)

            if raw_route == "call_tool":
                tool_name = fn_args.get("tool_name")
                raw_tool_args = fn_args.get("tool_args", {})

                # 归一化为 dict
                parsed_tool_args: Dict[str, Any] = {}
                if isinstance(raw_tool_args, dict):
                    parsed_tool_args = raw_tool_args
                elif isinstance(raw_tool_args, str):
                    try:
                        tmp = json.loads(raw_tool_args)
                        if isinstance(tmp, dict):
                            parsed_tool_args = tmp
                    except Exception:
                        parsed_tool_args = {}
                tool_args = parsed_tool_args

                if tool_name:
                    route = "call_tool"
                    planner_decision = {
                        "route": route,
                        "reason": reason,
                        "confidence": float(confidence) if confidence is not None else 1.0,
                        "tool_info": {"tool_name": str(tool_name), "tool_args": tool_args}
                    }
                else:
                    error_message = "LLM chose 'call_tool' but did not provide 'tool_name'."
                    route = "general_chat"
                    planner_decision = {
                        "route": route,
                        "reason": error_message,
                        "confidence": 0.5
                    }

            elif raw_route in ("retrieve_rag", "general_chat"):
                route = raw_route
                tool_name = None
                tool_args = {}
                planner_decision = {
                    "route": route,
                    "reason": reason,
                    "confidence": float(confidence) if confidence is not None else 1.0
                }
            else:
                error_message = f"Unknown route '{raw_route}' mapped from '{fn_name}'."
                route = "general_chat"
                tool_name = None
                tool_args = {}
                planner_decision = {
                    "route": route,
                    "reason": error_message,
                    "confidence": 0.5
                }
        else:
            error_message = "LLM did not return a valid tool call."
    except Exception as e:
        error_message = f"LLM call failed: {str(e)}"
        llm_raw_response = {"error": error_message}
        if ENABLE_VERBOSE_LOGGING:
            print(f"[router_llm_planner] call_qwen error: {e}")

    # 5) 兜底
    if not planner_decision:
        route = "general_chat"
        tool_name = None
        tool_args = {}
        planner_decision = {
            "route": route,
            "reason": f"Fallback to general chat due to error: {error_message or 'No decision made'}",
            "confidence": 0.5
        }
        if ENABLE_VERBOSE_LOGGING:
            print(f"[WARN] [router_llm_planner] Fallback decision: {planner_decision['reason']}")
    
    if route != "call_tool":
        tool_name = None
        tool_args = {}
    
    # 6) 轨迹与事件
    trail_entry: RouterTrail = {
        "node": "router_llm_planner",
        "timestamp": datetime.utcnow().timestamp(),
        "decision": planner_decision,
        "metadata": {"model": ROUTER_MODEL, "error": error_message}
    }
    sse_event: SSEEvent = {
        "event": "status",
        "data": {
            "message": "LLM planner has made a decision.", 
            "node": "router_llm_planner", 
            "decision": planner_decision, 
            "error": error_message
        }
    }

    return {
        "planner_raw": llm_raw_response,
        "planner_decision": planner_decision,
        "route": route,
        "tool_name": tool_name,
        "tool_args": tool_args,
        "router_trail": router_trail + [trail_entry],
        "sse_events": [sse_event],
        "pending_file_generation": pending_file_generation,
        "pending_plugin_install": pending_plugin_install,
    }