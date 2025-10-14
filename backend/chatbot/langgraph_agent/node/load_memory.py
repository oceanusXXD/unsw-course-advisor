# ./node/load_memory.py
import os, json, traceback
from typing import Dict, Any
from core import MEMORY_DIR, ENABLE_VERBOSE_LOGGING

def node_load_memory(state: Dict[str, Any]) -> Dict[str, Any]:
    user_id = state.get("user_id", "anonymous")
    memory_path = os.path.join(MEMORY_DIR, f"{user_id}.json")
    if os.path.exists(memory_path):
        try:
            with open(memory_path, "r", encoding="utf-8") as f:
                memory = json.load(f)
            if ENABLE_VERBOSE_LOGGING:
                print(f"🧠 Memory loaded for {user_id}")
        except Exception:
            traceback.print_exc()
            memory = {}
    else:
        memory = {}
    return {"memory": memory}
