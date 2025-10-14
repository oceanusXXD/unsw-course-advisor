# core.py
import os
import json
import time
import traceback
import requests
from functools import wraps
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Any, Optional, List, Annotated, Literal, Iterator, Union
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
load_dotenv()

# --- 配置 ---
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-max")
GROUNDING_MODEL = os.getenv("GROUNDING_MODEL", "qwen-plus")
API_KEY = os.getenv("DASHSCOPE_API_KEY")

ROUTING_MODEL_URL = os.getenv("ROUTING_MODEL_URL", "")
ROUTING_MODEL_NAME = os.getenv("ROUTING_MODEL_NAME", "")
ROUTING_MODEL_KEY = os.getenv("ROUTING_MODEL_KEY", "")
USE_FAST_ROUTER = os.getenv("USE_FAST_ROUTER", "false").lower() == "true"

ENABLE_GROUNDING_CHECK = os.getenv("ENABLE_GROUNDING_CHECK", "false").lower() == "true"
ENABLE_SUGGESTIONS = os.getenv("ENABLE_SUGGESTIONS", "false").lower() == "true"
ENABLE_VERBOSE_LOGGING = os.getenv("ENABLE_VERBOSE_LOGGING", "true").lower() == "true"
MAX_HISTORY_LENGTH = int(os.getenv("MAX_HISTORY_LENGTH", "10"))
MAX_MEMORY_MESSAGES = int(os.getenv("MAX_MEMORY_MESSAGES", "20"))
MEMORY_CACHE_TTL = int(os.getenv("MEMORY_CACHE_TTL", "300"))
TOP_K = int(os.getenv("TOP_K", "8"))

# 路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_DIR = os.path.join(BASE_DIR, "memory_data")
os.makedirs(MEMORY_DIR, exist_ok=True)

# --- Performance Monitor ---
class PerformanceMonitor:
    def __init__(self):
        self.metrics = {}
        self.current_session = None

    def start_session(self, session_id: str):
        self.current_session = session_id
        self.metrics[session_id] = {
            "start_time": time.time(),
            "nodes": {},
            "llm_calls": [],
            "total_tokens": 0
        }

    def record_node(self, node_name: str, duration: float):
        if self.current_session:
            if node_name not in self.metrics[self.current_session]["nodes"]:
                self.metrics[self.current_session]["nodes"][node_name] = []
            self.metrics[self.current_session]["nodes"][node_name].append(duration)

    def record_llm_call(self, purpose: str, duration: float, tokens: int = 0):
        if self.current_session:
            self.metrics[self.current_session]["llm_calls"].append({
                "purpose": purpose,
                "duration": duration,
                "tokens": tokens,
                "timestamp": time.time()
            })
            self.metrics[self.current_session]["total_tokens"] += tokens

    def end_session(self) -> Dict[str, Any]:
        if not self.current_session:
            return {}
        session_data = self.metrics[self.current_session]
        total_time = time.time() - session_data["start_time"]
        node_stats = {}
        for node, durations in session_data["nodes"].items():
            node_stats[node] = {
                "count": len(durations),
                "total_time": sum(durations),
                "avg_time": sum(durations) / len(durations),
                "percentage": (sum(durations) / total_time * 100) if total_time > 0 else 0
            }
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

perf_monitor = PerformanceMonitor()

def monitor_performance(node_name: str):
    """装饰器工厂，用于包裹节点函数"""
    def decorator(func):
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
            except Exception:
                duration = time.time() - start_time
                perf_monitor.record_node(f"{node_name}_ERROR", duration)
                raise
        return wrapper
    return decorator


RESPONSE_TEMPLATES = {
    "error_api": "抱歉，我在与我的核心模型通信时遇到了问题。请稍后再试。",
    "error_rag": "抱歉，我在检索课程信息时遇到了内部错误。我已经记录了这个问题。",
    "error_tool": "抱歉，在尝试执行一个工具时发生了错误。",
    "error_grounding": "我找到了相关信息，但在生成确认无误的答案时遇到了困难。为避免提供错误信息，我无法回答这个问题。",
    "fallback_no_rag_docs": "我在知识库中没有找到关于您问题的具体信息，但我会尽力根据通用知识来回答。"
}

# 动态加载 tools 包中的工具（如果可用）
try:
    # 尝试包内导入（优先）
    from .tools import get_tools
    TOOL_REGISTRY = get_tools()
except Exception:
    # 兼容旧路径导入
    try:
        from tools import get_tools
        TOOL_REGISTRY = get_tools()
    except Exception:
        TOOL_REGISTRY = {}
        if ENABLE_VERBOSE_LOGGING:
            print("⚠️  Warning: No tools loaded. 'tools' package not found or failed to load.")

