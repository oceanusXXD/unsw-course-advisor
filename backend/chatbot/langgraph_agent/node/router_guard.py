# backend/chatbot/langgraph_agent/node/router_guard.py

from typing import Dict, Any, Optional, List
import re
import json

# 导入强类型定义和核心功能
from ..state import ChatState
from ..schemas import StudentInfo, Memory, RouterDecision, PendingFileGeneration, PendingPluginInstall
from ..core import ENABLE_VERBOSE_LOGGING, is_file_generation_request,  is_planning_query
from ..tools import get_tools
import time

PROPOSAL_CONF_THRESH = 0.9
PROPOSAL_COOLDOWN_SEC = 120

def _now() -> float:
    return time.time()

def _on_cooldown(state: ChatState) -> bool:
    last_ts = float(state.get("last_proposal_ts") or 0.0)
    return (_now() - last_ts) < PROPOSAL_COOLDOWN_SEC


# =================================================================
# 辅助函数 (所有业务规则函数都集中在这里)
# =================================================================

def _confirm_yes(q: str) -> bool:
    q = (q or "").strip().lower()
    # 先排除否定
    if any(neg in q for neg in ["不要","不需要","不用","先不要","先别","别","算了","取消","no","nope","不是","不对","不对吧","不必"]):
        return False
    # 仅接受明确确认
    yes_patterns = ["确认生成","开始生成","生成吧","可以生成","确认", "好的", "是的", "可以", "ok", "yes"]
    return any(p in q for p in yes_patterns)


def _confirm_no(q: str) -> bool:
    q = (q or "").strip().lower()
    cancel_kws = ["不需要","不要","不用","先不要","先别","别","算了","取消","no","nope","不是","不对","不对吧","不必"]
    return any(kw in q for kw in cancel_kws) or q == "n"


def _wants_plugin_install(q: str) -> bool:
    q = (q or "").lower()
    return ("安装" in q and "插件" in q) or ("install" in q and "plugin" in q)


def _extract_codes(text: str) -> List[str]:
    if not isinstance(text, str): 
        return []
    return sorted(list(set(re.findall(r"\b[A-Z]{4}\d{4}\b", text.upper()))))


def _is_scheduling_intent(q: str) -> bool:
    q = (q or "").lower()
    keys = ["安排","时间","课表","t1","t2","t3","term","三门","两门","每学期","uoc","学分","冲突","时间冲突"]
    return any(k in q for k in keys)


def _is_course_query(query: str) -> bool:
    """
    判断是否是纯粹的课程查询问题（应该走 RAG）
    
    特征：
    - 包含课程代码（如 COMP6713）
    - 包含查询关键词（如"为什么不能选"、"难吗"）
    - 不是规划类问题
    """
    course_code_pattern = r'[A-Z]{4}\d{4}'
    query_lower = query.lower()
    
    # 课程查询关键词
    course_query_keywords = [
        "为什么不能选", "能不能选", "可以选", "怎么选",
        "先修", "prerequisite", "前置", "要求", 
        "难", "容易", "怎么样", "好不好",
        "这门课", "那门课", "overview", "讲什么", "学什么",
        "课程内容", "课程介绍", "课程描述"
    ]
    
    has_course_code = bool(re.search(r'\b[A-Z]{4}\d{4}\b', query.upper()))
    has_query_keyword = any(kw in query_lower for kw in course_query_keywords)
    
    return has_course_code and has_query_keyword


def _is_planning_question(query: str) -> bool:
    """
    判断是否是规划类问题（应该走 general_chat）
    
    特征：
    - 包含规划关键词（如"该选什么"、"帮我规划"）
    - 或使用 core.is_planning_query() 判断
    """
    query_lower = query.lower()
    
    planning_keywords = [
        "该选什么", "应该选", "推荐", "规划", "帮我选", 
        "下学期", "这学期", "next term", "安排", "课表",
        "选几门", "选多少", "一起选"
    ]
    
    return any(kw in query_lower for kw in planning_keywords) or is_planning_query(query)


# =================================================================
# 统一的守卫节点主函数
# =================================================================

