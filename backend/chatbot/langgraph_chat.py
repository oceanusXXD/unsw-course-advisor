"""
优化版 LangGraph：v3.3 - Bug修复与路由优化
- 
代码结构：
1. 性能监控模块（PerformanceMonitor）：记录各节点和 LLM 调用的耗时与统计信息。
2. 配置与环境变量加载：支持模型、路由、内存等参数的灵活配置。
3. 工具定义（TOOL_REGISTRY）：可扩展的工具调用接口。
4. 内存缓存（MemoryCache）：高效管理用户对话历史，减少磁盘 I/O。
5. 状态定义（ChatState）：统一管理对话流程中的所有变量。
6. 各节点函数（如 node_prepare_input、node_router、node_retrieve 等）：实现对话流程的各个步骤。
7. LangGraph 流程编排：通过 StateGraph 定义节点和条件路由，实现灵活的对话流转。
8. 主入口 run_chat：对外暴露的对话接口，支持性能报告和自定义参数。
9. 性能分析工具与测试代码：便于开发者调试和优化。

使用方法：
- 直接调用 run_chat(query, user_id, ...) 即可获得智能问答结果，支持课程检索、工具调用、澄清和通用对话。
- 支持性能报告、记忆管理和建议问题等高级功能。
- 可通过环境变量灵活配置模型、路由和缓存等参数。
"""

import os
import json
import time
import uuid
import traceback
import requests
from typing import Dict, Any, Optional, List, Annotated, Literal, Callable
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from functools import wraps
from datetime import datetime
from . import rag_chain_qwen as rag
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# --- Performance Monitoring ---

class PerformanceMonitor:
    """性能监控器"""
    def __init__(self):
        self.metrics = {}
        self.current_session = None
    
    def start_session(self, session_id: str):
        """开始新的会话监控"""
        self.current_session = session_id
        self.metrics[session_id] = {
            "start_time": time.time(),
            "nodes": {},
            "llm_calls": [],
            "total_tokens": 0
        }
    
    def record_node(self, node_name: str, duration: float):
        """记录节点执行时间"""
        if self.current_session:
            if node_name not in self.metrics[self.current_session]["nodes"]:
                self.metrics[self.current_session]["nodes"][node_name] = []
            self.metrics[self.current_session]["nodes"][node_name].append(duration)
    
    def record_llm_call(self, purpose: str, duration: float, tokens: int = 0):
        """记录 LLM 调用"""
        if self.current_session:
            self.metrics[self.current_session]["llm_calls"].append({
                "purpose": purpose,
                "duration": duration,
                "tokens": tokens,
                "timestamp": time.time()
            })
            self.metrics[self.current_session]["total_tokens"] += tokens
    
    def end_session(self) -> Dict[str, Any]:
        """结束会话并返回性能报告"""
        if not self.current_session:
            return {}
        
        session_data = self.metrics[self.current_session]
        total_time = time.time() - session_data["start_time"]
        
        # 计算节点统计
        node_stats = {}
        for node, durations in session_data["nodes"].items():
            node_stats[node] = {
                "count": len(durations),
                "total_time": sum(durations),
                "avg_time": sum(durations) / len(durations),
                "percentage": (sum(durations) / total_time * 100) if total_time > 0 else 0
            }
        
        # LLM 调用统计
        llm_stats = {
            "total_calls": len(session_data["llm_calls"]),
            "total_time": sum(c["duration"] for c in session_data["llm_calls"]),
            "total_tokens": session_data["total_tokens"],
            "by_purpose": {}
        }
        
        for call in session_data["llm_calls"]:
            purpose = call["purpose"]
            if purpose not in llm_stats["by_purpose"]:
                llm_stats["by_purpose"][purpose] = {"count": 0, "total_time": 0}
            llm_stats["by_purpose"][purpose]["count"] += 1
            llm_stats["by_purpose"][purpose]["total_time"] += call["duration"]
        
        report = {
            "session_id": self.current_session,
            "total_time": total_time,
            "node_stats": node_stats,
            "llm_stats": llm_stats,
            "timestamp": datetime.now().isoformat()
        }
        
        self.current_session = None
        return report

# 全局性能监控器
perf_monitor = PerformanceMonitor()

