# main_graph.py
import os
import sys
import time
import json
import threading
import traceback
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, List,Optional
from datetime import datetime
import asyncio
import uuid
from .timeline_store import append as timeline_append
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))
from .config_loader import load_graph_from_config
from .state import ChatState
from .core import (
    monitor_performance, perf_monitor, ENABLE_VERBOSE_LOGGING,
    register_stream_sink, unregister_stream_sink,extract_course_codes
)
import asyncio

from .schemas import StudentInfo
try:
    from .node.save_memory import load_memory_structure, save_memory_structure
except ImportError:
    from node.save_memory import load_memory_structure, save_memory_structure

CFG_PATH = os.path.join(os.path.dirname(__file__), "nodes_config.yaml")
_COMPILED_GRAPH = None
_GRAPH_LOCK = asyncio.Lock()


async def build_and_compile_graph(force_rebuild: bool = False):
    """编译 LangGraph 图"""
    global _COMPILED_GRAPH
    
    # 添加调试信息
    pid = os.getpid()
    
    if _COMPILED_GRAPH is not None and not force_rebuild:
        if ENABLE_VERBOSE_LOGGING:
            print(f"[PID {pid}] Using cached graph")
        return _COMPILED_GRAPH
    
    async with _GRAPH_LOCK:
        if _COMPILED_GRAPH is not None and not force_rebuild:
            return _COMPILED_GRAPH
        try:
            if ENABLE_VERBOSE_LOGGING:
                print(f"[PID {pid}] [BUILD] Compiling graph from config: {CFG_PATH}")
            
            graph_builder = load_graph_from_config(
                CFG_PATH, ChatState
            )
            compiled = graph_builder.compile()
            _COMPILED_GRAPH = compiled
            
            if ENABLE_VERBOSE_LOGGING:
                print(f"[PID {pid}] [OK] Graph compiled successfully")
            
            return _COMPILED_GRAPH
        except Exception as e:
            if ENABLE_VERBOSE_LOGGING:
                traceback.print_exc()
                print(f"[ERR] Failed to compile graph: {e}")
            _COMPILED_GRAPH = None
            return None
def _ensure_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        return [v]
    return [str(v)]


def _apply_long_term_to_student_info(
    student_info: StudentInfo,  # 改为 StudentInfo 类型
    long_term_summary: Any
) -> StudentInfo:  # 返回 StudentInfo 类型
    """将长期记忆（JSON 或字符串）合并到 student_info（只增不改，去重）"""
    
    # 创建副本，确保类型正确
    si: StudentInfo = dict(student_info or {})  # type: ignore
    
    # 解析 long_term_summary（优先 JSON）
    data = None
    if isinstance(long_term_summary, dict):
        data = long_term_summary
    else:
        try:
            data = json.loads(long_term_summary) if long_term_summary else None
            if not isinstance(data, dict):
                data = None
        except Exception:
            data = None
    
    if not data:
        return si  # 非 JSON 时，直接跳过，保持简洁

    # 1) 合并列表字段（按 student_info 可能存在的字段）
    for key in ("preferences", "constraints", "goals"):
        merged = []
        seen = set()
        for x in _ensure_list(si.get(key)) + _ensure_list(data.get(key)):
            s = str(x).strip()
            if not s or s in seen:
                continue
            seen.add(s)
            merged.append(s)
        if merged:
            si[key] = merged  # type: ignore

    # 2) 合并课程画像：从 skills / preferences / goals 等提取课程代码，加入 completed_courses
    code_sources: List[str] = []
    for k in ("skills", "preferences", "goals"):
        for item in _ensure_list(data.get(k)):
            code_sources.extend(extract_course_codes(str(item)) or [])
    
    if code_sources:
        # 确保 completed_courses 是列表类型
        existing = set(si.get("completed_courses") or [])
        for c in code_sources:
            if c not in existing:
                existing.add(c)
        si["completed_courses"] = list(existing)

    # 3) 合并 all_major_courses（如果存在）
    if "all_major_courses" in data:
        # 确保字段存在且类型正确
        existing_courses = set(si.get("all_major_courses") or [])
        new_courses = _ensure_list(data.get("all_major_courses"))
        existing_courses.update(new_courses)
        si["all_major_courses"] = list(existing_courses)

    return si  # 返回 StudentInfo 类型


