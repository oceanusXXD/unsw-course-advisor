# core.py (重构清理版)
import os
import time
import json
import traceback
import inspect 
from functools import wraps
import httpx
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Iterator, Callable, AsyncIterator
import threading
import requests
from dotenv import load_dotenv
from .schemas import RetrievedDocument
from langchain_core.messages import BaseMessage
import re
import random
load_dotenv()

# =========================
# Config (保持不变)
# =========================
import asyncio
_GLOBAL_HTTP_CLIENT: Optional[httpx.AsyncClient] = None
_CLIENT_LOCK = asyncio.Lock()
_LLM_SEMAPHORE: Optional[asyncio.Semaphore] = None
_SEM_LOCK = asyncio.Lock()

QWEN_BASE_URL = os.getenv("QWEN_BASE_URL")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-max")
GROUNDING_MODEL = os.getenv("GROUNDING_MODEL", "qwen-plus-latest")
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "qwen-plus-latest")
API_KEY = os.getenv("DASHSCOPE_API_KEY")

USE_FAST_ROUTER = os.getenv("USE_FAST_ROUTER", "false").lower() == "true"

ENABLE_GROUNDING_CHECK = os.getenv("ENABLE_GROUNDING_CHECK", "false").lower() == "true"
ENABLE_SUGGESTIONS = os.getenv("ENABLE_SUGGESTIONS", "false").lower() == "true"
ENABLE_VERBOSE_LOGGING = os.getenv("ENABLE_VERBOSE_LOGGING", "true").lower() == "true"

MAX_MEMORY_MESSAGES = int(os.getenv("MAX_MEMORY_MESSAGES", "20"))
MEMORY_CACHE_TTL = int(os.getenv("MEMORY_CACHE_TTL", "300"))
TOP_K = int(os.getenv("TOP_K", "8"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
#MEMORY_DIR = os.path.join(BASE_DIR, "memory_data")
#os.makedirs(MEMORY_DIR, exist_ok=True)

MAX_HISTORY_LENGTH = int(os.getenv("MAX_HISTORY_LENGTH", "10"))
MAX_ANSWER_LENGTH = int(os.getenv("MAX_ANSWER_LENGTH", "200"))
KEEP_FULL_RECENT = int(os.getenv("KEEP_FULL_RECENT", "5"))
LLM_MAX_CONCURRENCY = int(os.getenv("LLM_MAX_CONCURRENCY", "20"))  # 并发阈值（每进程）
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "5"))           # 最大重试次数
LLM_RETRY_BASE = float(os.getenv("LLM_RETRY_BASE", "0.5"))         # 初始退避秒
LLM_RETRY_MAX = float(os.getenv("LLM_RETRY_MAX", "10.0"))          # 单次最大等待秒
# =========================
# StreamBus (保持不变)
# =========================
_STREAM_SINKS: Dict[str, Callable[[str], None]] = {}
_STREAM_LOCK = threading.Lock()

def register_stream_sink(session_id: str, sink: Callable[[str], None]):
    with _STREAM_LOCK:
        _STREAM_SINKS[session_id] = sink
    if ENABLE_VERBOSE_LOGGING:
        print(f"[StreamBus] register sink for session={session_id}")

def unregister_stream_sink(session_id: str):
    with _STREAM_LOCK:
        _STREAM_SINKS.pop(session_id, None)
    if ENABLE_VERBOSE_LOGGING:
        print(f"[StreamBus] unregister sink for session={session_id}")

def emit_stream_token(session_id: str, token: str):
    sink = None
    with _STREAM_LOCK:
        sink = _STREAM_SINKS.get(session_id)
    if not sink:
        if ENABLE_VERBOSE_LOGGING:
            print(f"[StreamBus] no sink for session={session_id}, drop token: {token[:40]!r}")
        return
    try:
        sink(token)
    except Exception:
        if ENABLE_VERBOSE_LOGGING:
            traceback.print_exc()

