# backend/chatbot/langgraph_agent/node/agentic_router.py

import json
import time
from typing import Dict, Any, List, Set, Optional, Literal

# 导入强类型定义
from ..schemas import (
    RetrievedDocument,
    RouterDecision,
    RouterTrail,
    SSEEvent,
    ToolCall,
    StudentInfo
)
from ..state import ChatState

# 导入核心功能
from ..core import (
    ROUTER_MODEL,
    ENABLE_VERBOSE_LOGGING,
    call_qwen,  # [OK] 保留（向后兼容）
    call_qwen_httpx,  # [OK] 新增异步版本
    create_docs_summary,
    parse_tool_arguments,
    _messages_to_dicts,
    build_history_str,
    is_planning_query,
    extract_course_codes,
)
from ..tools import get_agentic_router_schema, get_rag_tools

# 初始化工具架构
try:
    TOOLS_SCHEMA_FOR_ROUTER = get_agentic_router_schema()
    RAG_TOOLS_LIST = get_rag_tools()
    RAG_TOOL_NAMES: Set[str] = {t.name for t in RAG_TOOLS_LIST}
    if ENABLE_VERBOSE_LOGGING:
        print(f"[OK] [Agentic Router] 成功加载 {len(TOOLS_SCHEMA_FOR_ROUTER)} 个 Schema")
        print(f"[OK] [Agentic Router] 识别出 {len(RAG_TOOL_NAMES)} 个可执行 RAG 工具: {RAG_TOOL_NAMES}")
except ImportError as e:
    if ENABLE_VERBOSE_LOGGING:
        print(f"[ERR] [Agentic Router] 导入工具失败: {e}")
    TOOLS_SCHEMA_FOR_ROUTER = []
    RAG_TOOL_NAMES = set()

RouteLiteral = Literal["retrieve_rag", "call_tool", "needs_clarification", "general_chat", "finish"]
DecisionRouteLiteral = Literal["retrieve_rag", "call_tool", "needs_clarification", "general_chat", "finish"]

def _create_router_decision(
    route: DecisionRouteLiteral,
    reason: str,
    tool_name: Optional[str] = None,
    tool_args: Optional[Dict[str, Any]] = None,
    confidence: float = 1.0
) -> RouterDecision:
    decision: RouterDecision = {"route": route, "reason": reason}
    if confidence != 1.0:
        decision["confidence"] = confidence
    if tool_name and tool_args is not None:
        decision["tool_info"] = {"tool_name": tool_name, "tool_args": tool_args}
    return decision