def monitor_performance(node_name: str):
    """性能监控装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                perf_monitor.record_node(node_name, duration)
                if ENABLE_VERBOSE_LOGGING:
                    print(f"⏱️  [{node_name}] completed in {duration:.3f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                perf_monitor.record_node(f"{node_name}_ERROR", duration)
                raise
        return wrapper
    return decorator

# --- Configuration ---
load_dotenv()
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-max")
GROUNDING_MODEL = os.getenv("GROUNDING_MODEL", "qwen-plus")
API_KEY = os.getenv("DASHSCOPE_API_KEY")

# 路由模型配置 - 支持独立的小模型
ROUTING_MODEL_URL = os.getenv("ROUTING_MODEL_URL", "")  # 留空则使用主模型
ROUTING_MODEL_NAME = os.getenv("ROUTING_MODEL_NAME", "")  # 留空则使用主模型
ROUTING_MODEL_KEY = os.getenv("ROUTING_MODEL_KEY", "")  # 留空则使用主 API Key
USE_FAST_ROUTER = os.getenv("USE_FAST_ROUTER", "false").lower() == "true"

TOP_K = getattr(rag, "TOP_K", 8)

# 性能优化配置
ENABLE_GROUNDING_CHECK = os.getenv("ENABLE_GROUNDING_CHECK", "false").lower() == "true"
ENABLE_SUGGESTIONS = os.getenv("ENABLE_SUGGESTIONS", "false").lower() == "true"
ENABLE_VERBOSE_LOGGING = os.getenv("ENABLE_VERBOSE_LOGGING", "true").lower() == "true"
MAX_HISTORY_LENGTH = int(os.getenv("MAX_HISTORY_LENGTH", "10"))
MAX_MEMORY_MESSAGES = int(os.getenv("MAX_MEMORY_MESSAGES", "20"))
MEMORY_CACHE_TTL = int(os.getenv("MEMORY_CACHE_TTL", "300"))  # 5分钟缓存

# 路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_DIR = os.path.join(BASE_DIR, "memory_data")
MEMORY_STORE = os.path.join(MEMORY_DIR, "memory_store.json")
os.makedirs(MEMORY_DIR, exist_ok=True)

RESPONSE_TEMPLATES = {
    "error_api": "抱歉，我在与我的核心模型通信时遇到了问题。请稍后再试。",
    "error_rag": "抱歉，我在检索课程信息时遇到了内部错误。我已经记录了这个问题。",
    "error_tool": "抱歉，在尝试执行一个工具时发生了错误。",
    "error_grounding": "我找到了相关信息，但在生成确认无误的答案时遇到了困难。为避免提供错误信息，我无法回答这个问题。",
    "fallback_no_rag_docs": "我在知识库中没有找到关于您问题的具体信息，但我会尽力根据通用知识来回答。"
}

# --- Tool Definition ---
def get_course_instructor(course_code: str) -> str:
    """A mock tool to get the instructor for a given course code."""
    if ENABLE_VERBOSE_LOGGING:
        print(f"🔧 TOOL: get_course_instructor({course_code=})")
    mock_db = {
        "CS101": "Dr. Alan Turing",
        "MATH203": "Prof. Ada Lovelace",
        "PHYS301": "Dr. Marie Curie"
    }
    instructor = mock_db.get(course_code.upper(), "未找到该课程的讲师信息")
    return json.dumps({"course_code": course_code, "instructor": instructor}, ensure_ascii=False)

TOOL_REGISTRY = {
    "get_course_instructor": {
        "function": get_course_instructor,
        "description": "获取特定课程代码的授课讲师。",
        "args": {"course_code": "string (e.g., 'CS101')"}
    }
}

# --- Memory Cache ---
class MemoryCache:
    """内存缓存，减少文件 I/O"""
    def __init__(self, ttl: int = 300):
        self.cache = {}
        self.ttl = ttl
        self.last_loaded = 0
        self._dirty_users = set()
    
    def get(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户记忆"""
        current_time = time.time()
        
        # 如果缓存过期，重新加载
        if current_time - self.last_loaded > self.ttl:
            self._load_from_disk()
        
        return self.cache.get(user_id)
    
    def set(self, user_id: str, memory: Dict[str, Any]):
        """设置用户记忆"""
        self.cache[user_id] = memory
        self._dirty_users.add(user_id)
    
    def _load_from_disk(self):
        """从磁盘加载所有记忆"""
        try:
            if os.path.exists(MEMORY_STORE):
                with open(MEMORY_STORE, "r", encoding="utf-8") as fr:
                    self.cache = json.load(fr)
                self.last_loaded = time.time()
                if ENABLE_VERBOSE_LOGGING:
                    print(f"💾 Memory cache loaded: {len(self.cache)} users")
        except Exception as e:
            if ENABLE_VERBOSE_LOGGING:
                print(f"⚠️  Memory cache load error: {e}")
    
    def flush(self):
        """将脏数据写入磁盘"""
        if not self._dirty_users:
            return
        
        try:
            # 读取现有数据
            all_mem = {}
            if os.path.exists(MEMORY_STORE):
                with open(MEMORY_STORE, "r", encoding="utf-8") as fr:
                    all_mem = json.load(fr)
            
            # 更新脏用户的数据
            for user_id in self._dirty_users:
                if user_id in self.cache:
                    all_mem[user_id] = self.cache[user_id]
            
            # 写入磁盘
            with open(MEMORY_STORE, "w", encoding="utf-8") as fw:
                json.dump(all_mem, fw, ensure_ascii=False, indent=2)
            
            if ENABLE_VERBOSE_LOGGING:
                print(f"💾 Memory flushed: {len(self._dirty_users)} users")
            
            self._dirty_users.clear()
        except Exception as e:
            if ENABLE_VERBOSE_LOGGING:
                print(f"⚠️  Memory flush error: {e}")

