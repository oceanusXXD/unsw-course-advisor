# node/load_memory.py
import os
import json
import traceback
from typing import Dict, Any
from core import MEMORY_DIR, ENABLE_VERBOSE_LOGGING

def node_load_memory(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    更稳健的 load：
    - 读取文件并标准化为 {'history': [...], ...latest fields...}
    - 清理 entry 中可能嵌套的 'history'（避免循环嵌套）
    - 返回 {"memory": memory_dict}
    """
    if ENABLE_VERBOSE_LOGGING:
        print("!!!!!!!!!!!!!!state in load_memory:")
    user_id = state.get("user_id", "anonymous")
    memory_path = os.path.join(MEMORY_DIR, f"{user_id}.json")
    memory = {}

    def _strip_history_from_entry(entry):
        """对单个 entry 做清理：去掉 entry['memory'] 中的 history，避免嵌套"""
        if not isinstance(entry, dict):
            return entry
        out = {}
        for k, v in entry.items():
            if k == "history":
                continue
            if k == "memory" and isinstance(v, dict):
                # 递归但移除内部 history
                inner = {}
                for ik, iv in v.items():
                    if ik == "history":
                        continue
                    inner[ik] = iv
                out["memory"] = inner
            else:
                out[k] = v
        return out

    # ensure dir
    os.makedirs(MEMORY_DIR, exist_ok=True)

    if not os.path.exists(memory_path):
        if ENABLE_VERBOSE_LOGGING:
            print(f"ℹ️ Memory file not found for {user_id}: {memory_path}")
        return {"memory": {}}

    try:
        with open(memory_path, "r", encoding="utf-8") as f:
            content = f.read()
        if not content or not content.strip():
            if ENABLE_VERBOSE_LOGGING:
                print(f"ℹ️ Empty memory file for {user_id}")
            return {"memory": {}}

        try:
            loaded = json.loads(content)
        except json.JSONDecodeError as e:
            try:
                fixed = content.replace(",}", "}").replace(",]", "]")
                loaded = json.loads(fixed)
                if ENABLE_VERBOSE_LOGGING:
                    print(f"⚠️ Recovered JSON memory for {user_id} after simple fix.")
            except Exception:
                if ENABLE_VERBOSE_LOGGING:
                    print(f"⚠️ Failed to parse memory file for {user_id}: {e}")
                    print(f"Problematic content preview: {content[:200]!r}")
                return {"memory": {}}

        # 规范化为 memory dict 包含 history（列表）和顶层最新字段
        if isinstance(loaded, dict):
            if "history" in loaded and isinstance(loaded["history"], list):
                # 清理每条 entry 的内嵌 history
                cleaned_history = [_strip_history_from_entry(e) for e in loaded["history"]]
                memory = dict(loaded)  # shallow copy
                memory["history"] = cleaned_history
                # 保证顶层最新字段对应最后一条
                if cleaned_history:
                    last = cleaned_history[-1]
                    for key in ("user_id", "query", "route", "messages", "answer", "is_grounded"):
                        if key in last:
                            memory[key] = last[key]
            else:
                # 旧的单条条目 -> 转为 history
                cleaned = _strip_history_from_entry(loaded)
                memory = {"history": [cleaned]}
                for key in ("user_id", "query", "route", "messages", "answer", "is_grounded"):
                    if key in cleaned:
                        memory[key] = cleaned[key]
        elif isinstance(loaded, list):
            cleaned_history = [_strip_history_from_entry(e) for e in loaded]
            memory = {"history": cleaned_history}
            if cleaned_history:
                last = cleaned_history[-1]
                for key in ("user_id", "query", "route", "messages", "answer", "is_grounded"):
                    if key in last:
                        memory[key] = last[key]
        else:
            memory = {"history": [loaded]}

        if ENABLE_VERBOSE_LOGGING:
            print(f"🧠 Memory loaded for {user_id}: keys={list(memory.keys())}")
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"⚠️ Failed to load memory for {user_id}: {e}")
            traceback.print_exc()
        memory = {}

    return {"memory": memory}
