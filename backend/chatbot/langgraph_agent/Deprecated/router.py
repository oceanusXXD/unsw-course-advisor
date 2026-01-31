# node/router.py 废弃-兜底节点
import json
import re
from typing import Dict, Any, List, Optional, Callable
from abc import ABC, abstractmethod

from ..core import (
    ROUTER_MODEL,
    ENABLE_VERBOSE_LOGGING,
    call_qwen,
    build_history_str,
    is_file_generation_request,
    _messages_to_dicts,
    parse_tool_arguments
)
from ..tools import get_tools, ROUTER_ONLY_SCHEMA
from langchain_core.tools import BaseTool
# ==================== 上下文对象 ====================
class RouterContext:
    """封装 Router 所需的所有上下文信息"""
    def __init__(self, state: Dict[str, Any]):
        self.state = state
        self.query = state.get("query", "").strip()
        self.messages = state.get("messages", [])
        self.memory = state.get("memory", {}) or {}
        self.student_info = state.get("student_info", {}) or {}
        self.pending_file_generation = state.get("pending_file_generation")
        self.pending_plugin_install = state.get("pending_plugin_install")

    def log(self, message: str):
        """统一日志输出"""
        if ENABLE_VERBOSE_LOGGING:
            print(message)


# ==================== 处理器基类 ====================
class RouteHandler(ABC):
    """路由处理器基类（责任链模式）"""
    
    def __init__(self, next_handler: Optional['RouteHandler'] = None):
        self.next_handler = next_handler
    
    def handle(self, ctx: RouterContext) -> Optional[Dict[str, Any]]:
        """
        处理路由逻辑
        - 返回 Dict: 表示处理完成，返回路由结果
        - 返回 None: 表示不处理，交给下一个处理器
        """
        result = self._process(ctx)
        if result is not None:
            return result
        if self.next_handler:
            return self.next_handler.handle(ctx)
        return None
    
    @abstractmethod
    def _process(self, ctx: RouterContext) -> Optional[Dict[str, Any]]:
        """子类实现具体逻辑"""
        pass


# ==================== 具体处理器 ====================

class DeclineFileGenerationHandler(RouteHandler):
    """处理：明确拒绝生成选课文件"""
    
    def _process(self, ctx: RouterContext) -> Optional[Dict[str, Any]]:
        if _wants_to_decline_file_gen(ctx.query):
            ctx.log("[STOP] Router: 用户明确拒绝生成选课文件")
            return {
                "route": "general_chat",
                "file_generation_declined": True,
                "reasoning": "用户拒绝生成选课文件"
            }
        return None


class CoursePlanningHandler(RouteHandler):
    """处理：选课/规划请求 -> 强制进入 RAG"""
    
    def _process(self, ctx: RouterContext) -> Optional[Dict[str, Any]]:
        if _is_course_planning_request(ctx.query):
            ctx.log(" Router: 检测到选课/规划意图 -> 先进入 RAG/硬规则")
            return {
                "route": "retrieve_rag",
                "reasoning": "选课/规划请求：硬规则/检索优先"
            }
        return None


class FileGenerationRequestHandler(RouteHandler):
    """处理：生成选课文件请求（新请求，非确认）"""
    
    def _process(self, ctx: RouterContext) -> Optional[Dict[str, Any]]:
        # 必须是文件生成请求 且 不在 pending 状态
        if not is_file_generation_request(ctx.query):
            return None
        if ctx.pending_file_generation:  # 已有 pending，交给后续处理器处理
            return None
        
        # 优先硬规则筛选
        if _mentions_hard_rule_first(ctx.query) or _student_info_ready(ctx.student_info):
            ctx.log(" Router: 检测到硬规则优先 -> 路由到 RAG")
            return {"route": "retrieve_rag", "reasoning": "硬规则优先"}
        
        # 提取课程并返回确认文案
        rec = _extract_courses_with_llm(ctx.memory, ctx.query)
        codes = [
            it["course_code"]
            for it in (rec.get("selected") or [])
            if isinstance(it, dict) and it.get("course_code")
        ]
        codes_str = ", ".join(codes) if codes else "（未提供）"
        ask = (
            f"我可以为你生成选课文件（包含：{codes_str}）。\n"
            f"是否确认生成？\n"
            f"回复\"确认/安装/好的\"继续，或\"不要/取消\"放弃。"
        )
        ctx.log(f"[Folder] Router: 新请求 -> 待生成选课文件 pending -> {codes}")
        return {
            "route": "finish",
            "answer": ask,
            "pending_file_generation": {"courses": codes},
            "reasoning": "待确认：生成选课文件"
        }


