# main_graph.py
import os
import threading
import traceback
import time
import json
import sys
from pathlib import Path

# 确保项目根加入路径（与之前逻辑一致）
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from .config_loader import load_graph_from_config
from .core import ChatState, monitor_performance, perf_monitor, ENABLE_VERBOSE_LOGGING
# 注意：不要直接依赖 core 中是否包含 MEMORY_DIR；我们优先使用 node_save_memory 来保存

CFG_PATH = os.path.join(os.path.dirname(__file__), "nodes_config.yaml")

# 全局缓存与锁，确保线程安全的单例编译
_COMPILED_GRAPH = None
_GRAPH_LOCK = threading.Lock()

def build_and_compile_graph(force_rebuild: bool = False):
    """
    线程安全的单例编译函数。
    首次调用会读取 CFG_PATH 并编译 graph，后续调用直接返回缓存。
    如果需要强制重建，传入 force_rebuild=True。
    返回编译结果（可能为 None，表示编译失败）。
    """
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is not None and not force_rebuild:
        if ENABLE_VERBOSE_LOGGING:
            print("[DEBUG] Returning cached _COMPILED_GRAPH")
        return _COMPILED_GRAPH

    with _GRAPH_LOCK:
        if _COMPILED_GRAPH is not None and not force_rebuild:
            if ENABLE_VERBOSE_LOGGING:
                print("[DEBUG] Returning cached _COMPILED_GRAPH after lock")
            return _COMPILED_GRAPH
        try:
            if ENABLE_VERBOSE_LOGGING:
                print(f"🔧 Compiling graph from config: {CFG_PATH}")
            graph_builder = load_graph_from_config(CFG_PATH, ChatState, monitor_wrapper=monitor_performance)
            compiled = graph_builder.compile()
            if compiled is None:
                if ENABLE_VERBOSE_LOGGING:
                    print("⚠️ Graph compile returned None. Check nodes_config.yaml and load_graph_from_config.")
            else:
                if ENABLE_VERBOSE_LOGGING:
                    print("✅ Graph compiled and cached.")
            _COMPILED_GRAPH = compiled
            return _COMPILED_GRAPH
        except Exception as e:
            if ENABLE_VERBOSE_LOGGING:
                traceback.print_exc()
                print(f"❌ Failed to compile graph: {e}")
            _COMPILED_GRAPH = None
            return None

def _safe_import_node_save_memory():
    """
    尝试多种导入路径获取 node_save_memory 函数，返回函数或 None。
    """
    try:
        # 优先尝试包外导入（如果脚本以包方式运行）
        from node.save_memory import node_save_memory
        return node_save_memory
    except Exception:
        pass
    try:
        # 相对导入（当作为包模块被 import 时）
        from .node.save_memory import node_save_memory
        return node_save_memory
    except Exception:
        pass
    if ENABLE_VERBOSE_LOGGING:
        print("⚠️ Could not import node_save_memory; final auto-save after stream will be skipped.")
    return None