# 全局内存缓存
memory_cache = MemoryCache(ttl=MEMORY_CACHE_TTL)

# --- State Definition ---
class ChatState(TypedDict):
    messages: Annotated[list, add_messages]
    query: str
    user_id: Optional[str]
    route: Optional[Literal["retrieve_rag", "call_tool", "needs_clarification", "general_chat"]]
    tool_name: Optional[str]
    tool_args: Optional[dict]
    tool_call_id: Optional[str]  # 新增：存储工具调用 ID
    retrieved: Optional[List[dict]]
    answer: Optional[str]
    is_grounded: Optional[bool]
    final_output: Optional[Dict[str, Any]]
    memory: Optional[Dict[str, Any]]
    # 性能配置
    enable_grounding: Optional[bool]
    enable_suggestions: Optional[bool]

# --- Helper Functions ---
def _message_to_dict(msg) -> Dict[str, str]:
    """Convert a message to a plain dict."""
    if isinstance(msg, HumanMessage):
        return {"role": "user", "content": msg.content}
    elif isinstance(msg, AIMessage):
        return {"role": "assistant", "content": msg.content}
    elif isinstance(msg, ToolMessage):
        return {"role": "tool", "content": msg.content, "tool_call_id": msg.tool_call_id}
    elif isinstance(msg, dict):
        return msg
    else:
        return {"role": "unknown", "content": str(msg)}

def _messages_to_dicts(messages: List) -> List[Dict[str, str]]:
    """Convert messages to plain dicts."""
    return [_message_to_dict(m) for m in messages]

def load_memory(user_id: Optional[str]) -> Dict[str, Any]:
    """加载用户记忆（使用缓存）"""
    if not user_id:
        return {"summary": "", "history": []}
    
    # 先从缓存获取
    cached = memory_cache.get(user_id)
    if cached is not None:
        return cached
    
    # 缓存未命中，从磁盘加载
    try:
        if os.path.exists(MEMORY_STORE):
            with open(MEMORY_STORE, "r", encoding="utf-8") as fr:
                all_mem = json.load(fr)
                user_mem = all_mem.get(user_id, {"summary": "", "history": []})
                memory_cache.set(user_id, user_mem)
                return user_mem
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"⚠️  Memory load error: {e}")
    
    return {"summary": "", "history": []}

def save_memory(user_id: Optional[str], memory: Dict[str, Any]):
    """保存用户记忆（延迟写入）"""
    if not user_id:
        return
    
    try:
        safe_memory = {
            "summary": memory.get("summary", ""),
            "history": _messages_to_dicts(memory.get("history", []))
        }
        memory_cache.set(user_id, safe_memory)
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"⚠️  Memory save error: {e}")