class PluginInstallRequestHandler(RouteHandler):
    """处理：安装插件请求（新请求，非确认）"""
    
    def _process(self, ctx: RouterContext) -> Optional[Dict[str, Any]]:
        # 必须是插件安装请求 且 不在 pending 状态
        if not _wants_plugin_install(ctx.query):
            return None
        if ctx.pending_plugin_install:  # 已有 pending，交给后续处理器处理
            return None
        
        ask = (
            "我可以为你安装选课插件，以便后续一键导入选课文件并自动选课。\n"
            "是否确认现在安装？\n"
            "回复\"确认/安装/好的\"继续，或\"不要/取消\"放弃。"
        )
        ctx.log("[PLUGIN] Router: 新请求 -> 待安装插件 pending")
        return {
            "route": "finish",
            "answer": ask,
            "pending_plugin_install": {"requested": True},
            "reasoning": "待确认：安装插件"
        }


class PendingFileConfirmationHandler(RouteHandler):
    """处理：pending 文件生成的确认/取消"""
    
    def _process(self, ctx: RouterContext) -> Optional[Dict[str, Any]]:
        if not ctx.pending_file_generation:
            return None
        if _confirm_no(ctx.query) or _wants_to_decline_file_gen(ctx.query):
            ctx.log("[STOP] Router: 用户取消生成选课文件")
            return {
                "route": "general_chat",
                "file_generation_declined": True,
                "pending_file_generation": None,
                "reasoning": "用户取消生成选课文件"
            }
        # 确认
        if _confirm_yes(ctx.query):
            codes = ctx.pending_file_generation.get("courses") or []
            ctx.log(f"[OK] Router: 用户确认生成选课文件 -> {codes}")
            return {
                "route": "call_tool",
                "tool_name": "generate_selection",
                "tool_args": {"courses": codes},
                "pending_file_generation": None,
                "reasoning": "用户确认生成选课文件"
            }

        
        return None


class PendingPluginConfirmationHandler(RouteHandler):
    """处理：pending 插件安装的确认/取消"""
    
    def _process(self, ctx: RouterContext) -> Optional[Dict[str, Any]]:
        if not ctx.pending_plugin_install:
            return None
        # 取消
        if _confirm_no(ctx.query):
            ctx.log("[STOP] Router: 用户取消安装插件")
            return {
                "route": "general_chat",
                "pending_plugin_install": None,
                "reasoning": "用户取消安装插件"
            }
        # 确认
        if _confirm_yes(ctx.query):
            ctx.log("[OK] Router: 用户确认安装插件")
            return {
                "route": "call_tool",
                "tool_name": "plugin_install",
                "tool_args": {},
                "pending_plugin_install": None,
                "reasoning": "用户确认安装插件"
            }
        
        return None