def run_chat(query: str, user_id: str = "anonymous", init_messages=None):
    """
    更健壮的 run_chat：
    - 为每次调用注入 run_id，避免内部缓存导致节点不再执行
    - 兼容流式 answer（generator）或同步 answer（str）
    - 在流结束后主动调用 node_save_memory 将最终 final_answer 写入磁盘（如果可用）
    - 以 generator yield 事件：token/history/error/end
    """
    print("\n[DEBUG] ====== STARTING NEW CHAT SESSION ======")
    compiled = build_and_compile_graph()
    if compiled is None:
        yield {"type": "error", "data": {"message": "Graph 未能成功编译"}}
        return

    session_id = f"{user_id}_{int(time.time() * 1000)}"
    perf_monitor.start_session(session_id)

    # 尝试导入 save_memory 函数（用于流结束后的最终保存）
    node_save_memory = _safe_import_node_save_memory()

    try:
        # messages 统一为 list（init_messages 可能为 None 或已是 list）
        if init_messages is None:
            messages = []
        else:
            # 如果 init_messages 是 dict/str，尝试包裹；通常 init_messages 应为 list
            if isinstance(init_messages, list):
                messages = init_messages
            else:
                messages = [init_messages]

        # inputs 中加入 run_id 每次都不同，避免图框架缓存导致节点不执行
        inputs = {
            "query": query,
            "messages": messages,
            "user_id": user_id,
            "stream": True,
            "run_id": time.time(),  # 保证每次唯一
        }
        if ENABLE_VERBOSE_LOGGING:
            print("!!!!!!!!!!!!!!inputs:")

        # 调用编译后的图
        result = compiled.invoke(inputs)
        if ENABLE_VERBOSE_LOGGING:
            print("!!!!!!!!!!!!!!result:")

        final_answer = ""
        output_stream = result.get("answer")
        if ENABLE_VERBOSE_LOGGING:
            print("!!!!!!!!!output_stream:")

        # 如果 answer 是 generator/iterable，则逐步读取并 yield token
        # 兼容几种 chunk 类型：bytes / str / dict-like(JSON line)
        if output_stream is None:
            # 无输出流，尝试直接从 result 中取同步 answer 字段（可能为字符串）
            maybe_sync = result.get("answer_sync") or result.get("final_answer") or result.get("text") or result.get("answer_text")
            if isinstance(maybe_sync, str):
                final_answer = maybe_sync
                yield {"type": "token", "data": final_answer}
        else:
            try:
                # 假设 output_stream 是可迭代的 generator/iterator
                for chunk in output_stream:
                    # chunk 可能为 bytes、str、或 dict/object
                    if isinstance(chunk, bytes):
                        chunk = chunk.decode("utf-8", errors="ignore")
                    elif not isinstance(chunk, str):
                        # 如果是 dict 或其他对象，尽量转为字符串（JSON 行）
                        try:
                            chunk = json.dumps(chunk, ensure_ascii=False)
                        except Exception:
                            chunk = str(chunk)

                    # 每个 chunk 可能包含多行 JSON 或纯文本
                    for line in chunk.strip().splitlines():
                        if not line.strip():
                            continue
                        # 尝试解析为 JSON，提取 streaming delta.content
                        text_piece = None
                        try:
                            data = json.loads(line)
                            # 常见格式： {"choices":[{"delta":{"content":"..."}}]}
                            if isinstance(data, dict):
                                choices = data.get("choices")
                                if isinstance(choices, list) and len(choices) > 0:
                                    delta = choices[0].get("delta", {})
                                    if isinstance(delta, dict):
                                        text_piece = delta.get("content", "")
                                # 备用字段
                                if not text_piece:
                                    # 有时直接在 text/content 字段
                                    text_piece = data.get("text") or data.get("content") or ""
                        except Exception:
                            # 不是 JSON 行，直接把这一行当作文本片段
                            text_piece = line

                        if text_piece:
                            final_answer += text_piece
                            yield {"type": "token", "data": text_piece}
            except TypeError:
                # output_stream 可能不是可迭代对象（例如是单个字符串）
                if isinstance(output_stream, str):
                    final_answer = output_stream
                    yield {"type": "token", "data": final_answer}
                else:
                    # 不可处理类型，记录日志
                    if ENABLE_VERBOSE_LOGGING:
                        print("⚠️ output_stream is not iterable and not str; skipping streaming consumption.")
            except Exception as e:
                tb = traceback.format_exc()
                if ENABLE_VERBOSE_LOGGING:
                    print(f"❌ Error while iterating output_stream: {e}\n{tb}")
                yield {"type": "error", "data": {"message": str(e), "trace": tb}}

        # 流结束后，输出完整对话历史（包含 assistant 最终回答）
        assistant_entry = {"role": "assistant", "content": final_answer}
        final_history = messages + [assistant_entry]
        yield {"type": "history", "data": final_history}

        # ===== 在流结束后做一次最终保存：把完整 final_answer 写入 memory =====
        try:
            if node_save_memory:
                # 构造一个状态字典，符合 save_memory 函数预期
                state_for_save = {
                    "messages": final_history,
                    "query": query,
                    "user_id": user_id,
                    # 保留 route 信息
                    "route": result.get("route", "general_chat"),
                    "answer": final_answer,
                    "memory": result.get("memory", {}) or {},
                    "is_grounded": result.get("is_grounded", True),
                }
                if ENABLE_VERBOSE_LOGGING:
                    print("🟢 Calling node_save_memory with state:")
                try:
                    node_save_memory(state_for_save)
                    if ENABLE_VERBOSE_LOGGING:
                        print("🟢 Final answer saved by node_save_memory.")
                except Exception as e:
                    if ENABLE_VERBOSE_LOGGING:
                        print(f"⚠️ node_save_memory raised exception: {e}")
                        traceback.print_exc()
            else:
                if ENABLE_VERBOSE_LOGGING:
                    print("⚠️ node_save_memory not available; skipped final save.")
        except Exception as e:
            if ENABLE_VERBOSE_LOGGING:
                print(f"⚠️ Exception during final save step: {e}")
                traceback.print_exc()

    except Exception as e:
        tb = traceback.format_exc()
        if ENABLE_VERBOSE_LOGGING:
            print(f"❌ Error during run_chat: {e}\n{tb}")
        yield {"type": "error", "data": {"message": str(e), "trace": tb}}

    finally:
        if ENABLE_VERBOSE_LOGGING:
            print("✅ STREAMING SESSION COMPLETED")
        try:
            perf_monitor.end_session()
        except Exception:
            pass
        yield {"type": "end", "data": "Stream finished."}