def node_router_guard(state: ChatState) -> Dict[str, Any]:
    query = state.get("query", "")
    pending_file_generation: Optional[PendingFileGeneration] = state.get("pending_file_generation")
    pending_plugin_install: Optional[PendingPluginInstall] = state.get("pending_plugin_install")
    planner_decision: Optional[RouterDecision] = state.get("planner_decision")
    file_generation_declined = bool(state.get("file_generation_declined"))

    if ENABLE_VERBOSE_LOGGING:
        print("\n" + "=" * 60)
        print("【Router Guard 节点】启动")
        print(f"   - Query: '{query}'")
        print(f"   - Pending File: {pending_file_generation}")
        print(f"   - Pending Plugin: {pending_plugin_install}")
        print(f"   - Planner's Suggestion: {planner_decision.get('route') if planner_decision else 'None'}")
        print("=" * 60 + "\n")

    # =================================================================
    # 1. 待处理任务响应（最高优先级）
    # =================================================================
    
    if pending_file_generation:
        if (_is_scheduling_intent(query) or _is_planning_question(query)):
            if ENABLE_VERBOSE_LOGGING: 
                print("   [Guard] 规划/排课意图，清空 pending，转 general_chat")
            return {
                "route": "general_chat",
                "answer": "明白，不用生成文件。我先基于你的偏好为 T1/T2 做课程安排。",
                "pending_file_generation": {},
            }
        
        if _confirm_no(query):
            if ENABLE_VERBOSE_LOGGING: 
                print("   [Guard] 规则命中: 用户取消文件生成。")
            return {
                "route": "general_chat",
                "answer": "明白，不用生成文件。我先基于你已修课程帮你规划下一学期。",
                "pending_file_generation": {},
            }
        
        if _confirm_yes(query):
            if ENABLE_VERBOSE_LOGGING: 
                print("   [Guard] 规则命中: 用户确认文件生成。")
            courses = pending_file_generation.get("courses", [])
            return {
                "route": "call_tool", 
                "tool_name": "generate_selection", 
                "tool_args": {"courses": courses}, 
                "pending_file_generation": None
            }

    if pending_plugin_install:
        if _confirm_no(query):
            if ENABLE_VERBOSE_LOGGING: 
                print("   [Guard] 规则命中: 用户取消插件安装。")
            return {
                "route": "finish", 
                "pending_plugin_install": None, 
                "answer": "已取消安装插件。"
            }
        
        if _confirm_yes(query):
            if ENABLE_VERBOSE_LOGGING: 
                print("   [Guard] 规则命中: 用户确认插件安装。")
            return {
                "route": "call_tool", 
                "tool_name": "plugin_install", 
                "tool_args": {}, 
                "pending_plugin_install": None
            }

    # =================================================================
    # 2. 显式请求（兜底保留）
    # =================================================================
    
    if is_file_generation_request(query):
        if ENABLE_VERBOSE_LOGGING: 
            print("   [Guard] 规则命中: 新的文件生成请求。")
        codes = _extract_codes(query)
        ask = f"我可以为你生成包含 {', '.join(codes) if codes else '你提到的课程'} 的选课文件。请问是否确认？"
        return {
            "route": "finish", 
            "answer": ask, 
            "pending_file_generation": {"courses": codes}
        }

    if _wants_plugin_install(query):
        if ENABLE_VERBOSE_LOGGING: 
            print("   [Guard] 规则命中: 新的插件安装请求。")
        ask = "我可以为你安装选课插件，以便后续一键选课。是否确认？"
        return {
            "route": "finish", 
            "answer": ask, 
            "pending_plugin_install": {"requested": True}
        }

    # =================================================================
    # 3. LLM Planner 的 proposal/autostart 处理
    # =================================================================
    
    if planner_decision and planner_decision.get("route") == "call_tool":
        tool_info = planner_decision.get("tool_info") or {}
        if tool_info.get("tool_name") == "generate_selection":
            args = tool_info.get("tool_args") or {}
            courses = args.get("courses") or []
            ask_message = args.get("ask_message") or f"我可以为你生成包含 {', '.join(courses) if courses else '你提到的课程'} 的选课文件。是否确认？"
            confidence = float(args.get("confidence") or planner_decision.get("confidence") or 1.0)
            autostart = bool(args.get("autostart"))
            proposal = bool(args.get("proposal"))

            # 规划/咨询类问句：不接受早提案，优先走规划
            if proposal and _is_planning_question(query) and not state.get("pending_file_generation"):
                if ENABLE_VERBOSE_LOGGING: 
                    print("   [Guard] 规划问句：忽略生成文件提案，转 general_chat")
                return {"route": "general_chat"}

            # autostart 只有在"显式提出生成文件"时才允许
            if autostart and not is_file_generation_request(query):
                if ENABLE_VERBOSE_LOGGING: 
                    print("   [Guard] 拦截 autostart：用户未显式提出生成文件")
                return {"route": "general_chat"}

            # 其余保持
            if autostart and confidence >= PROPOSAL_CONF_THRESH and not _on_cooldown(state):
                return {
                    "route": "call_tool", 
                    "tool_name": "generate_selection", 
                    "tool_args": {"courses": courses}, 
                    "pending_file_generation": None
                }

            if proposal and not _on_cooldown(state):
                return {
                    "route": "finish", 
                    "answer": ask_message, 
                    "pending_file_generation": {"courses": courses}, 
                    "last_proposal_ts": _now()
                }

    # =================================================================
    # 4. 条件化 RAG 开放策略（核心逻辑）
    # =================================================================
    
    # 检测问题类型
    is_course_query_question = _is_course_query(query)
    is_planning = _is_planning_question(query)
    
    if ENABLE_VERBOSE_LOGGING:
        print(f"   [Guard] 问题类型分析:")
        print(f"      - 课程查询问题: {is_course_query_question}")
        print(f"      - 规划类问题: {is_planning}")
    
    # 策略 1: 纯粹的课程查询 -> 允许 RAG
    if is_course_query_question and not is_planning:
        if ENABLE_VERBOSE_LOGGING:
            print(f"   [Guard] 检测到课程查询问题（非规划），允许 RAG")
        
        # 如果 LLM 也判断是 RAG，直接放行
        llm_route = planner_decision.get("route") if planner_decision else "general_chat"
        if llm_route == "retrieve_rag":
            return {"route": "retrieve_rag"}
        else:
            # LLM 没选 RAG，但我们认为应该 RAG，强制改为 RAG
            if ENABLE_VERBOSE_LOGGING:
                print(f"   [Guard] LLM 决策是 {llm_route}，但强制改为 RAG")
            return {"route": "retrieve_rag"}
    
    # 策略 2: 规划类问题 + LLM 选择了 RAG -> 拦截，改为 general_chat
    llm_route = planner_decision.get("route") if planner_decision else "general_chat"
    
    if llm_route == "retrieve_rag":
        if is_planning:
            # 规划类问题 -> 拦截 RAG
            if ENABLE_VERBOSE_LOGGING:
                print("   [Guard] V1 补丁: 规划类问题，RAG -> general_chat")
            return {"route": "general_chat"}
        else:
            # 非规划类问题 -> 允许 RAG
            if ENABLE_VERBOSE_LOGGING:
                print("   [Guard] 非规划类问题，允许 RAG")
            # 继续走后面的逻辑，不拦截

    # =================================================================
    # 5. 工具调用验证
    # =================================================================
    
    if llm_route == "call_tool":
        tool_info = planner_decision.get("tool_info")
        tool_name = tool_info.get("tool_name") if tool_info else None
        callable_tool_names = {t.name for t in get_tools()}
        
        if tool_name and tool_name in callable_tool_names:
            return {
                "route": "call_tool", 
                "tool_name": tool_name, 
                "tool_args": tool_info.get("tool_args", {}) if tool_info else {}
            }
        else:
            if ENABLE_VERBOSE_LOGGING: 
                print(f"     - 修正: LLM 尝试调用未知工具 '{tool_name}'，兜底到 general_chat。")
            return {"route": "general_chat"}

    # =================================================================
    # 6. 兜底逻辑
    # =================================================================
    
    if ENABLE_VERBOSE_LOGGING: 
        print(f"   [Guard] 兜底：LLM 决策 '{llm_route}' 被路由到 general_chat。")
    
    return {"route": "general_chat"}