async def run_chat(
    query: str,
    user_id: str = "anonymous",
    frontend_state: Dict[str, Any] = None,
    tab_id: Optional[str] = None,
    cancel_event: Optional[asyncio.Event] = None,  # 已有参数
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    运行聊天流程的主函数，使用强类型 ChatState。
    支持通过 cancel_event 中止生成。
    """
    if frontend_state is None:
        frontend_state = {}

    compiled = await build_and_compile_graph()
    if compiled is None:
        yield {"event": "error", "data": {"message": "Graph 未能成功编译"}}
        return

    run_id = time.time()
    session_id = str(run_id)
    turn_id = f"{int(run_id*1000)}-{uuid.uuid4().hex[:8]}"

    if ENABLE_VERBOSE_LOGGING:
        print("\n" + "=" * 60)
        print("【RunChat】启动 (强类型版本)")
        print(f"  - User: {user_id}, Query: '{query[:50]}...'")
        print(f"  - SessionId: {session_id}, TurnId: {turn_id}, TabId: {tab_id}")
        print("=" * 60 + "\n")

    perf_monitor.start_session(f"{user_id}_{int(run_id*1000)}")

    # 1. 初始状态
    initial_state = ChatState(
        query=query,
        user_id=user_id,
        turn_id=turn_id,
        run_id=run_id,
        stream=True,
    )

    # 2. 恢复前端状态（保持不变）
    initial_state["messages"] = frontend_state.get("messages", [])
    initial_state["pending_file_generation"] = frontend_state.get("pending_file_generation")
    initial_state["pending_plugin_install"] = frontend_state.get("pending_plugin_install")
    initial_state["last_proposal_ts"] = frontend_state.get("last_proposal_ts") or 0.0
    initial_state["file_generation_declined"] = bool(frontend_state.get("file_generation_declined") or False)
    
    if "memory" in frontend_state and frontend_state["memory"]:
        initial_state.memory = frontend_state["memory"]
    elif tab_id:
        try:
            from chatbot.langgraph_agent.node.save_memory import load_memory_structure_async
            initial_state.memory = await load_memory_structure_async(user_id, tab_id)
        except Exception:
            if ENABLE_VERBOSE_LOGGING:
                traceback.print_exc()
    
    if "student_info" in frontend_state:
        initial_state.student_info = frontend_state["student_info"]
    
    try:
        lt = (initial_state.memory or {}).get("long_term_summary")
        if lt:
            initial_state.student_info = _apply_long_term_to_student_info(
                initial_state.student_info or {}, lt
            )
            if ENABLE_VERBOSE_LOGGING:
                print(f"[RunChat] student_info merged with long_term_summary.")
    except Exception:
        if ENABLE_VERBOSE_LOGGING:
            traceback.print_exc()

    # 3. 队列
    token_queue: asyncio.Queue[str] = asyncio.Queue()
    events_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
    
    def sink(token: str):
        """同步回调 -> 异步队列"""
        try:
            asyncio.get_running_loop().call_soon_threadsafe(
                token_queue.put_nowait, token
            )
        except RuntimeError:
            pass

    register_stream_sink(session_id, sink)

    # 4. Graph Worker 任务
    final_state_from_graph: Dict[str, Any] = {}
    graph_done = asyncio.Event()
    was_cancelled = False  # 标记是否被取消

    async def graph_worker():
        nonlocal final_state_from_graph, was_cancelled
        try:
            accumulated_state = dict(initial_state)
            
            async for update_chunk in compiled.astream(initial_state, stream_mode="updates"):
                # 检查是否需要取消
                if cancel_event and cancel_event.is_set():
                    if ENABLE_VERBOSE_LOGGING:
                        print(f"[RunChat] [WARN] Graph worker cancelled (turn_id={turn_id})")
                    was_cancelled = True
                    break
                
                for node_name, node_output in update_chunk.items():
                    if isinstance(node_output, dict):
                        accumulated_state.update(node_output)
                        
                        # 处理 SSE 事件
                        evts: List[Dict[str, Any]] = node_output.get("sse_events", [])
                        for evt in evts:
                            if isinstance(evt, dict) and evt:
                                await events_queue.put(evt)
                        
                        # 处理路由轨迹
                        trail: List[Dict[str, Any]] = node_output.get("router_trail", [])
                        for entry in trail:
                            await asyncio.to_thread(timeline_append, turn_id, entry)
                            
                            if isinstance(entry, dict):
                                decision_event = {
                                    "event": "decision",
                                    "data": {
                                        "route": entry.get("route"),
                                        "reason": entry.get("reason"),
                                        "confidence": entry.get("confidence"),
                                        "tool_info": entry.get("tool_info"),
                                    }
                                }
                                await events_queue.put(decision_event)
            
            final_state_from_graph = accumulated_state
            
        except asyncio.CancelledError:
            # 任务被取消
            if ENABLE_VERBOSE_LOGGING:
                print(f"[RunChat] [WARN] Graph worker cancelled via asyncio.CancelledError")
            was_cancelled = True
            raise  # 重新抛出以确保任务正确取消
            
        except Exception as e:
            if ENABLE_VERBOSE_LOGGING:
                print(f"[ERR] graph_worker error: {e}")
                traceback.print_exc()
        finally:
            graph_done.set()

    # 启动异步任务
    graph_task = asyncio.create_task(graph_worker())

    # 5. 主循环：异步消费队列
    final_answer_streamed = ""
    try:
        # 首先发送 session_init 事件
        yield {"event": "session_init", "data": {"tab_id": tab_id, "turn_id": turn_id}}
        
        while not graph_done.is_set() or not token_queue.empty() or not events_queue.empty():
            # 检查是否需要取消
            if cancel_event and cancel_event.is_set():
                if ENABLE_VERBOSE_LOGGING:
                    print(f"[RunChat] [WARN] Main loop cancelled (turn_id={turn_id})")
                
                # 取消 graph 任务
                graph_task.cancel()
                
                # 发送取消事件
                yield {
                    "event": "cancelled",
                    "data": {
                        "turn_id": turn_id,
                        "tab_id": tab_id,
                        "message": "Generation cancelled by user"
                    }
                }
                break
            
            # 优先处理事件队列
            while not events_queue.empty():
                evt = events_queue.get_nowait()
                event_type = evt.get("event", "status")
                event_data = evt.get("data", {})

                if not isinstance(event_data, dict):
                    event_data = {"value": event_data}
                event_data.setdefault("turn_id", turn_id)
                if tab_id:
                    event_data.setdefault("tab_id", tab_id)

                yield {"event": event_type, "data": event_data}

            # 处理 token 队列
            try:
                token = await asyncio.wait_for(token_queue.get(), timeout=0.1)
                final_answer_streamed += token
                yield {"event": "token", "data": token}
            except asyncio.TimeoutError:
                pass
            
            # 让出控制权
            await asyncio.sleep(0)
            
    finally:
        unregister_stream_sink(session_id)
        
        # 等待 graph 任务完成（带超时）
        try:
            await asyncio.wait_for(graph_task, timeout=5.0)
        except asyncio.TimeoutError:
            if ENABLE_VERBOSE_LOGGING:
                print(f"[RunChat] [WARN] Graph task did not finish in time, force cancelling")
            graph_task.cancel()
        except asyncio.CancelledError:
            pass

    # 如果被取消，提前返回
    if was_cancelled or (cancel_event and cancel_event.is_set()):
        if ENABLE_VERBOSE_LOGGING:
            print(f"[RunChat] [OK] Gracefully exited after cancellation (turn_id={turn_id})")
        yield {"event": "end", "data": "Stream cancelled."}
        return

    # 6. 汇总最终状态
    final_state: ChatState = ChatState(**final_state_from_graph)

    if ENABLE_VERBOSE_LOGGING:
        print("\n" + "=" * 60)
        print("【最终状态】")
        print(f"  - Final Route: {final_state.route}")
        print(f"  - Final Answer Length: {len(final_state.answer or '')}")
        print("=" * 60 + "\n")

    final_answer = final_answer_streamed or final_state.answer or "抱歉，我没有生成答案。"

    user_message = {"role": "user", "content": query}
    assistant_message = {
        "role": "assistant",
        "content": final_answer,
        "metadata": {
            "retrieved_docs": final_state.retrieved_docs,
            "sources": final_state.sources,
            "citations": final_state.citations,
            "pending_file_generation": final_state.pending_file_generation,
            "pending_plugin_install": final_state.pending_plugin_install,
            "is_grounded": final_state.is_grounded,
        }
    }

    final_messages = initial_state.messages + [user_message, assistant_message]
    final_state_to_yield = {
        "messages": final_messages,
        "pending_file_generation": final_state.pending_file_generation,
        "pending_plugin_install": final_state.pending_plugin_install,
        "turn_id": turn_id,
        "tab_id": tab_id,
        "session_id": session_id,
        "last_proposal_ts": getattr(final_state, "last_proposal_ts", 0.0),
        "file_generation_declined": getattr(final_state, "file_generation_declined", False),
    }

    yield {"event": "final_state", "data": final_state_to_yield}

    # 7. 持久化记忆
    try:
        from chatbot.langgraph_agent.node.save_memory import (
            load_memory_structure_async,
            save_memory_structure_async
        )
        memory_on_disk: Dict[str, Any] = await load_memory_structure_async(user_id, tab_id)
        
        new_entry: Dict[str, Any] = {
            "Q": query,
            "A": final_answer,
            "T": datetime.now().isoformat(),
            "metadata": {
                "route": final_state.route,
                "turn_id": turn_id,
                "session_id": session_id,
                "tab_id": tab_id,
                "is_grounded": final_state.is_grounded,
                "source_count": len(final_state.sources or []),
            }
        }
        memory_on_disk["recent_conversations"].append(new_entry)

        if final_state.memory and final_state.memory.get("long_term_summary"):
            memory_on_disk["long_term_summary"] = final_state.memory["long_term_summary"]

        await save_memory_structure_async(user_id, tab_id, memory_on_disk)
        
        if ENABLE_VERBOSE_LOGGING:
            print("[OK] 最终状态已持久化")
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"[ERR] 持久化失败: {e}")
            traceback.print_exc()

    yield {"event": "end", "data": "Stream finished."}


async def warmup_graph():
    """
    预编译图，用于服务启动时加载。
    
    注意：调用此函数前，应该已经加载了所有依赖模块
    （如 parallel_search_and_rerank），避免重复初始化。
    """
    try:
        if ENABLE_VERBOSE_LOGGING:
            import os
            pid = os.getpid()
            print(f"[PID {pid}] [Warmup] 开始预编译图...")
        
        graph = await build_and_compile_graph(force_rebuild=False)
        
        if graph and ENABLE_VERBOSE_LOGGING:
            print(f"[PID {pid}] [OK] [Warmup] 图预编译成功")
        
        return graph
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"[WARN] [Warmup] 预编译失败: {e}")
            traceback.print_exc()
        return None
