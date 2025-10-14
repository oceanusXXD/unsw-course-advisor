# main_graph.py
import os
from .config_loader import load_graph_from_config
from .core import ChatState, monitor_performance, perf_monitor, ENABLE_VERBOSE_LOGGING, call_qwen_sync
import yaml
import json
import traceback
import time
CFG_PATH = os.path.join(os.path.dirname(__file__), "nodes_config.yaml")

def build_and_compile_graph():
    graph_builder = load_graph_from_config(CFG_PATH, ChatState, monitor_wrapper=monitor_performance)
    compiled = graph_builder.compile()
    return compiled

def run_chat(query: str, user_id: str = "anonymous", init_messages=None):
    session_id = f"{user_id}_{int(time.time() * 1000)}"
    perf_monitor.start_session(session_id)
    try:
        if ENABLE_VERBOSE_LOGGING:
            print(f"🚀 STREAMING SESSION: {session_id}")
            print(f"❓ QUERY: {query}")
        messages = (init_messages or []) + [{"role": "user", "content": query}]
        final_answer = ""
        stream_gen = call_qwen_sync(messages=messages, stream=True, model="qwen-plus", purpose="chat")
        for chunk in stream_gen:
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

if __name__ == "__main__":
    compiled = build_and_compile_graph()
    print("Graph compiled:", bool(compiled))