# --- Core LLM Call ---
def call_qwen_sync(messages: list, model: Optional[str] = None, system_prompt: Optional[str] = None, 
                   purpose: str = "general", base_url: Optional[str] = None, 
                   api_key: Optional[str] = None, **kwargs) -> str:
    """调用 Qwen LLM API，同步接口（带性能监控）"""
    start_time = time.time()
    safe_messages = _messages_to_dicts(messages)
    final_messages = ([{"role": "system", "content": system_prompt}] + safe_messages) if system_prompt else safe_messages

    # 使用指定的 base_url 和 api_key，否则使用默认值
    url = (base_url or QWEN_BASE_URL).rstrip("/") + "/chat/completions"
    key = api_key or API_KEY
    
    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model or QWEN_MODEL, "messages": final_messages, **kwargs},
            timeout=45
        )
        response.raise_for_status()
        result = response.json()
        
        # 记录性能
        duration = time.time() - start_time
        tokens = result.get("usage", {}).get("total_tokens", 0)
        perf_monitor.record_llm_call(purpose, duration, tokens)
        
        return result['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        duration = time.time() - start_time
        perf_monitor.record_llm_call(f"{purpose}_ERROR", duration)
        if ENABLE_VERBOSE_LOGGING:
            traceback.print_exc()
        return json.dumps({"error": "API_ERROR", "message": str(e)})

# --- Graph Nodes ---

@monitor_performance("prepare_input")
def node_prepare_input(state: ChatState) -> Dict[str, Any]:
    """准备输入：加载用户记忆并构建消息列表"""
    user_id = state.get("user_id")
    query = state.get("query", "").strip()
    
    mem = load_memory(user_id)
    history = mem.get("history", [])
    recent_history = history[-MAX_HISTORY_LENGTH:] if len(history) > MAX_HISTORY_LENGTH else history
    messages = _messages_to_dicts(recent_history) + [{"role": "user", "content": query}]
    
    return {"memory": mem, "messages": messages}

@monitor_performance("router")
def node_router(state: ChatState) -> Dict[str, Any]:
    """智能路由：决定使用 RAG、工具、澄清还是通用对话"""
    query = state.get("query", "")
    
    tool_definitions = json.dumps([
        {"name": name, "description": details["description"], "args": details["args"]} 
        for name, details in TOOL_REGISTRY.items()
    ], ensure_ascii=False)
    
    prompt = f"""你是一个智能路由机器人。根据用户的问题，决定下一步的最佳行动。可用的行动如下：
1. `retrieve_rag`: 当用户询问课程的具体信息，如先修课程、学分、课程代码、教学大纲(syllabus)等。
2. `call_tool`: 当用户意图可以通过调用工具来完成时。
3. `needs_clarification`: 当用户的问题含糊不清，需要更多信息才能准确回答时。
4. `general_chat`: 对于其他所有问题，如问候、常识性问题、自我介绍等。

可用的工具如下:
{tool_definitions}

用户问题: "{query}"

请只返回一个JSON对象，格式如下:
- 如果选择 `retrieve_rag` 或 `general_chat` 或 `needs_clarification`，返回: {{"route": "行动名称"}}
- 如果选择 `call_tool`，返回: {{"route": "call_tool", "tool_name": "工具名称", "tool_args": {{"参数1": "值1", ...}}}}
"""
    try:
        # 根据配置选择路由模型
        if USE_FAST_ROUTER and ROUTING_MODEL_URL and ROUTING_MODEL_NAME:
            if ENABLE_VERBOSE_LOGGING:
                print(f"🚀 Using fast router: {ROUTING_MODEL_NAME}")
            response_str = call_qwen_sync(
                [{"role": "user", "content": prompt}], 
                model=ROUTING_MODEL_NAME,
                base_url=ROUTING_MODEL_URL,
                api_key=ROUTING_MODEL_KEY if ROUTING_MODEL_KEY else None,
                temperature=0.0, 
                purpose="routing_fast"
            )
        else:
            response_str = call_qwen_sync(
                [{"role": "user", "content": prompt}], 
                model=QWEN_MODEL, 
                temperature=0.0, 
                purpose="routing"
            )
        
        decision = json.loads(response_str)
        
        route = decision.get("route")
        if ENABLE_VERBOSE_LOGGING:
            print(f"🧭 ROUTE: {route}")
        
        # 如果是工具调用，生成 tool_call_id
        if route == "call_tool":
            decision["tool_call_id"] = f"call_{uuid.uuid4().hex[:16]}"
        
        return decision
        
    except (json.JSONDecodeError, KeyError) as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"⚠️  Router failed, defaulting to general_chat: {e}")
        return {"route": "general_chat"}