class HistoryRecoveryHandler(RouteHandler):
    """处理：历史恢复（无 pending 时用户说"确认/取消"）"""
    
    def _process(self, ctx: RouterContext) -> Optional[Dict[str, Any]]:
        # 必须：无 pending 且 用户说"确认/取消"
        if ctx.pending_file_generation or ctx.pending_plugin_install:
            return None
        if not (_confirm_yes(ctx.query) or _confirm_no(ctx.query)):
            return None
        
        recovered = _detect_pending_from_history(ctx.memory)
        
        # 恢复文件生成确认
        if recovered.get("type") == "file":
            if _confirm_yes(ctx.query):
                codes = recovered.get("courses") or []
                if not codes:
                    ctx.log("[STOP] Router: 历史恢复 -> 未识别到课程，先进入 RAG")
                    return {"route": "retrieve_rag", "reasoning": "历史确认缺少课程"}
                ctx.log(f"[OK] Router: 历史恢复 -> 用户确认生成选课文件 -> {codes}")
                return {
                    "route": "call_tool",
                    "tool_name": "generate_selection",
                    "tool_args": {"courses": codes},
                    "pending_file_generation": None,
                    "reasoning": "历史恢复：用户确认生成选课文件"
                }
            else:
                ctx.log("[STOP] Router: 历史恢复 -> 用户取消生成选课文件")
                return {
                    "route": "general_chat",
                    "file_generation_declined": True,
                    "pending_file_generation": None,
                    "reasoning": "历史恢复：用户取消生成选课文件"
                }
        
        # 恢复插件安装确认
        if recovered.get("type") == "plugin":
            if _confirm_yes(ctx.query):
                ctx.log("[OK] Router: 历史恢复 -> 用户确认安装插件")
                return {
                    "route": "call_tool",
                    "tool_name": "plugin_install",
                    "tool_args": {},
                    "pending_plugin_install": None,
                    "reasoning": "历史恢复：用户确认安装插件"
                }
            else:
                ctx.log("[STOP] Router: 历史恢复 -> 用户取消安装插件")
                return {
                    "route": "general_chat",
                    "pending_plugin_install": None,
                    "reasoning": "历史恢复：用户取消安装插件"
                }
        
        # 历史无匹配
        ctx.log("[INFO] Router: 用户输入确认/取消，但历史无匹配 -> 普通聊天")
        return {"route": "general_chat", "reasoning": "无 pending 且历史无匹配"}


