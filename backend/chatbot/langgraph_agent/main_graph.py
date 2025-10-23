# main_graph.py
import os
import sys
import time
import json
import threading
import traceback
from pathlib import Path
import collections.abc
# ==== 路径配置 ====
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from .config_loader import load_graph_from_config
from .core import ChatState, monitor_performance, perf_monitor, ENABLE_VERBOSE_LOGGING


# ==== 全局常量 ====
CFG_PATH = os.path.join(os.path.dirname(__file__), "nodes_config.yaml")

# ==== 全局缓存与锁 ====
_COMPILED_GRAPH = None
_GRAPH_LOCK = threading.Lock()


# ==== 图编译函数 ====
def build_and_compile_graph(force_rebuild: bool = False):
    """
    单例编译函数：
    - 第一次调用时从 CFG_PATH 构建并编译图；
    - 后续调用直接返回缓存；
    - force_rebuild=True 时强制重新构建。
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

            graph_builder = load_graph_from_config(
                CFG_PATH, ChatState, monitor_wrapper=monitor_performance
            )
            compiled = graph_builder.compile()

            if compiled is None:
                if ENABLE_VERBOSE_LOGGING:
                    print("Graph compile returned None. Check config file.")
            else:
                if ENABLE_VERBOSE_LOGGING:
                    print("Graph compiled and cached.")

            _COMPILED_GRAPH = compiled
            return _COMPILED_GRAPH

        except Exception as e:
            if ENABLE_VERBOSE_LOGGING:
                traceback.print_exc()
                print(f"❌ Failed to compile graph: {e}")
            _COMPILED_GRAPH = None
            return None


# ==== 尝试导入保存函数 ====
def _safe_import_node_save_memory():
    """兼容导入 node_save_memory，无则返回 None"""
    try:
        from node.save_memory import node_save_memory
        return node_save_memory
    except Exception:
        pass

    try:
        from .node.save_memory import node_save_memory
        return node_save_memory
    except Exception:
        pass

    if ENABLE_VERBOSE_LOGGING:
        print("⚠️ Could not import node_save_memory; final auto-save skipped.")
    return None


# ==== 主入口 ====
def run_chat(query: str, user_id: str = "anonymous", init_messages=None):
    """
    核心对话函数：
    - 每次运行注入唯一 run_id，防止缓存；
    - 支持流式输出（generator）与同步输出；
    - 流结束后调用 node_save_memory 保存完整上下文；
    - 输出事件类型：token / history / error / end。
    """
    print("\n[DEBUG] ====== STARTING NEW CHAT SESSION ======")
    compiled = build_and_compile_graph()
    if compiled is None:
        yield {"type": "error", "data": {"message": "Graph 未能成功编译"}}
        return

    session_id = f"{user_id}_{int(time.time() * 1000)}"
    perf_monitor.start_session(session_id)
    node_save_memory = _safe_import_node_save_memory()

    try:
        # ==== 预处理输入 ====
        messages = init_messages if isinstance(init_messages, list) else (
            [init_messages] if init_messages else []
        )

        inputs = {
            "query": query,
            "messages": messages,
            "user_id": user_id,
            "stream": True,
            "run_id": time.time(),
        }

        if ENABLE_VERBOSE_LOGGING:
            # (这是你原来的调试打印)
            print("!!!!!!!!!!!!!!inputs:")

        # ==== 调用编译后的图 ====
        result = compiled.invoke(inputs)
        if ENABLE_VERBOSE_LOGGING:
            # (这是你原来的调试打印)
            print("!!!!!!!!!!!!!!result:")

        output_stream = result.get("answer")
        final_answer = ""

        # ==========================================================
        # ==== 流式输出 (这是已修复的核心逻辑) ====
        # ==========================================================
        
        if output_stream is None:
            # --- 兜底逻辑：如果 "answer" 为空，尝试从其他字段获取非流式答案 ---
            if ENABLE_VERBOSE_LOGGING:
                print("⚠️ 'answer' field is None, checking sync fallbacks...")
            
            maybe_sync = (
                result.get("answer_sync")
                or result.get("final_answer")
                or result.get("text")
                or result.get("answer_text")
            )
            if isinstance(maybe_sync, str):
                final_answer = maybe_sync
                yield {"type": "token", "data": final_answer}
            elif ENABLE_VERBOSE_LOGGING:
                 print("⚠️ No valid answer or fallback answer found.")

        elif isinstance(output_stream, str):
            # --- 修复点 1: answer 是一个完整的字符串 (来自插件或选课) ---
            # 我们直接把它作为单个 token 发送出去，而不是逐字迭代
            if ENABLE_VERBOSE_LOGGING:
                print(f"[RunChat] Received a single string answer: {output_stream[:50]}...")
                
            final_answer = output_stream
            yield {"type": "token", "data": final_answer}

        elif isinstance(output_stream, collections.abc.Iterator):
            # --- 修复点 2: answer 是一个流 (来自 LLM) ---
            # 我们迭代它，并逐个解析和转发 token
            if ENABLE_VERBOSE_LOGGING:
                print("[RunChat] Received an iterator stream, starting iteration...")
            try:
                # (这是你原来的 Qwen 解析逻辑，保持不变)
                for chunk in output_stream:
                    if isinstance(chunk, bytes):
                        chunk = chunk.decode("utf-8", errors="ignore")
                    elif not isinstance(chunk, str):
                        try:
                            chunk = json.dumps(chunk, ensure_ascii=False)
                        except Exception:
                            chunk = str(chunk)

                    for line in chunk.strip().splitlines():
                        if not line.strip():
                            continue
                        text_piece = None
                        try:
                            data = json.loads(line)
                            if isinstance(data, dict):
                                choices = data.get("choices")
                                if choices and isinstance(choices, list):
                                    delta = choices[0].get("delta", {})
                                    text_piece = delta.get("content", "")
                                if not text_piece:
                                    text_piece = (
                                        data.get("text")
                                        or data.get("content")
                                        or ""
                                    )
                        except Exception:
                            text_piece = line

                        if text_piece:
                            final_answer += text_piece
                            yield {"type": "token", "data": text_piece}
                            
            except Exception as e:
                tb = traceback.format_exc()
                if ENABLE_VERBOSE_LOGGING:
                    print(f"Error while iterating output_stream: {e}\n{tb}")
                yield {"type": "error", "data": {"message": str(e), "trace": tb}}
                
        else:
            # --- 兜底：如果类型未知，转为字符串并发送 ---
            if ENABLE_VERBOSE_LOGGING:
                print(f"⚠️ Unknown answer type: {type(output_stream)}, converting to str.")
            final_answer = str(output_stream)
            yield {"type": "token", "data": final_answer}
            
        # ==========================================================
        # ==== 修复结束 ====
        # ==========================================================


        # ==== 输出完整历史 ====
        # (这部分逻辑保持不变)
        final_history = messages + [{"role": "assistant", "content": final_answer}]
        yield {"type": "history", "data": final_history}

        # ==== 保存最终结果 ====
        # (这部分逻辑保持不变)
        if node_save_memory:
            try:
                state_for_save = {
                    "messages": final_history,
                    "query": query,
                    "user_id": user_id,
                    "route": result.get("route", "general_chat"),
                    "answer": final_answer,
                    "memory": result.get("memory", {}) or {},
                    "is_grounded": result.get("is_grounded", True),
                }
                if ENABLE_VERBOSE_LOGGING:
                    print("Calling node_save_memory with state:")
                node_save_memory(state_for_save)
                if ENABLE_VERBOSE_LOGGING:
                    print("Final answer saved.")
            except Exception as e:
                if ENABLE_VERBOSE_LOGGING:
                    print(f"node_save_memory exception: {e}")
                    traceback.print_exc()
        elif ENABLE_VERBOSE_LOGGING:
            print("⚠️ node_save_memory not available; skipped final save.")

    except Exception as e:
        tb = traceback.format_exc()
        if ENABLE_VERBOSE_LOGGING:
            print(f"❌ Error during run_chat: {e}\n{tb}")
        yield {"type": "error", "data": {"message": str(e), "trace": tb}}

    finally:
        if ENABLE_VERBOSE_LOGGING:
            print("STREAMING SESSION COMPLETED")
        try:
            perf_monitor.end_session()
        except Exception:
            pass
        # 你的前端 _makeRequest 解析器目前没有处理 [DONE] 或 "end" 类型
        # 但发送这个事件是一个好习惯，以防未来需要
        yield {"type": "end", "data": "Stream finished."}