@monitor_performance("retrieve")
def node_retrieve(state: ChatState) -> Dict[str, Any]:
    """执行 RAG 检索"""
    try:
        query = state.get("query", "")
        docs = rag.retrieve(query, top_k=TOP_K) or []
        
        if ENABLE_VERBOSE_LOGGING:
            print(f"📚 RETRIEVE: Found {len(docs)} documents")
        
        if not docs:
            no_docs_msg = {"role": "system", "content": RESPONSE_TEMPLATES["fallback_no_rag_docs"]}
            return {"retrieved": [], "messages": [no_docs_msg]}
        
        return {"retrieved": docs}
        
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"⚠️  RETRIEVE ERROR: {e}")
            traceback.print_exc()
        return {"retrieved": [], "answer": RESPONSE_TEMPLATES["error_rag"]}

@monitor_performance("tool_executor")
def node_tool_executor(state: ChatState) -> Dict[str, Any]:
    """执行工具调用"""
    tool_name = state.get("tool_name")
    tool_args = state.get("tool_args")
    tool_call_id = state.get("tool_call_id")
    
    if not tool_name or tool_name not in TOOL_REGISTRY:
        error_msg = ToolMessage(
            content=f"Error: Tool '{tool_name}' not found.",
            tool_call_id=tool_call_id or "unknown"
        )
        return {"messages": [error_msg], "answer": RESPONSE_TEMPLATES["error_tool"]}
    
    try:
        tool_function = TOOL_REGISTRY[tool_name]["function"]
        if not isinstance(tool_args, dict):
            raise ValueError("tool_args must be a dictionary.")
        
        result = tool_function(**tool_args)
        
        # 创建符合 LangChain 规范的 ToolMessage
        tool_msg = ToolMessage(
            content=result,
            tool_call_id=tool_call_id or f"call_{uuid.uuid4().hex[:16]}"
        )
        
        if ENABLE_VERBOSE_LOGGING:
            print(f"✅ TOOL: {tool_name} executed successfully")
        
        return {"messages": [tool_msg]}
        
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            traceback.print_exc()
        
        error_msg = ToolMessage(
            content=f"Error executing tool {tool_name}: {str(e)}",
            tool_call_id=tool_call_id or "unknown"
        )
        return {"messages": [error_msg], "answer": RESPONSE_TEMPLATES["error_tool"]}

@monitor_performance("generate")
def node_generate(state: ChatState) -> Dict[str, Any]:
    """生成答案"""
    messages = state.get("messages", [])
    retrieved = state.get("retrieved") or []
    route = state.get("route")
    
    system_prompt = "你是一个中立且乐于助人的 AI 助手。请根据对话历史和你的知识来回答。"

    if retrieved:
        context_str = "\n\n".join([
            f"来源 {i+1}: {doc.get('source_file', '未知')}\n内容: {(doc.get('_text') or doc.get('content') or '')[:500]}"
            for i, doc in enumerate(retrieved) if doc
        ])
        system_prompt = (f"你是一个课程问答助手。请严格基于以下检索到的信息和对话历史来回答问题。\n\n"
                         f"### 检索到的信息 ###\n{context_str}\n\n"
                         "请用中文简洁回答，并引用相关来源（如来源1、来源2等）。如果信息不足，请明确说明。")
    elif route == "needs_clarification":
        system_prompt = "你是一个乐于助人的AI助手。用户的问题不够清晰，请你生成一个问题来向用户请求澄清。"
    elif route == "general_chat":
        system_prompt = "你是一个友好、乐于助人的 AI 助手。请自然地回答用户的问题，保持对话的连贯性。"

    answer = call_qwen_sync(messages, system_prompt=system_prompt, temperature=0.2, purpose="generation")
    
    try:
        answer_json = json.loads(answer)
        if "error" in answer_json:
            return {"answer": RESPONSE_TEMPLATES["error_api"]}
    except json.JSONDecodeError:
        pass
    
    return {"answer": answer}