class LLMRouterHandler(RouteHandler):
    """处理：LLM 智能路由（兜底）"""
    
    def __init__(self, next_handler: Optional['RouteHandler'] = None):
        super().__init__(next_handler)
        
        self.routing_tools_schema = ROUTER_ONLY_SCHEMA
        
        self.callable_tools_list: List[BaseTool] = get_tools()

        available_tools_desc = []
        for t in self.routing_tools_schema:
            func_info = t.get("function", {})
            available_tools_desc.append(
                f"- {func_info.get('name')}: {func_info.get('description')}"
            )
        
        for t in self.callable_tools_list:
            available_tools_desc.append(
                f"- {t.name} (通过 'call_tool' 调用): {t.description}"
            )
        
        self.tools_desc_str = "\n".join(available_tools_desc)


    def _process(self, ctx: RouterContext) -> Optional[Dict[str, Any]]:
        # 2. ‼ 关键：构建 prompt
        #    (我们现在使用 self.tools_desc_str)
        history_str = build_history_str(ctx.messages, max_turns=5)
        
        prompt = f"""你是一个智能路由助手。分析用户查询并决定下一步操作。

**用户查询：** {ctx.query}

**历史对话：**
{history_str}

**学生信息：**
{json.dumps(ctx.student_info, ensure_ascii=False) if ctx.student_info else "(未提供)"}

**待生成文件：**
{json.dumps(ctx.pending_file_generation, ensure_ascii=False) if ctx.pending_file_generation else "(无)"}

**可用操作/工具（你必须选择其中之一）：**
{self.tools_desc_str}

**决策规则：**
1. 仔细阅读用户查询和历史记录。
2. 比较查询意图和可用操作的描述。
3. 你必须调用 `general_chat`、`retrieve_rag` 或 `call_tool` 三个函数之一。
4. 如果调用 `call_tool`，请在 `tool_args` 中提供该工具所需的所有参数。
"""
        
        if ENABLE_VERBOSE_LOGGING:
            print("\n" + "-" * 30 + " LLM ROUTER PROMPT " + "-" * 30)
            print(prompt[:1000] + ("..." if len(prompt) > 1000 else ""))
            print("-" * 75 + "\n")
        
        final_llm_messages = _messages_to_dicts(ctx.messages)
        final_llm_messages.insert(0, {"role": "system", "content": prompt})
        
        try:
            llm_response = call_qwen(
                final_llm_messages,
                model=ROUTER_MODEL,
                temperature=0.1,
                stream=False,
                tools=self.routing_tools_schema,
                tool_choice="auto",
                purpose="router_decision_native",
            )
            ctx.log(f"[LLM Router] 原始返回: {json.dumps(llm_response, ensure_ascii=False, indent=2)[:800]}")
        except Exception as e:
            ctx.log(f"[ERR] LLM Router: 调用异常: {e}")
            return {"route": "general_chat"}
        
        return self._parse_llm_response(ctx, llm_response)
    
    def _parse_llm_response(self, ctx: RouterContext, llm_response: Any) -> Dict[str, Any]:
        """解析 LLM 返回的 tool_calls"""
        if not isinstance(llm_response, dict):
            return {"route": "general_chat"}
        
        tool_calls = llm_response.get("tool_calls")
        if not tool_calls:
            ctx.log("[WARN] LLM Router: 无 tool_calls，fallback 到 general_chat")
            return {"route": "general_chat"}
        
        tool_call = tool_calls[0]
        fn_info = tool_call.get("function", {}) or {}
        function_name = fn_info.get("name")
        arguments = parse_tool_arguments(fn_info.get("arguments"))
        reasoning = arguments.get("reasoning", "(未提供推理)")
        
        ctx.log(f"[BUILD] LLM Router: Function={function_name}, Args={json.dumps(arguments, ensure_ascii=False)}")
        
        # retrieve_rag
        if function_name == "retrieve_rag":
            return {"route": "retrieve_rag", "reasoning": reasoning}
        
        # general_chat
        if function_name == "general_chat":
            return {"route": "general_chat", "reasoning": reasoning}
        
        # call_tool
        if function_name == "call_tool":
            tool_name = arguments.get("tool_name")
            tool_args = arguments.get("tool_args", {}) or {}
            
            # 拦截 generate_selection：(这部分业务逻辑保持不变)
            if tool_name == "generate_selection":
                pending = ctx.state.get("pending_file_generation")
                courses = self._extract_courses_from_args(tool_args)
                if not pending and not courses:
                    ctx.log("[STOP] LLM Router: 想直接生成文件，但没有 pending/courses -> 改为 RAG")
                    return {"route": "retrieve_rag", "reasoning": "禁止直接生成文件，先筛选"}
            
            #  关键变化：检查 self.callable_tools_list
            callable_tool_names = [t.name for t in self.callable_tools_list]
            if not tool_name or tool_name not in callable_tool_names:
                ctx.log(f"[WARN] LLM Router: 尝试调用一个未知的工具 '{tool_name}' (不在 self.callable_tools_list 中)")
                return {"route": "general_chat"}
            
            ctx.log(f"[OK] LLM Router: 决定调用工具 {tool_name}")
            return {
                "route": "call_tool",
                "tool_name": tool_name,
                "tool_args": tool_args,
                "reasoning": reasoning
            }
        
        # 未知函数
        ctx.log(f"[WARN] LLM Router: 未知函数 {function_name}")
        return {"route": "general_chat"}
    
    def _extract_courses_from_args(self, tool_args: dict) -> List[str]:
        """从工具参数中提取课程列表"""
        # (这个辅助函数保持不变)
        if isinstance(tool_args.get("courses"), list):
            return tool_args["courses"]
        if isinstance(tool_args.get("args"), dict) and isinstance(tool_args["args"].get("courses"), list):
            return tool_args["args"]["courses"]
        return []


# ==================== 辅助函数（保持原有逻辑）====================

