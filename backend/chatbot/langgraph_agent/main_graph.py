# main_graph.py
import os
import threading
import traceback
import time
import json
from .config_loader import load_graph_from_config
from .core import ChatState, monitor_performance, perf_monitor, ENABLE_VERBOSE_LOGGING, call_qwen_sync
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent  # 调整层级
sys.path.append(str(project_root))
CFG_PATH = os.path.join(os.path.dirname(__file__), "nodes_config.yaml")

# 全局缓存与锁，确保线程安全的单例编译
_COMPILED_GRAPH = None
_GRAPH_LOCK = threading.Lock()

def build_and_compile_graph(force_rebuild: bool = False):
    print("[DEBUG] Entering build_and_compile_graph function")
    """
    线程安全的单例编译函数。
    首次调用会读取 CFG_PATH 并编译 graph，后续调用直接返回缓存。
    如果需要强制重建，传入 force_rebuild=True。
    返回编译结果（可能为 None，表示编译失败）。
    """
    global _COMPILED_GRAPH
    # 快速路径
    print(f"[DEBUG] Checking _COMPILED_GRAPH: {_COMPILED_GRAPH}, force_rebuild: {force_rebuild}")
    if _COMPILED_GRAPH is not None and not force_rebuild:
        print("[DEBUG] Returning cached _COMPILED_GRAPH")
        return _COMPILED_GRAPH

    with _GRAPH_LOCK:
        print("[DEBUG] Acquired _GRAPH_LOCK")
        # double-check
        print(f"[DEBUG] Double-checking _COMPILED_GRAPH: {_COMPILED_GRAPH}")
        if _COMPILED_GRAPH is not None and not force_rebuild:
            print("[DEBUG] Returning cached _COMPILED_GRAPH after lock")
            return _COMPILED_GRAPH
        try:
            if ENABLE_VERBOSE_LOGGING:
                print(f"🔧 Compiling graph from config: {CFG_PATH}")
            print("[DEBUG] Loading graph from config...")
            graph_builder = load_graph_from_config(CFG_PATH, ChatState, monitor_wrapper=monitor_performance)
            print("[DEBUG] Compiling graph...")
            compiled = graph_builder.compile()
            if compiled is None:
                if ENABLE_VERBOSE_LOGGING:
                    print("⚠️ Graph compile returned None. Check nodes_config.yaml and load_graph_from_config.")
                print("[DEBUG] Graph compilation returned None")
            else:
                if ENABLE_VERBOSE_LOGGING:
                    print("✅ Graph compiled and cached.")
                print("[DEBUG] Graph compiled successfully")
            _COMPILED_GRAPH = compiled
            print(f"[DEBUG] Set _COMPILED_GRAPH to: {_COMPILED_GRAPH}")
            return _COMPILED_GRAPH
        except Exception as e:
            if ENABLE_VERBOSE_LOGGING:
                traceback.print_exc()
                print(f"❌ Failed to compile graph: {e}")
            print(f"[DEBUG] Exception during compilation: {str(e)}")
            _COMPILED_GRAPH = None
            return None
        finally:
            print("[DEBUG] Releasing _GRAPH_LOCK")

def run_chat(query: str, user_id: str = "anonymous", init_messages=None):
    """
    更健壮的 run_chat：
    - 在打印时会把复杂对象序列化为基础类型，避免 HumanMessage 无法序列化问题
    - 对 output_stream 的 chunk 做多格式兼容（string-json, dict/object, dashscope 格式等）
    - 仍然以 generator yield 事件：token/history/error/end
    """
    import time, traceback, json

    print("\n[DEBUG] ====== STARTING NEW CHAT SESSION ======")
    compiled = build_and_compile_graph()
    if compiled is None:
        yield {"type": "error", "data": {"message": "Graph 未能成功编译"}}
        return

    session_id = f"{user_id}_{int(time.time() * 1000)}"
    perf_monitor.start_session(session_id)

    try:
        messages = (init_messages or []) + [{"role": "user", "content": query}] if not isinstance(query, dict) else (init_messages or []) + [{"role": "user", "content": query}]
        inputs = {
            "query": query, 
            "messages": init_messages or [],
            "user_id": user_id,
            "stream": True
        }
        print("!!!!!!!!!!!!!!inputs:", inputs)
        result = compiled.invoke(inputs)

        print("!!!!!!!!!!!!!!result:",result )

        final_answer = ""
        # ------------- 处理 output_stream -------------
        output_stream = result.get("answer")
        print("!!!!!!!!!output_stream:", output_stream)
        for chunk in output_stream:
            # chunk 通常为字节流或字符串，每行一个 JSON
            if isinstance(chunk, bytes):
                chunk = chunk.decode("utf-8", errors="ignore")
            elif not isinstance(chunk, str):
                chunk = str(chunk)

            for line in chunk.strip().splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    text = delta.get("content", "")
                    if text:
                        final_answer += text
                        yield {"type": "token", "data": text}
                except Exception:
                    continue
        
        # ===== 流结束后，输出完整对话历史 =====
        final_history = messages + [{"role": "assistant", "content": final_answer}]
        yield {"type": "history", "data": final_history}

    except Exception as e:
        tb = traceback.format_exc()
        if ENABLE_VERBOSE_LOGGING:
            print(f"❌ Error during stream: {e}\n{tb}")
        yield {"type": "error", "data": {"message": str(e), "trace": tb}}

    finally:
        if ENABLE_VERBOSE_LOGGING:
            print("✅ STREAMING SESSION COMPLETED")
        perf_monitor.end_session()
        yield {"type": "end", "data": "Stream finished."}