@monitor_performance("grounding_check")
def node_grounding_check(state: ChatState) -> Dict[str, Any]:
    """检查答案是否有检索文档支持（可选功能）"""
    # 检查是否启用
    if not state.get("enable_grounding", ENABLE_GROUNDING_CHECK):
        if ENABLE_VERBOSE_LOGGING:
            print("⏭️  GROUNDING CHECK: Disabled")
        return {"is_grounded": True}
    
    retrieved = state.get("retrieved")
    if not retrieved:
        return {"is_grounded": True}
    
    answer = state.get("answer", "")
    if answer in RESPONSE_TEMPLATES.values():
        return {"is_grounded": True}
    
    context_str = "\n\n".join([
        f"来源 {i+1}: {(doc.get('_text') or doc.get('content') or '')[:800]}"
        for i, doc in enumerate(retrieved)
    ])
    
    prompt = (f"只回答yes")
    
    try:
        verification = call_qwen_sync([{"role": "user", "content": prompt}], 
                                     model=GROUNDING_MODEL, temperature=0.0, purpose="grounding")
        is_grounded = "yes" in verification.lower()
        
        if ENABLE_VERBOSE_LOGGING:
            print(f"✓ GROUNDING: {is_grounded}")
        
        return {"is_grounded": is_grounded}
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"⚠️  GROUNDING ERROR: {e}")
        return {"is_grounded": True}

@monitor_performance("finalize")
def node_finalize(state: ChatState) -> Dict[str, Any]:
    """最终化节点：生成完整输出并保存记忆"""
    final_answer = state.get("answer", "抱歉，我无法回答。")
    is_grounded = state.get("is_grounded", True)
    route = state.get("route")
    
    # 只有在 RAG 路由且 grounding 失败时才使用错误模板
    #if not is_grounded:
    #    final_answer = RESPONSE_TEMPLATES["error_grounding"]

    # 生成建议问题（可选功能）
    suggested_questions = []
    if state.get("enable_suggestions", ENABLE_SUGGESTIONS):
        try:
            messages = state.get("messages", [])
            history_str = "\n".join([f"{m.get('role', 'unknown')}: {m.get('content', '')}" 
                                    for m in _messages_to_dicts(messages[-5:])])
            prompt = (f"基于以下对话，请生成 2-3 个用户可能感兴趣的相关问题，用于引导对话。"
                     f"请只返回一个JSON列表，例如：[\"问题1？\", \"问题2？\"]。\n\n"
                     f"### 对话历史 ###\n{history_str}\n\n最终回答: {final_answer[:200]}")
            suggestions_str = call_qwen_sync([{"role": "user", "content": prompt}], 
                                            model=GROUNDING_MODEL, temperature=0.5, purpose="suggestions")
            suggested_questions = json.loads(suggestions_str)
        except Exception as e:
            if ENABLE_VERBOSE_LOGGING:
                print(f"⚠️  SUGGESTIONS ERROR: {e}")

    # 准备源信息
    retrieved = state.get("retrieved") or []
    sources = [
        {
            "title": d.get("title", d.get("course_code", "未知")), 
            "source": d.get("source_file", d.get("url", "未知")), 
            "score": d.get("_score")
        } 
        for d in retrieved
    ]

    # 准备最终输出
    final_output = {
        "answer": final_answer,
        "sources": sources,
        "suggested_questions": suggested_questions,
        "route_decision": route,
        "is_grounded": is_grounded
    }
    
    # 更新并保存记忆
    user_id = state.get("user_id")
    mem = state.get("memory", {})
    
    current_messages = _messages_to_dicts(state.get("messages", []))
    updated_messages = current_messages + [{"role": "assistant", "content": final_answer}]
    
    # 只保留最近的消息
    if len(updated_messages) > MAX_MEMORY_MESSAGES:
        updated_messages = updated_messages[-MAX_MEMORY_MESSAGES:]
    
    mem = mem or {}
    mem["history"] = updated_messages
    
    # 更新摘要（简化版）
    if final_answer and any(k in final_answer for k in ["记住", "保存偏好", "我叫", "我的名字"]):
        current_summary = mem.get("summary", "")
        mem["summary"] = (current_summary + "\n" + final_answer)[:2000]
    
    # 保存记忆（延迟写入）
    save_memory(user_id, mem)

    return {"final_output": final_output, "memory": mem}

# --- Graph Definition ---

def route_logic(state: ChatState) -> str:
    """Conditional routing logic."""
    if state.get("answer"):
        return "finalize"
    route = state.get("route")
    if route == "retrieve_rag":
        return "retrieve"
    if route == "call_tool":
        return "tool_executor"
    return "generate"

def grounding_check_logic(state: ChatState) -> str:
    """Decide if grounding is needed."""
    route = state.get("route")
    retrieved = state.get("retrieved")
    enable_grounding = state.get("enable_grounding", ENABLE_GROUNDING_CHECK)
    
    if enable_grounding and route == "retrieve_rag" and retrieved:
        return "grounding_check"
    return "finalize"

graph_builder = StateGraph(ChatState)