# node/router.py (AFTER - 修复版)
def _confirm_yes(q: str) -> bool:
    """严格判断确认意图（排除主动请求 和 否定词）"""
    q = (q or "").strip().lower()
    
    # 1. 优先检查否定词（最重要）
    if any(neg_kw in q for neg_kw in ["不要", "取消", "不用", "算了", "no", "decline"]):
        return False
        
    # 2. 排除主动请求（避免"生成选课文件"被误判为确认）
    exclude_patterns = [
        "生成选课文件", "生成文件", "帮我生成",
        "安装插件", "帮我安装",
        "选课", "帮我选", "规划课程"
    ]
    if any(pat in q for pat in exclude_patterns):
        return False
    
    # 3. 确认关键词
    # (我们仍然保留 "要"，因为 "我要" 是一个有效的确认)
    return any(kw in q for kw in ["确认", "好的", "是的", "可以", "要", "ok", "yes"]) or q in ["y", "好"]


def _confirm_no(q: str) -> bool:
    q = (q or "").strip().lower()
    return any(kw in q for kw in ["不需要", "不要", "取消", "算了", "先不要", "no"]) or q == "n"


def _wants_to_decline_file_gen(q: str) -> bool:
    q = (q or "").lower()
    return any(kw in q for kw in ["先不要生成", "不要生成", "不用生成", "暂不生成", "先不要", "不用文件", "取消生成"])


def _wants_plugin_install(q: str) -> bool:
    q = (q or "").lower()
    return ("安装" in q and "插件" in q) or ("install" in q and "plugin" in q)


def _mentions_hard_rule_first(q: str) -> bool:
    q = (q or "").lower()
    return any(kw in q for kw in ["硬规则", "先用硬规则", "先筛选", "先过滤", "filter"])


def _student_info_ready(si: dict) -> bool:
    si = si or {}
    return bool(si.get("major_code") or si.get("raw_summary"))


def _is_course_planning_request(q: str) -> bool:
    ql = (q or "").strip().lower()
    if not ql:
        return False
    has_plan = any(k in ql for k in ["选课", "帮我选", "安排课程", "规划课程", "推荐课程"])
    has_file = any(k in ql for k in ["文件", "生成", "导出", "下载"])
    return has_plan and not has_file


# node/router.py (AFTER - 精确修复版)

def _last_assistant_message(mem: Dict[str, Any]) -> str:
    mem = mem or {}
    
    recent_conversations = mem.get("recent_conversations") or []
    
    if not isinstance(recent_conversations, list):
        return ""

    for conv in reversed(recent_conversations):
        if isinstance(conv, dict):
            a = conv.get("answer") or "" 
            if isinstance(a, str) and a.strip():
                return a
    
    return ""


def _extract_codes(text: str) -> List[str]:
    if not isinstance(text, str):
        return []
    codes = re.findall(r"\b[A-Z]{4}\d{4}\b", text.upper())
    seen, uniq = set(), []
    for c in codes:
        if c not in seen:
            uniq.append(c)
            seen.add(c)
    return uniq


def _detect_pending_from_history(mem: Dict[str, Any]) -> Dict[str, Any]:
    """从历史中检测 pending 信息"""
    a = _last_assistant_message(mem)
    if not a:
        return {}
    a_no_space = a.replace(" ", "").lower()
    
    # 识别"生成选课文件"的确认文案
    if ("选课文件" in a) and ("确认" in a or "是否确认" in a_no_space):
        codes = _extract_codes(a)
        if not codes:
            rec = _extract_courses_with_llm(mem, a)
            codes = [
                it.get("course_code")
                for it in (rec.get("selected") or [])
                if isinstance(it, dict) and it.get("course_code")
            ]
        return {"type": "file", "courses": codes}
    
    # 识别"安装插件"的确认文案
    if ("安装" in a and "插件" in a) and ("确认" in a or "是否确认" in a_no_space):
        return {"type": "plugin"}
    
    return {}