# =========================
# Performance Monitor (保持不变)
# =========================
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
            "total_tokens": 0,
        }

    def record_node(self, node_name: str, duration: float):
        if not self.current_session:
            return
        self.metrics[self.current_session]["nodes"].setdefault(node_name, []).append(duration)

    def record_llm_call(self, purpose: str, duration: float, tokens: int = 0):
        if not self.current_session:
            return
        session = self.metrics[self.current_session]
        session["llm_calls"].append({
            "purpose": purpose,
            "duration": duration,
            "tokens": tokens,
            "timestamp": time.time(),
        })
        session["total_tokens"] += tokens

    def end_session(self) -> Dict[str, Any]:
        if not self.current_session:
            return {}
        session_id = self.current_session
        session_data = self.metrics[session_id]
        total_time = time.time() - session_data["start_time"]
        node_stats = {
            node: {
                "count": len(durations),
                "total_time": sum(durations),
                "avg_time": sum(durations) / len(durations),
                "percentage": (sum(durations) / total_time * 100) if total_time > 0 else 0,
            }
            for node, durations in session_data["nodes"].items()
        }
        llm_calls = session_data["llm_calls"]
        llm_stats = {
            "total_calls": len(llm_calls),
            "total_time": sum(c["duration"] for c in llm_calls),
            "total_tokens": session_data["total_tokens"],
            "by_purpose": {},
        }
        for call in llm_calls:
            purpose = call["purpose"]
            llm_stats["by_purpose"].setdefault(purpose, {"count": 0, "total_time": 0})
            llm_stats["by_purpose"][purpose]["count"] += 1
            llm_stats["by_purpose"][purpose]["total_time"] += call["duration"]
        report = {
            "session_id": session_id,
            "total_time": total_time,
            "node_stats": node_stats,
            "llm_stats": llm_stats,
            "timestamp": datetime.now().isoformat(),
        }
        self.current_session = None
        return report

perf_monitor = PerformanceMonitor()

def monitor_performance(node_name: str):
    """
    支持同步和异步函数的性能监控装饰器
    
    关键：使用 inspect.iscoroutinefunction 而不是 asyncio.iscoroutinefunction
    """
    def decorator(func):
        # 更可靠的异步检测方式
        is_async = inspect.iscoroutinefunction(func)
        
        if ENABLE_VERBOSE_LOGGING:
            print(f"[Monitor] Wrapping {node_name}: is_async={is_async}, func={func.__name__}")
        
        if is_async:
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    perf_monitor.record_node(node_name, duration)
                    if ENABLE_VERBOSE_LOGGING:
                        print(f"[Timer] [{node_name}] (async) completed in {duration:.3f}s")
                    return result
                except Exception:
                    duration = time.time() - start_time
                    perf_monitor.record_node(f"{node_name}_ERROR", duration)
                    raise
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    perf_monitor.record_node(node_name, duration)
                    if ENABLE_VERBOSE_LOGGING:
                        print(f"[Timer] [{node_name}] (sync) completed in {duration:.3f}s")
                    return result
                except Exception:
                    duration = time.time() - start_time
                    perf_monitor.record_node(f"{node_name}_ERROR", duration)
                    raise
            return sync_wrapper
    return decorator
def build_history_str(history: List[BaseMessage], max_turns: int = 5) -> str:
    """
    从 BaseMessage 对象列表中构建历史对话字符串。
    """
    if not history:
        return "(无历史对话)"
    
    # 获取最近的 N*2 条消息
    recent_messages = history[-max_turns * 2:]
    lines = []
    for msg in recent_messages:
        # 使用 msg 对象的属性，而不是解析字典
        role = getattr(msg, "type", "unknown")
        # 将 LangChain 的类型映射为 user/assistant
        role_map = {"human": "user", "ai": "assistant"}
        display_role = role_map.get(role, role)
        
        content = getattr(msg, "content", "")
        # 清理内容中的换行符等
        content_str = " ".join(str(content).split())
        lines.append(f"{display_role}: {content_str}")
        
    return "\n".join(lines)

def create_docs_summary(docs: List[RetrievedDocument], max_docs: int = 3) -> str:
    """
    从强类型的 RetrievedDocument 列表中创建文档摘要。
    """
    if not docs:
        return "(无检索文档)"
    
    summary_list = []
    for i, doc in enumerate(docs[:max_docs]):
        try:
            # 直接使用强类型字段 _text
            content = doc["_text"]
            snippet = content[:300].replace("\n", " ").strip()
            if len(content) > 300:
                snippet += "..."
            summary_list.append(f"[Doc] 文档 {i+1}: {snippet}")
        except (KeyError, TypeError) as e:
            if ENABLE_VERBOSE_LOGGING:
                print(f"[WARN] [create_docs_summary] 文档 {i+1} 解析失败: {e}")
            summary_list.append(f"[WARN] 文档 {i+1}: (解析失败)")
            
    return "\n".join(summary_list)