# --- Chat State Type ---
class ChatState(TypedDict):
    messages: Annotated[list, add_messages]
    query: str
    user_id: Optional[str]
    route: Optional[Literal["retrieve_rag", "call_tool", "needs_clarification", "general_chat"]]
    tool_name: Optional[str]
    tool_args: Optional[dict]
    tool_call_id: Optional[str]
    retrieved: Optional[List[dict]]
    answer: Optional[str]
    is_grounded: Optional[bool]
    final_output: Optional[Dict[str, Any]]
    memory: Optional[Dict[str, Any]]
    enable_grounding: Optional[bool]
    enable_suggestions: Optional[bool]

# --- Qwen 调用（支持流式与非流式） ---
def _messages_to_dicts(messages):
    if not messages:
        return []
    if isinstance(messages[0], dict):
        return messages
    dict_messages = []
    for msg in messages:
        if hasattr(msg, 'type') and hasattr(msg, 'content'):
            if msg.type == 'human':
                dict_messages.append({'role': 'user', 'content': msg.content})
            elif msg.type == 'ai':
                dict_messages.append({'role': 'assistant', 'content': msg.content})
    return dict_messages

def call_qwen_sync(messages: list,
                   model: Optional[str] = None,
                   system_prompt: Optional[str] = None,
                   purpose: str = "general",
                   base_url: Optional[str] = None,
                   api_key: Optional[str] = None,
                   stream: bool = True,
                   **kwargs) -> Union[str, Iterator[str]]:
    print("!!!!!!!!!!!!!!messages in call_qwen_sync:", messages)
    start_time = time.time()
    safe_messages = []
    for m in _messages_to_dicts(messages):
        if m.get("role") in ("user", "assistant") and m.get("content"):
            safe_messages.append({"role": m["role"], "content": m["content"]})
    final_messages = ([{"role": "system", "content": system_prompt}] + safe_messages) if system_prompt else safe_messages
    url = (base_url or QWEN_BASE_URL).rstrip("/") + "/chat/completions"
    key = api_key or API_KEY
    payload = {"model": model or QWEN_MODEL, "messages": final_messages, **kwargs}
    if stream:
        payload["stream"] = True
        def stream_generator():
            tokens = 0
            response = None
            try:
                response = requests.post(
                    url,
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=60,
                    stream=True
                )
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    decoded_line = line.decode("utf-8").strip()
                    if decoded_line.startswith("data:"):
                        content = decoded_line[5:].strip()
                        if content == "[DONE]":
                            break
                        yield content
                        try:
                            chunk = json.loads(content)
                            if chunk.get("usage"):
                                tokens = chunk["usage"].get("total_tokens", 0)
                        except Exception:
                            pass
            except requests.exceptions.RequestException as e:
                if ENABLE_VERBOSE_LOGGING:
                    traceback.print_exc()
                yield json.dumps({"error": "API_ERROR", "message": str(e)}, ensure_ascii=False)
            finally:
                if response is not None:
                    response.close()
                duration = time.time() - start_time
                perf_monitor.record_llm_call(purpose, duration, tokens)
        return stream_generator()
    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=45
        )
        
        response.raise_for_status()
        result = response.json()
        duration = time.time() - start_time
        tokens = result.get("usage", {}).get("total_tokens", 0)
        perf_monitor.record_llm_call(purpose, duration, tokens)
        print("!!!!!!!!!!!!!!result in call_qwen_sync:", result)
        return result['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        duration = time.time() - start_time
        perf_monitor.record_llm_call(f"{purpose}_ERROR", duration)
        if ENABLE_VERBOSE_LOGGING:
            traceback.print_exc()
        return json.dumps({"error": "API_ERROR", "message": str(e)}, ensure_ascii=False)

# 性能报告打印
def print_performance_summary(perf_report: Dict[str, Any]):
    print("\n" + "=" * 80)
    print("📊 PERFORMANCE SUMMARY")
    print("=" * 80)
    print(f"\n⏱️  Total Time: {perf_report['total_time']:.3f}s")
    print("\n📈 Node Performance:")
    for node, stats in sorted(perf_report['node_stats'].items(), key=lambda x: x[1]['total_time'], reverse=True):
        print(f"  {node:20s}: {stats['total_time']:.3f}s ({stats['percentage']:.1f}%) [{stats['count']} calls, avg: {stats['avg_time']:.3f}s]")
    print("\n🤖 LLM Call Statistics:")
    llm_stats = perf_report['llm_stats']
    print(f"  Total Calls: {llm_stats['total_calls']}")
    print(f"  Total Time: {llm_stats['total_time']:.3f}s")
    print(f"  Total Tokens: {llm_stats['total_tokens']}")
    print("\n  By Purpose:")
    for purpose, stats in sorted(llm_stats['by_purpose'].items(), key=lambda x: x[1]['total_time'], reverse=True):
        avg_time = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
        print(f"    {purpose:15s}: {stats['count']} calls, {stats['total_time']:.3f}s (avg: {avg_time:.3f}s)")
    print("\n" + "=" * 80)