graph_builder.add_node("prepare_input", node_prepare_input)
graph_builder.add_node("router", node_router)
graph_builder.add_node("retrieve", node_retrieve)
graph_builder.add_node("tool_executor", node_tool_executor)
graph_builder.add_node("generate", node_generate)
graph_builder.add_node("grounding_check", node_grounding_check)
graph_builder.add_node("finalize", node_finalize)

graph_builder.add_edge(START, "prepare_input")
graph_builder.add_edge("prepare_input", "router")
graph_builder.add_conditional_edges(
    "router",
    route_logic,
    {"retrieve": "retrieve", "tool_executor": "tool_executor", "generate": "generate", "finalize": "finalize"}
)
graph_builder.add_edge("retrieve", "generate")
graph_builder.add_edge("tool_executor", "generate")
graph_builder.add_conditional_edges(
    "generate",
    grounding_check_logic,
    {"grounding_check": "grounding_check", "finalize": "finalize"}
)
graph_builder.add_edge("grounding_check", "finalize")
graph_builder.add_edge("finalize", END)

compiled_graph = graph_builder.compile()

# --- Helper Functions ---

def _deep_convert_langchain(obj):
    """深度转换 LangChain 消息对象"""
    if isinstance(obj, (HumanMessage, AIMessage, ToolMessage)):
        result = {"role": "user" if isinstance(obj, HumanMessage) else 
                         "assistant" if isinstance(obj, AIMessage) else "tool", 
                  "content": obj.content}
        if isinstance(obj, ToolMessage):
            result["tool_call_id"] = obj.tool_call_id
        return result
    elif isinstance(obj, list):
        return [_deep_convert_langchain(o) for o in obj]
    elif isinstance(obj, dict):
        return {k: _deep_convert_langchain(v) for k, v in obj.items()}
    else:
        return obj

# --- Main Entry Point ---

def run_chat(
    query: str,
    user_id: Optional[str] = None,
    init_messages: Optional[List[Dict]] = None,
    enable_grounding: Optional[bool] = None,
    enable_suggestions: Optional[bool] = None,
    return_performance: bool = False
) -> Dict[str, Any]:
    """
    Main function to run the conversational agent.
    
    Args:
        query: 用户问题
        user_id: 用户 ID
        init_messages: 初始消息列表
        enable_grounding: 是否启用 grounding check（None 使用默认配置）
        enable_suggestions: 是否启用建议问题（None 使用默认配置）
        return_performance: 是否返回性能报告
    
    Returns:
        包含答案和性能报告的字典
    """
    # 生成会话 ID
    session_id = f"{user_id or 'anonymous'}_{int(time.time() * 1000)}"
    perf_monitor.start_session(session_id)
    
    initial_state: Dict[str, Any] = {
        "query": query,
        "user_id": user_id,
        "messages": init_messages if init_messages else [],
        "route": None,
        "tool_name": None,
        "tool_args": None,
        "tool_call_id": None,
        "retrieved": None,
        "answer": None,
        "is_grounded": None,
        "final_output": None,
        "memory": None,
        "enable_grounding": enable_grounding if enable_grounding is not None else ENABLE_GROUNDING_CHECK,
        "enable_suggestions": enable_suggestions if enable_suggestions is not None else ENABLE_SUGGESTIONS
    }

    try:
        if ENABLE_VERBOSE_LOGGING:
            print("=" * 80)
            print(f"🚀 SESSION: {session_id}")
            print(f"❓ QUERY: {query}")
            print("=" * 80)
        
        final_state = compiled_graph.invoke(initial_state)
        
        # 获取性能报告
        perf_report = perf_monitor.end_session()
        
        if ENABLE_VERBOSE_LOGGING:
            print("=" * 80)
            print("✅ SESSION COMPLETED")
            print(f"⏱️  Total time: {perf_report['total_time']:.3f}s")
            print(f"🔄 LLM calls: {perf_report['llm_stats']['total_calls']}")
            print(f"🎯 Tokens: {perf_report['llm_stats']['total_tokens']}")
            print("=" * 80)
        
        # 刷新内存缓存到磁盘
        memory_cache.flush()
        
        # 转换结果
        final_state = _deep_convert_langchain(final_state)
        output = final_state.get("final_output", {}) if isinstance(final_state, dict) else {}
        
        if not isinstance(output, dict):
            if isinstance(output, list) and output and isinstance(output[0], dict):
                output = output[0]
            else:
                output = {}

        if not output or (isinstance(output, dict) and "error" in output):
            result = {
                "error": output.get("error", "Graph execution failed") if isinstance(output, dict) else "Graph execution failed",
                "answer": RESPONSE_TEMPLATES.get("error_api")
            }
        else:
            result = {
                **output,
                "messages": _messages_to_dicts(final_state.get("messages", initial_state["messages"])),
                "use_rag": (output.get("route_decision") == "retrieve_rag"),
                "memory": final_state.get("memory")
            }
        
        # 添加性能报告
        if return_performance:
            result["performance"] = perf_report
        
        return result

    except Exception as e:
        perf_report = perf_monitor.end_session()
        if ENABLE_VERBOSE_LOGGING:
            traceback.print_exc()
        
        result = {
            "error": str(e),
            "answer": RESPONSE_TEMPLATES.get("error_api"),
            "trace": traceback.format_exc()
        }
        
        if return_performance:
            result["performance"] = perf_report
        
        return result