def extract_course_codes(text: str) -> list[str]:
    if not isinstance(text, str): return []
    return sorted(list(set(re.findall(r"\b[A-Z]{4}\d{4}\b", text.upper()))))

def is_planning_query(q: str) -> bool:
    q = (q or "").lower()
    patterns = ["选什么课","怎么选","推荐选","能选","可以选","我能选什么","下学期","下个学期","怎么安排"]
    return any(p in q for p in patterns)

def is_file_generation_request(query: str) -> bool:
    if not isinstance(query, str):
        return False
    q = query.lower()
    strong = any(k in q for k in ["生成", "导出", "文件", "一键", "自动", "export", "file"])
    domain = any(k in q for k in ["选课", "课程", "course", "enrol", "enroll", "enrolment", "enrollment"])
    return strong and domain

def _messages_to_dicts(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    """
    将 BaseMessage 对象列表转换为 Qwen API 需要的字典列表。
    """
    if not messages:
        return []
    
    dict_messages = []
    for msg in messages:
        if not isinstance(msg, BaseMessage):
            # 处理可能混入的裸字典
            if isinstance(msg, dict) and "role" in msg:
                dict_messages.append(msg)
            continue
            
        role = getattr(msg, "type", "unknown")
        content = getattr(msg, "content", "")
        
        if role == "human":
            dict_messages.append({"role": "user", "content": content})
        elif role == "ai":
            ai_dict = {"role": "assistant", "content": content}
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                ai_dict["tool_calls"] = msg.tool_calls
                if not content:
                    ai_dict["content"] = None
            dict_messages.append(ai_dict)
        elif role == "system":
            dict_messages.append({"role": "system", "content": content})
        elif role == "tool":
            tool_dict = {"role": "tool", "content": content}
            if hasattr(msg, "tool_call_id") and msg.tool_call_id:
                tool_dict["tool_call_id"] = msg.tool_call_id
            dict_messages.append(tool_dict)
            
    return dict_messages

def build_context_string(retrieved: List[RetrievedDocument]) -> str:
    """
    [公共函数] 将强类型的 RetrievedDocument 列表格式化为字符串上下文。
    """
    if not retrieved:
        return "无上下文。"
    
    context_parts = []
    for i, doc in enumerate(retrieved):
        try:
            # 直接访问强类型字段
            text = doc["_text"]
            url = doc.get("source_url", "")
            title = doc.get("title", f"来源 {i+1}")
            
            source_identifier = title if title != f"来源 {i+1}" else url or f"来源 {i+1}"
            
            context_parts.append(f"--- 来源 {i+1} ({source_identifier}) ---\n{text}\n")
        except (KeyError, TypeError):
            # 降级处理，以防传入了不规范的字典
            context_parts.append(f"--- 来源 {i+1} ---\n{str(doc)}\n")

    return "\n".join(context_parts)
# =========================
# Single entrypoint: run
# =========================

def call_qwen(
    messages: List[Any],
    *,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    purpose: str = "general",
    stream: bool = False,
    temperature: float = 0.7,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[str] = "auto",
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs,
) -> Union[Iterator[str], Dict[str, Any]]:
    """
    统一入口：(已简化，不再支持 native_tool_loop)
    - stream=True  -> 返回迭代器（逐条 JSON chunk 字符串）
    - stream=False -> 返回标准 message 字典（可能包含 tool_calls）
    """

    def _print_payload_debug(prefix: str, payload: Dict[str, Any], response_text: Optional[str] = None):
        if not ENABLE_VERBOSE_LOGGING:
            return
        try:
            msgs = payload.get("messages", [])
            preview = msgs[-4:] if isinstance(msgs, list) else msgs
            print(f"[Qwen API][{prefix}] payload.messages(last 4): {json.dumps(preview, ensure_ascii=False)[:800]}")
            if "tools" in payload and payload.get("tools"):
                tool_names = [t["function"]["name"] for t in payload["tools"] if isinstance(t, dict) and t.get("function")]
                print(f"[Qwen API][{prefix}] tools: {tool_names}")
            if response_text is not None:
                print(f"[Qwen API][{prefix}] response body: {response_text[:1000]}")
        except Exception:
            traceback.print_exc()

    def _http_call(payload: Dict[str, Any], stream_mode: bool):
        url = (base_url or QWEN_BASE_URL).rstrip("/") + "/chat/completions"
        key = api_key or API_KEY

        if stream_mode:
            payload["stream"] = True

            def stream_generator():
                response = None
                try:
                    response = requests.post(
                        url,
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=60,
                        stream=True,
                    )
                    if response.status_code >= 400:
                        body = ""
                        try:
                            body = response.text
                        except Exception:
                            pass
                        _print_payload_debug("HTTP-ERROR(stream)", payload, body)
                        yield json.dumps({"error": f"HTTP_{response.status_code}", "message": body[:500]}, ensure_ascii=False)
                        return

                    if ENABLE_VERBOSE_LOGGING:
                        print(f"[Qwen API] Response status: {response.status_code}")

                    for line in response.iter_lines():
                        if not line:
                            continue
                        decoded_line = line.decode("utf-8").strip()
                        if decoded_line.startswith("data:"):
                            content = decoded_line[5:].strip()
                            if content == "[DONE]":
                                break
                            yield content
                except requests.exceptions.RequestException as e:
                    if ENABLE_VERBOSE_LOGGING:
                        traceback.print_exc()
                    try:
                        resp = getattr(e, "response", None)
                        body = resp.text if resp is not None else ""
                        _print_payload_debug("EXCEPTION(stream)", payload, body)
                    except Exception:
                        pass
                    yield json.dumps({"error": "API_ERROR", "message": str(e)}, ensure_ascii=False)
                finally:
                    if response is not None:
                        try:
                            response.close()
                        except Exception:
                            pass
            return stream_generator()

        else:
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60,
            )
            if response.status_code >= 400:
                _print_payload_debug("HTTP-ERROR(non-stream)", payload, response.text)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]

    dict_messages = _messages_to_dicts(messages)
    # --------- 规整消息 + 无 tools 时的历史清洗（保持不变）---------

    if not tools:
        sanitized: List[Dict[str, Any]] = []
        for m in dict_messages:
            role = m.get("role")
            if role == "tool" or (role == "assistant" and m.get("tool_calls")):
                if role == "assistant" and m.get("content"): # 保留 assistant 的文本内容
                    sanitized.append({"role": "assistant", "content": m["content"]})
                continue
            if m.get("content") is None and role != "system":
                continue
            sanitized.append(m)
        if ENABLE_VERBOSE_LOGGING:
            print(f"[Sanitize] No tools supplied -> dropped {len(dict_messages) - len(sanitized)} tool/tool_calls messages")
        dict_messages = sanitized

    # --- 构建 payload ---
    payload = {
        "model": model or QWEN_MODEL,
        "messages": ([{"role": "system", "content": system_prompt}] + dict_messages) if system_prompt else dict_messages,
        "temperature": temperature,
        **kwargs,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice

    if ENABLE_VERBOSE_LOGGING:
        print(f"!!!!!!!!!!!!!!Calling Qwen with {len(dict_messages)} messages for purpose: {purpose}")

    return _http_call(payload, stream_mode=stream)



async def get_http_client() -> httpx.AsyncClient:
    """获取全局 HTTP 客户端（单例模式）"""
    global _GLOBAL_HTTP_CLIENT
    
    if _GLOBAL_HTTP_CLIENT is not None and not _GLOBAL_HTTP_CLIENT.is_closed:
        return _GLOBAL_HTTP_CLIENT
    
    async with _CLIENT_LOCK:
        if _GLOBAL_HTTP_CLIENT is not None and not _GLOBAL_HTTP_CLIENT.is_closed:
            return _GLOBAL_HTTP_CLIENT
        
        _GLOBAL_HTTP_CLIENT = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
            http2=True  # 启用 HTTP/2（可选）
        )
        
        if ENABLE_VERBOSE_LOGGING:
            print("[OK] [HTTP Client] Global async client initialized")
        
        return _GLOBAL_HTTP_CLIENT

