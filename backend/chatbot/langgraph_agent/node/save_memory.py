# node/save_memory.py

import os
import json
import traceback
import tempfile
import types
from typing import Dict, Any
from core import MEMORY_DIR, ENABLE_VERBOSE_LOGGING

def node_save_memory(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if ENABLE_VERBOSE_LOGGING:
            print("!!!!!!!!!!!!!!state in save_memory:")
    except Exception:
        print("!!!!!!!!!!!!!!state in save_memory: <logging failed>")

    user_id = state.get("user_id", "anonymous")
    memory_path = os.path.join(MEMORY_DIR, f"{user_id}.json")

    def convert_message(msg):
        if hasattr(msg, 'dict') and callable(getattr(msg, "dict")):
            try:
                return msg.dict()
            except Exception:
                return str(msg)
        elif hasattr(msg, 'role') and hasattr(msg, 'content'):
            try:
                return {"role": msg.role, "content": msg.content}
            except Exception:
                return {"role": getattr(msg, "role", ""), "content": str(getattr(msg, "content", ""))}
        elif isinstance(msg, dict):
            return {k: convert_message(v) for k, v in msg.items()}
        elif isinstance(msg, (list, tuple)):
            return [convert_message(item) for item in msg]
        return msg

    def _is_generator_like(obj):
        if obj is None: return False
        if isinstance(obj, (str, bytes, dict, list, tuple)): return False
        if isinstance(obj, types.GeneratorType): return True
        try:
            from collections.abc import Iterator
            if isinstance(obj, Iterator): return True
        except Exception: pass
        return False
    
    new_entry = {
        "user_id": user_id,
        "query": state.get("query"),
        "route": state.get("route"),
        "messages": state.get("messages"),
        "memory": state.get("memory", {}),
        "is_grounded": state.get("is_grounded"),
    }

    answer_obj = state.get("answer")
    if _is_generator_like(answer_obj):
        new_entry["answer"] = "<STREAMING_ANSWER_NOT_SAVED>"
        if ENABLE_VERBOSE_LOGGING:
            print(f"🟡 Detected streaming answer for {user_id}, saving placeholder.")
    else:
        new_entry["answer"] = answer_obj

    existing = None
    try:
        os.makedirs(MEMORY_DIR, exist_ok=True)
        if os.path.exists(memory_path):
            with open(memory_path, "r", encoding="utf-8") as f:
                content = f.read()
                if content and content.strip():
                    try:
                        existing = json.loads(content)
                    except Exception:
                        try:
                            fixed = content.replace(",}", "}").replace(",]", "]")
                            existing = json.loads(fixed)
                        except Exception:
                            existing = None
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"⚠️ Error while reading existing memory file: {e}")
        existing = None

    history = []
    if isinstance(existing, dict):
        if "history" in existing and isinstance(existing["history"], list):
            history = existing["history"]
        else:
            history = [existing]
    elif isinstance(existing, list):
        history = existing
    else:
        history = []

    should_append = True
    if history:
        last = history[-1]
        try:
            last_q = last.get("query")
            if last_q == new_entry.get("query") and new_entry.get("answer") == "<STREAMING_ANSWER_NOT_SAVED>":
                history[-1] = new_entry
                should_append = False
                if ENABLE_VERBOSE_LOGGING:
                    print("🔁 Detected duplicate last entry (streaming); updating last entry.")
            elif last_q == new_entry.get("query") and last.get("answer") == new_entry.get("answer"):
                history[-1] = new_entry
                should_append = False
                if ENABLE_VERBOSE_LOGGING:
                    print("🔁 Detected duplicate last entry (sync); updating last entry.")
        except Exception:
            pass

    if should_append:
        history.append(new_entry)

    to_dump = new_entry.copy()
    to_dump["history"] = history

    try:
        serializable_memory = convert_message(to_dump)
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"⚠️ convert_message failed: {e}; fallback to str")
        serializable_memory = {"raw": str(to_dump)}

    try:
        if ENABLE_VERBOSE_LOGGING:
            preview = str(serializable_memory)
            if len(preview) > 1000:
                preview = preview[:1000] + " ...(truncated)"
            print(f"!!!!!!!!!!!!!!serializable_memory preview:")

        with tempfile.NamedTemporaryFile("w", delete=False, dir=MEMORY_DIR, encoding="utf-8") as tf:
            json.dump(serializable_memory, tf, ensure_ascii=False, indent=2)
            tmpname = tf.name
        os.replace(tmpname, memory_path)

        if ENABLE_VERBOSE_LOGGING:
            print(f"💾 Memory saved for {user_id} -> {memory_path}")
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"⚠️ Failed to write memory file for {user_id}: {e}")
            traceback.print_exc()

    return {}