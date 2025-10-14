# ./node/save_memory.py
import os, json, traceback
from typing import Dict, Any
from core import MEMORY_DIR, ENABLE_VERBOSE_LOGGING

def node_save_memory(state: Dict[str, Any]) -> Dict[str, Any]:
    user_id = state.get("user_id", "anonymous")
    memory = state.get("memory", {})
    memory_path = os.path.join(MEMORY_DIR, f"{user_id}.json")
    try:
        with open(memory_path, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)
        if ENABLE_VERBOSE_LOGGING:
            print(f"💾 Memory saved for {user_id}")
    except Exception:
        traceback.print_exc()
    return {}