async def get_llm_semaphore() -> asyncio.Semaphore:
    global _LLM_SEMAPHORE
    if _LLM_SEMAPHORE is not None:
        return _LLM_SEMAPHORE
    async with _SEM_LOCK:
        if _LLM_SEMAPHORE is None:
            _LLM_SEMAPHORE = asyncio.Semaphore(LLM_MAX_CONCURRENCY)
            if ENABLE_VERBOSE_LOGGING:
                print(f"[OK] [LLM Limiter] Init semaphore with {LLM_MAX_CONCURRENCY}")
        return _LLM_SEMAPHORE

def _parse_retry_after(headers: dict[str, str]) -> float | None:
    val = headers.get("retry-after") or headers.get("Retry-After")
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        try:
            dt = datetime.strptime(val, "%a, %d %b %Y %H:%M:%S GMT")
            delay = (dt - datetime.utcnow()).total_seconds()
            return max(0.0, delay)
        except Exception:
            return None

def _compute_backoff(attempt: int, headers: dict[str, str] | None = None) -> float:
    # 优先尊重 Retry-After
    if headers:
        ra = _parse_retry_after(headers)
        if ra is not None:
            return min(max(ra, 0.1), LLM_RETRY_MAX)
    # 指数退避 + 抖动
    base = LLM_RETRY_BASE * (2 ** attempt)
    jitter = random.uniform(0, LLM_RETRY_BASE)
    return min(base + jitter, LLM_RETRY_MAX)