def _extract_courses_with_llm(memory: Dict[str, Any], query: str) -> Dict[str, Any]:
    """使用 LLM 提取推荐课程（保持原有逻辑）"""
    # ... 保持原有实现 ...
    context_parts = []
    long_term = (memory or {}).get("long_term_summary", "")
    if long_term:
        context_parts.append(f"用户背景信息：{long_term}")

    recent_convs = (memory or {}).get("recent_conversations", [])
    if recent_convs:
        conv_text = "\n".join([
            f"用户: {conv.get('Q', '')}\n助手: {conv.get('A', '')}"
            for conv in recent_convs[-10:]
        ])
        context_parts.append(f"最近对话记录：\n{conv_text}")

    context_str = "\n\n".join(context_parts) if context_parts else "(无)"

    extraction_tool = [
        {
            "type": "function",
            "function": {
                "name": "return_course_extraction",
                "description": "从对话与背景中提取明确推荐的课程及对应学期。course_code 必须是如 COMP1511 的格式。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selected": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "course_code": {
                                        "type": "string",
                                        "pattern": "^[A-Z]{4}\\d{4}$",
                                        "description": "课程代码，如 COMP1511"
                                    },
                                    "term": {
                                        "type": "string",
                                        "description": "学期，如 T1 2025 或 S2 2025，可为空"
                                    }
                                },
                                "required": ["course_code"]
                            },
                            "description": "推荐的课程列表"
                        },
                        "meta": {
                            "type": "object",
                            "description": "额外的元信息",
                            "additionalProperties": True
                        }
                    },
                    "required": ["selected"]
                }
            }
        }
    ]

    extract_prompt = f"""
你是一个课程推荐提取专家。请从以下用户背景和最近的对话中，提取出明确推荐的课程及对应学期。
- 课程代码必须是大写四字母+四数字（如 COMP1511）
- 没有学期也可以，term 字段可留空或省略
- 将结果通过工具 return_course_extraction 返回

【用户背景】:
{context_str}

【当前用户输入】:
{query}
"""

    messages = [
        {"role": "system", "content": "你只负责结构化抽取，不要输出自然语言。"},
        {"role": "user", "content": extract_prompt},
    ]

    try:
        resp = call_qwen(
            messages,
            model=ROUTER_MODEL,
            temperature=0.1,
            stream=False,
            tools=extraction_tool,
            tool_choice="auto",
            purpose="course_extraction_native",
        )

        if ENABLE_VERBOSE_LOGGING:
            print(f"[Course Extraction] FC response: {json.dumps(resp, ensure_ascii=False)[:800]}")

        if isinstance(resp, dict) and resp.get("tool_calls"):
            tc = resp["tool_calls"][0]
            fn = (tc.get("function") or {})
            args = parse_tool_arguments(fn.get("arguments"))

            if fn.get("name") == "return_course_extraction" and isinstance(args, dict):
                selected = args.get("selected", [])
                if not isinstance(selected, list):
                    selected = []
                meta = args.get("meta", {})
                if not isinstance(meta, dict):
                    meta = {}

                norm = []
                for item in selected:
                    if not isinstance(item, dict):
                        continue
                    code = item.get("course_code")
                    term = item.get("term")
                    if isinstance(code, str):
                        norm.append({"course_code": code, "term": term} if term else {"course_code": code})
                return {"selected": norm, "meta": meta}

    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"[Course Extraction] Failed: {e}")

    return {"selected": [], "meta": {"note": "no_valid_courses_found"}}


# ==================== 主入口函数 ====================

def node_router(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    路由决策主函数（责任链模式）
    
    处理顺序（按优先级）：
    1. 明确拒绝生成选课文件
    2. 选课/规划请求
    3. 文件生成请求（新请求）
    4. 插件安装请求（新请求）
    5. pending 文件确认/取消
    6. pending 插件确认/取消
    7. 历史恢复（无 pending 时）
    8. LLM 智能路由（兜底）
    """
    ctx = RouterContext(state)
    
    # 构建处理器链（按优先级顺序）
    handler_chain = DeclineFileGenerationHandler(
        CoursePlanningHandler(
            FileGenerationRequestHandler(
                PluginInstallRequestHandler(
                    PendingFileConfirmationHandler(
                        PendingPluginConfirmationHandler(
                            HistoryRecoveryHandler(
                                LLMRouterHandler()
                            )
                        )
                    )
                )
            )
        )
    )
    
    # 执行责任链
    result = handler_chain.handle(ctx)
    
    # 兜底（理论上不会到这里）
    return result or {"route": "general_chat", "reasoning": "fallback"}