def _create_router_trail_entry(
    node: str,
    decision: Optional[RouterDecision] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> RouterTrail:
    trail: RouterTrail = {"node": node, "timestamp": time.time()}
    if decision:
        trail["decision"] = decision
    if metadata:
        trail["metadata"] = metadata
    return trail

def _get_fallback_rag_call(query: str, reason: str = "unknown") -> Dict[str, Any]:
    if ENABLE_VERBOSE_LOGGING:
        print(f"[WARN] [RAG Agentic Router] 触发兜底 (原因: {reason})，路由到 'finish'")
    decision = _create_router_decision(route="finish", reason=f"兜底决策: {reason}", confidence=0.5)
    sse_event: SSEEvent = {"event": "status", "data": {"message": f"路由决策失败，使用兜底策略: {reason}", "node": "agentic_router"}}
    return {"route": "finish", "planner_decision": decision, "sse_events": [sse_event]}


async def node_agentic_router(state: ChatState) -> Dict[str, Any]:  # [OK] async def
    """
    [RAG Agentic Router] 智能路由决策节点
    
    - 分析当前检索状态和用户查询
    - 决定下一步操作：继续检索 / 调用工具 / 结束检索
    - 使用 LLM Function Calling 做出智能决策
    
    [WARN] 注意：这是异步节点，必须在 async/await 上下文中调用。
    """
    # 读取状态
    query = state.get("query", "") or ""
    retrieved_docs: List[RetrievedDocument] = state.get("retrieved_docs", []) or []
    retrieval_round = int(state.get("retrieval_round", 0))
    student_info: StudentInfo = state.get("student_info", {}) or {}
    messages = state.get("messages", []) or []
    router_trail: List[RouterTrail] = state.get("router_trail", []) or []

    MAX_ROUNDS = 3

    # 开始事件
    start_event: SSEEvent = {
        "event": "status",
        "data": {"message": f"正在进行智能路由决策（轮次 {retrieval_round + 1}/{MAX_ROUNDS}）...", "node": "agentic_router", "progress": 0.4}
    }
    sse_events: List[SSEEvent] = [start_event]

    if ENABLE_VERBOSE_LOGGING:
        print("\n" + "=" * 80)
        print(f"[LLM] [RAG Agentic Router] 启动 (轮次 {retrieval_round})")
        print(f"   Query: '{query}'")
        print(f"   已检索文档数 (原始): {len(retrieved_docs)}")
        print(f"   当前 messages 数量: {len(messages)}")
        print(f"   Student Info: major_code={student_info.get('major_code', 'N/A')}, year={student_info.get('year', 'N/A')}")
        print("=" * 80)

    # 轮次上限检查
    if retrieval_round >= MAX_ROUNDS:
        if ENABLE_VERBOSE_LOGGING:
            print(f"[STOP] [RAG Router] 已达最大轮次 ({retrieval_round}/{MAX_ROUNDS})，强制结束检索")
        decision = _create_router_decision(route="finish", reason=f"已达最大检索轮次 ({MAX_ROUNDS})，强制结束", confidence=1.0)
        trail_entry = _create_router_trail_entry(node="agentic_router", decision=decision, metadata={"round": retrieval_round, "forced": True})
        sse_events.append({"event": "status", "data": {"message": "达到最大检索轮次，结束检索", "node": "agentic_router"}})
        return {"route": "finish", "planner_decision": decision, "router_trail": router_trail + [trail_entry], "sse_events": sse_events}

    # 检索失败保护（避免仅重写未检索时触发）
    if retrieval_round >= 2 and len(retrieved_docs) == 0 and not state.get("rewritten_query"):
        if ENABLE_VERBOSE_LOGGING:
            print(f"[STOP] [RAG Router] 检索失败保护：轮次 {retrieval_round}，文档数仍为 0")
        decision = _create_router_decision(route="finish", reason="多轮检索后仍未获取到文档，可能检索系统故障", confidence=0.8)
        trail_entry = _create_router_trail_entry(node="agentic_router", decision=decision, metadata={"round": retrieval_round, "no_docs": True})
        sse_events.append({"event": "status", "data": {"message": "多轮检索未获得文档，结束检索", "node": "agentic_router"}})
        return {"route": "finish", "planner_decision": decision, "router_trail": router_trail + [trail_entry], "sse_events": sse_events}

    # 工具 Schema
    tools_schema = TOOLS_SCHEMA_FOR_ROUTER
    if not tools_schema:
        if ENABLE_VERBOSE_LOGGING:
            print("[ERR] [RAG Agentic Router] 工具 Schema 为空")
        return _get_fallback_rag_call(query, "no_tools_schema")

    if ENABLE_VERBOSE_LOGGING:
        tool_names = [t["function"]["name"] for t in tools_schema]
        print(f"\n[BUILD] [Tool Schema] 构建了 {len(tools_schema)} 个工具")
        print(f"   工具列表: {', '.join(tool_names)}")

    # 路由线索
    docs_summary_str = create_docs_summary(retrieved_docs, max_docs=5)
    planning = is_planning_query(query)
    codes = extract_course_codes(query)
    docs_count = len(retrieved_docs)
    history_summary = build_history_str(messages, max_turns=4)
    rewritten_hint = state.get("rewritten_query") or ""

    # 统计 rewrite 次数、最近一次是否 rewrite
    rewrite_count = 0
    last_was_rewrite = False
    if router_trail:
        for entry in router_trail:
            dec = (entry.get("decision") or {})
            ti = (dec.get("tool_info") or {})
            if ti.get("tool_name") == "rewrite_query":
                rewrite_count += 1
        last_dec = (router_trail[-1].get("decision") or {})
        last_ti = (last_dec.get("tool_info") or {})
        last_was_rewrite = last_ti.get("tool_name") == "rewrite_query"

    # 若已有 rewritten_query 且仍无文档 -> 直接检索（短路）
    if rewritten_hint and docs_count == 0:
        if ENABLE_VERBOSE_LOGGING:
            print("[Rewritten] [RAG Router] 检测到已存在 rewritten_query 且暂无文档，直接使用它进行检索")
        decision = _create_router_decision(route="retrieve_rag", reason="Use rewritten_query to perform retrieval", confidence=0.95)
        trail_entry = _create_router_trail_entry(node="agentic_router", decision=decision, metadata={"policy": "use_rewritten_query"})
        sse_events.append({"event": "status", "data": {"message": "使用重写后的查询执行检索", "node": "agentic_router"}})
        return {"route": "retrieve_rag", "planner_decision": decision, "router_trail": router_trail + [trail_entry], "sse_events": sse_events}

    signals_str = f"""
【路由线索】
- 规划意图: {planning}
- 识别到的课程代码: {', '.join(codes) if codes else '(无)'}
- 已检索文档数: {docs_count}
- 当前轮次: {retrieval_round + 1}/{MAX_ROUNDS}
- 学生专业已知: {bool(student_info.get('major_code'))}
- 已有重写查询: {rewritten_hint or '(无)'}
- 最近对话摘要:
{history_summary}
"""

    # 学生信息
    if student_info:
        info_parts = []
        if student_info.get("major_code"): info_parts.append(f"专业: {student_info['major_code']}")
        if student_info.get("year"): info_parts.append(f"年级: {student_info['year']}")
        if student_info.get("completed_courses"):
            courses = student_info["completed_courses"][:5]
            info_parts.append(f"已修课程: {', '.join(courses)}")
        student_info_str = "\n".join(info_parts) if info_parts else "(未提供)"
    else:
        student_info_str = "(未提供)"

    # Prompt
    prompt = f"""你是一个顶级的 RAG 检索决策专家。你的任务是分析当前状态，智能地选择下一步操作以最高效地收集回答用户问题所需的信息。

{signals_str}

【当前查询】
{query}

【学生信息】
{student_info_str}

【已检索文档摘要】（轮次 {retrieval_round + 1}/{MAX_ROUNDS}）
{docs_summary_str if docs_summary_str else "(尚未检索任何文档)"}

【决策优先级（重要）】
- 如果是课程规划类问题（planning=True），优先：
  1) filter_compiled_courses（需要综合学生背景做整体规划时）
  2) vector_retrieve（获取通用描述/课程概览）
  若信息缺失或表述宽泛 -> 使用 rewrite_query，并明确 missing_information。
- 已经进行过 rewrite_query 时，下一步必须 vector_retrieve 或 finish_retrieval，禁止连续两次 rewrite_query。
- knowledge_graph_search 仅用于查询具体关系（如"X 的先修是什么/学完 Y 解锁什么"），不要用它来完成课程规划。

【工具使用要求】
- rewrite_query 的参数必须包含：
  - original_query: 当前用户原始问题
  - history: 最近对话摘要
  - retrieved_docs_summary: 当前已检索文档摘要
  - missing_information: 明确说明缺什么

现在，请从可用工具中选择一个最合适的操作。
"""

    # 过滤历史
    safe_messages = _messages_to_dicts(messages)
    filtered_messages = []
    for msg in safe_messages:
        role = msg.get("role")
        if role == "tool": continue
        if role == "assistant" and msg.get("tool_calls"): continue
        if role in ("user", "assistant") and msg.get("content"):
            filtered_messages.append({"role": role, "content": msg["content"]})

    final_llm_messages = [{"role": "system", "content": prompt}]
    if filtered_messages:
        final_llm_messages.extend(filtered_messages[-4:])

    if ENABLE_VERBOSE_LOGGING:
        print(f"[Steps] [Message Filter] 原始 {len(safe_messages)} 条 -> 过滤后 {len(filtered_messages)} 条")

    # 禁用重复重写：已有文档 或 已重写过一次 -> 从工具列表移除 rewrite_query
    tools_for_llm = TOOLS_SCHEMA_FOR_ROUTER
    if docs_count >= 1 or rewrite_count >= 1:
        tools_for_llm = [t for t in TOOLS_SCHEMA_FOR_ROUTER if (t.get("function") or {}).get("name") != "rewrite_query"]
        if ENABLE_VERBOSE_LOGGING:
            print("[SKIP] [RAG Router] 已禁用 rewrite_query 供 LLM 选择（已有文档或已重写过）")

    # 首轮兜底：规划型且无文档 -> 先 rewrite（不消耗轮次）
    if retrieval_round == 0 and planning and docs_count == 0:
        tool_args = {
            "original_query": query,
            "history": history_summary,
            "retrieved_docs_summary": "(暂无文档)",
            "missing_information": "需要明确目标学期、每学期修读门数、偏好方向（如AI/安全/系统）、时间/学分限制等。"
        }
        decision = _create_router_decision(
            route="call_tool", reason="规划型问题首轮无文档，先重写查询以缩小范围",
            tool_name="rewrite_query", tool_args=tool_args, confidence=0.9
        )
        trail_entry = _create_router_trail_entry(node="agentic_router", decision=decision, metadata={"forced": "rewrite_query"})
        sse_events.append({"event": "status", "data": {"message": "先进行查询重写以明确方向", "node": "agentic_router"}})
        return {
            "route": "call_tool",
            "tool_name": "rewrite_query",
            "tool_args": tool_args,
            "planner_decision": decision,
            "router_trail": router_trail + [trail_entry],
            # [ERR] 不再在 rewrite 阶段递增轮次，避免 MAX_ROUNDS 被重写消耗
            "sse_events": sse_events
        }

    # [OK] 调用异步 LLM
    try:
        llm_response = await call_qwen_httpx(  # [OK] await call_qwen_httpx
            final_llm_messages,
            model=ROUTER_MODEL,
            temperature=0.5,
            stream=False,
            tools=tools_for_llm,
            tool_choice="auto",
            purpose="rag_agentic_routing",
        )
        if ENABLE_VERBOSE_LOGGING:
            print(f"\n[OK] [LLM Response] Function Calling 返回成功")
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"[ERR] [LLM Call] 调用失败: {e}")
        return _get_fallback_rag_call(query, f"llm_call_failed: {e}")

    # 解析 LLM 决策
    if isinstance(llm_response, dict) and llm_response.get("tool_calls"):
        tc = llm_response["tool_calls"][0]
        fn_info = tc.get("function", {}) or {}
        fn_name = fn_info.get("name")
        args = parse_tool_arguments(fn_info.get("arguments"))
        reasoning = args.get("reasoning", "(未提供推理)")

        if ENABLE_VERBOSE_LOGGING:
            print(f"[BUILD] [Decision] Function: {fn_name}")
            print(f"   Reasoning: {reasoning}")

        # 拦截重复重写：已有文档 / 已重写过 / 刚刚重写 -> 改为检索
        if fn_name == "rewrite_query" and (docs_count >= 1 or rewrite_count >= 1 or last_was_rewrite):
            if ENABLE_VERBOSE_LOGGING:
                print("[SKIP] [RAG Router] 拦截重复 rewrite，改为 retrieve_rag")
            decision = _create_router_decision(route="retrieve_rag", reason="Avoid repeated rewrite; proceed to retrieval", confidence=0.95)
            trail_entry = _create_router_trail_entry(node="agentic_router", decision=decision, metadata={"fix": "rewrite_to_retrieve"})
            sse_events.append({"event": "status", "data": {"message": "跳过重复重写，执行检索", "node": "agentic_router"}})
            return {"route": "retrieve_rag", "planner_decision": decision, "router_trail": router_trail + [trail_entry], "sse_events": sse_events}

        # 允许的一次 rewrite_query（不递增轮次）
        if fn_name == "rewrite_query":
            tool_args = {k: v for k, v in args.items() if k != "reasoning"}
            history_summary = build_history_str(messages, max_turns=4)
            if not tool_args.get("missing_information"):
                mi_parts = []
                if planning: mi_parts.append("目标学期（T1/T2/T3）、每学期修读门数、偏好方向（AI/安全/系统）、时间/学分限制")
                if not student_info.get("major_code"): mi_parts.append("学生专业/方向")
                if not student_info.get("completed_courses"): mi_parts.append("已修课程列表")
                if docs_count == 0: mi_parts.append("相关课程概览文档")
                tool_args["missing_information"] = "；".join(mi_parts) or "需要更明确的检索目标"
            tool_args["original_query"] = query
            tool_args["history"] = history_summary
            tool_args["retrieved_docs_summary"] = docs_summary_str

            decision = _create_router_decision(route="call_tool", reason=reasoning, tool_name=fn_name, tool_args=tool_args)
            trail_entry = _create_router_trail_entry(node="agentic_router", decision=decision)
            sse_events.append({"event": "status", "data": {"message": f"决策：重写查询以获取 '{reasoning[:30]}...'", "node": "agentic_router"}})
            return {
                "route": "call_tool",
                "tool_name": fn_name,
                "tool_args": tool_args,
                "planner_decision": decision,
                "router_trail": router_trail + [trail_entry],
                # [ERR] 重写不递增轮次
                "sse_events": sse_events
            }

        # 检索工具
        if fn_name in ["vector_retrieve", "continue_retrieve"]:
            decision = _create_router_decision(
                route="finish" if retrieval_round >= MAX_ROUNDS - 1 else "retrieve_rag",
                reason=reasoning,
                confidence=0.95 if retrieval_round < MAX_ROUNDS - 1 else 0.9
            )
            trail_entry = _create_router_trail_entry(node="agentic_router", decision=decision, metadata={"llm_function": fn_name, "round": retrieval_round})
            sse_events.append({"event": "status", "data": {"message": f"决定执行检索: {reasoning[:50]}...", "node": "agentic_router"}})
            return {"route": decision["route"], "rewritten_query": None, "planner_decision": decision, "router_trail": router_trail + [trail_entry], "sse_events": sse_events}

        # finish_retrieval
        if fn_name == "finish_retrieval":
            decision = _create_router_decision(route="finish", reason=reasoning, confidence=1.0)
            trail_entry = _create_router_trail_entry(node="agentic_router", decision=decision, metadata={"round": retrieval_round})
            sse_events.append({"event": "status", "data": {"message": "检索信息充足，准备生成答案", "node": "agentic_router"}})
            return {"route": "finish", "planner_decision": decision, "router_trail": router_trail + [trail_entry], "sse_events": sse_events}

        # 其他 RAG 工具（KG、Filter 等）
        if fn_name in RAG_TOOL_NAMES:
            tool_args = {k: v for k, v in args.items() if k != "reasoning"}
            decision = _create_router_decision(route="call_tool", reason=reasoning, tool_name=fn_name, tool_args=tool_args, confidence=0.95)
            trail_entry = _create_router_trail_entry(node="agentic_router", decision=decision, metadata={"round": retrieval_round})
            sse_events.append({"event": "tool", "data": {"tool_name": fn_name, "message": f"调用工具: {fn_name}", "node": "agentic_router"}})
            return {
                "route": "call_tool",
                "tool_name": fn_name,
                "tool_args": tool_args,
                "planner_decision": decision,
                "router_trail": router_trail + [trail_entry],
                "retrieval_round": retrieval_round + 1,  # [OK] 仅在执行实际 RAG 工具时递增轮次
                "sse_events": sse_events
            }

        # 未知函数
        if ENABLE_VERBOSE_LOGGING:
            print(f"[WARN] [RAG Router] 未知函数: {fn_name}")
        decision = _create_router_decision(route="finish", reason=f"未知函数 {fn_name}，无法继续", confidence=0.6)
        trail_entry = _create_router_trail_entry(node="agentic_router", decision=decision, metadata={"unknown_function": fn_name})
        return {"route": "finish", "planner_decision": decision, "router_trail": router_trail + [trail_entry], "sse_events": sse_events}

    # 没有 tool_calls 的兜底
    decision = _create_router_decision(
        route="finish",
        reason="LLM 返回文本内容而非工具调用" if (isinstance(llm_response, dict) and llm_response.get("content")) else "无法解析 LLM 响应",
        confidence=0.7 if (isinstance(llm_response, dict) and llm_response.get("content")) else 0.5
    )
    trail_entry = _create_router_trail_entry(node="agentic_router", decision=decision, metadata={"fallback": True})
    return {"route": "finish", "planner_decision": decision, "router_trail": router_trail + [trail_entry], "sse_events": sse_events}