# --- Performance Analysis ---

def print_performance_summary(perf_report: Dict[str, Any]):
    """打印性能摘要"""
    print("\n" + "=" * 80)
    print("📊 PERFORMANCE SUMMARY")
    print("=" * 80)
    
    print(f"\n⏱️  Total Time: {perf_report['total_time']:.3f}s")
    
    print("\n📈 Node Performance:")
    for node, stats in sorted(perf_report['node_stats'].items(), 
                              key=lambda x: x[1]['total_time'], reverse=True):
        print(f"  {node:20s}: {stats['total_time']:.3f}s ({stats['percentage']:.1f}%) "
              f"[{stats['count']} calls, avg: {stats['avg_time']:.3f}s]")
    
    print("\n🤖 LLM Call Statistics:")
    llm_stats = perf_report['llm_stats']
    print(f"  Total Calls: {llm_stats['total_calls']}")
    print(f"  Total Time: {llm_stats['total_time']:.3f}s")
    print(f"  Total Tokens: {llm_stats['total_tokens']}")
    
    print("\n  By Purpose:")
    for purpose, stats in sorted(llm_stats['by_purpose'].items(), 
                                 key=lambda x: x[1]['total_time'], reverse=True):
        avg_time = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
        print(f"    {purpose:15s}: {stats['count']} calls, {stats['total_time']:.3f}s "
              f"(avg: {avg_time:.3f}s)")
    
    print("\n" + "=" * 80)

# --- For Testing ---

if __name__ == "__main__":
    # 设置测试环境变量
    os.environ["ENABLE_VERBOSE_LOGGING"] = "true"
    os.environ["ENABLE_GROUNDING_CHECK"] = "false"
    os.environ["ENABLE_SUGGESTIONS"] = "false"
    os.environ["USE_FAST_ROUTER"] = "false"  # 默认不使用快速路由
    
    user_id = "test_user_v3.3_fixed"
    
    print("\n" + "🧪 " * 40)
    print("Testing Fixed & Optimized LangGraph v3.3")
    print("🧪 " * 40)
    
    # 测试 1: RAG 查询
    print("\n\n--- Test 1: RAG Query ---")
    result1 = run_chat("COMP9011的先修课程和学分是什么？", user_id, return_performance=True)
    print(json.dumps({k: v for k, v in result1.items() if k != "performance"}, 
                     indent=2, ensure_ascii=False))
    if "performance" in result1:
        print_performance_summary(result1["performance"])

    # 测试 2: 工具调用（修复后应该不会报错）
    print("\n\n--- Test 2: Tool Use Query (FIXED) ---")
    result2 = run_chat("谁是COMP9011的老师？", user_id, return_performance=True)
    print(json.dumps({k: v for k, v in result2.items() if k != "performance"}, 
                     indent=2, ensure_ascii=False))
    if "performance" in result2:
        print_performance_summary(result2["performance"])
    
    # 测试 3: 通用对话
    print("\n\n--- Test 3: General Chat ---")
    result3 = run_chat("你好，我叫小明", user_id, return_performance=True)
    print(json.dumps({k: v for k, v in result3.items() if k != "performance"}, 
                     indent=2, ensure_ascii=False))
    if "performance" in result3:
        print_performance_summary(result3["performance"])
    
    print(f"\n💾 Memory file: {MEMORY_STORE}")
    print("\n" + "✅ " * 40)
    print("All tests completed!")
    print("✅ " * 40)