def _is_retryable_status(code: int) -> bool:
    # 可重试状态码
    return code in (429, 500, 502, 503, 504)
async def call_qwen_httpx(
    messages: List[Any],
    *,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    purpose: str = "general",
    stream: bool = False,
    temperature: float = 0.7,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[str] = "auto",
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs,
):
    """异步 LLM 调用：自动重试（429/5xx/网络瞬断）+ 并发限流（Semaphore）"""
    dict_messages = _messages_to_dicts(messages)

    # 清理消息（无工具时丢弃 tool/tool_calls）
    if not tools:
        sanitized: List[Dict[str, Any]] = []
        for m in dict_messages:
            role = m.get("role")
            if role == "tool" or (role == "assistant" and m.get("tool_calls")):
                if role == "assistant" and m.get("content"):
                    sanitized.append({"role": "assistant", "content": m["content"]})
                continue
            if m.get("content") is None and role != "system":
                continue
            sanitized.append(m)
        dict_messages = sanitized

    payload = {
        "model": model or QWEN_MODEL,
        "messages": ([{"role": "system", "content": system_prompt}] + dict_messages)
                    if system_prompt else dict_messages,
        "temperature": temperature,
        **kwargs,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice

    url = (base_url or QWEN_BASE_URL).rstrip("/") + "/chat/completions"
    key = api_key or API_KEY
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    client = await get_http_client()
    sem = await get_llm_semaphore()

    if stream:
        payload["stream"] = True

        async def stream_generator() -> AsyncIterator[str]:
            # 建连重试；一旦流建立，中途断流仅返回错误，避免复杂的续传
            for attempt in range(LLM_MAX_RETRIES + 1):
                try:
                    async with sem:  # gate 并发
                        async with client.stream("POST", url, headers=headers, json=payload) as response:
                            if response.status_code >= 400:
                                body = await response.aread()
                                code = response.status_code
                                if _is_retryable_status(code) and attempt < LLM_MAX_RETRIES:
                                    delay = _compute_backoff(attempt, dict(response.headers))
                                    if ENABLE_VERBOSE_LOGGING:
                                        print(f"[LLM Stream][{purpose}] HTTP {code}, retry {attempt+1}/{LLM_MAX_RETRIES} after {delay:.2f}s")
                                    await asyncio.sleep(delay)
                                    continue
                                if ENABLE_VERBOSE_LOGGING:
                                    print(f"[LLM Stream][{purpose}] HTTP {code} stop. Body: {body[:500]!r}")
                                yield json.dumps({"error": f"HTTP_{code}", "message": body.decode(errors='ignore')[:500]}, ensure_ascii=False)
                                return

                            async for line in response.aiter_lines():
                                if not line:
                                    continue
                                if line.startswith("data:"):
                                    content = line[5:].strip()
                                    if content == "[DONE]":
                                        break
                                    yield content
                            return  # 正常结束

                except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                    if attempt < LLM_MAX_RETRIES:
                        delay = _compute_backoff(attempt)
                        if ENABLE_VERBOSE_LOGGING:
                            print(f"[LLM Stream][{purpose}] Network {type(e).__name__}, retry {attempt+1}/{LLM_MAX_RETRIES} after {delay:.2f}s")
                        await asyncio.sleep(delay)
                        continue
                    yield json.dumps({"error": "STREAM_ERROR", "message": str(e)}, ensure_ascii=False)
                    return
                except Exception as e:
                    if ENABLE_VERBOSE_LOGGING:
                        traceback.print_exc()
                    yield json.dumps({"error": "STREAM_ERROR", "message": str(e)}, ensure_ascii=False)
                    return

            yield json.dumps({"error": "RETRY_EXHAUSTED", "message": f"Exceeded {LLM_MAX_RETRIES} retries"}, ensure_ascii=False)

        return stream_generator()

    else:
        # 非流式：请求级重试
        last_exc: Exception | None = None
        for attempt in range(LLM_MAX_RETRIES + 1):
            try:
                async with sem:
                    response = await client.post(url, headers=headers, json=payload)

                if response.status_code >= 400:
                    code = response.status_code
                    if _is_retryable_status(code) and attempt < LLM_MAX_RETRIES:
                        delay = _compute_backoff(attempt, dict(response.headers))
                        if ENABLE_VERBOSE_LOGGING:
                            print(f"[LLM][{purpose}] HTTP {code}, retry {attempt+1}/{LLM_MAX_RETRIES} after {delay:.2f}s")
                        await asyncio.sleep(delay)
                        continue
                    response.raise_for_status()

                result = response.json()
                return result["choices"][0]["message"]

            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                last_exc = e
                if attempt < LLM_MAX_RETRIES:
                    delay = _compute_backoff(attempt)
                    if ENABLE_VERBOSE_LOGGING:
                        print(f"[LLM][{purpose}] Network {type(e).__name__}, retry {attempt+1}/{LLM_MAX_RETRIES} after {delay:.2f}s")
                    await asyncio.sleep(delay)
                    continue
                break
            except httpx.HTTPStatusError as e:
                last_exc = e
                break
            except Exception as e:
                last_exc = e
                break

        if ENABLE_VERBOSE_LOGGING and last_exc:
            print(f"[LLM][{purpose}] Failed after retries: {type(last_exc).__name__}: {last_exc}")
        raise last_exc or RuntimeError("LLM call failed with no response")


# =========================
# Misc (保持不变)
# =========================
RESPONSE_TEMPLATES = {
    "error_api": "抱歉，我在与核心模型通信时遇到了问题，请稍后再试。",
    "error_rag": "抱歉，我在检索课程信息时遇到了内部错误，已记录问题。",
    "error_tool": "抱xA歉，执行工具时发生错误。",
    "error_grounding": "找到相关信息，但无法确认答案正确性，为避免误导暂不回答。",
    "fallback_no_rag_docs": "知识库中暂无相关信息，我将根据通用知识尝试回答。",
}

# =========================
# Tool helpers (保留 parse_tool_arguments)
# =========================
def parse_tool_arguments(arguments: Union[str, Dict[str, Any], None]) -> Dict[str, Any]:
    """
    解析 Function Calling 返回的 arguments：
    (这个函数仍然被 router.py 使用)
    """
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            if ENABLE_VERBOSE_LOGGING:
                print(f"[ERR] parse_tool_arguments: invalid JSON: {arguments[:200]}")
            return {}
    return {}

def print_performance_summary(perf_report: Dict[str, Any]):
    # (保持不变)
    print("\n" + "=" * 80)
    print("[Stats] PERFORMANCE SUMMARY")
    print("=" * 80)
    print(f"\n[Timer] Total Time: {perf_report['total_time']:.3f}s")
    print("\n[Perf] Node Performance:")
    for node, stats in sorted(
        perf_report["node_stats"].items(), key=lambda x: x[1]["total_time"], reverse=True
    ):
        print(
            f"  {node:20s}: {stats['total_time']:.3f}s "
            f"({stats['percentage']:.1f}%) "
            f"[{stats['count']} calls, avg: {stats['avg_time']:.3f}s]"
        )
    print("\n[LLM] LLM Call Statistics:")
    llm_stats = perf_report["llm_stats"]
    print(f"  Total Calls: {llm_stats['total_calls']}")
    print(f"  Total Time: {llm_stats['total_time']:.3f}s")
    print(f"  Total Tokens: {llm_stats['total_tokens']}")
    print("\n  By Purpose:")
    for p, stats in sorted(
        llm_stats["by_purpose"].items(), key=lambda x: x[1]["total_time"], reverse=True
    ):
        avg_time = stats["total_time"] / stats["count"] if stats["count"] > 0 else 0
        print(f"    {p:15s}: {stats['count']} calls, {stats['total_time']:.3f}s (avg: {avg_time:.3f}s)")
    print("\n" + "=" * 80)