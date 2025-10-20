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
            pass
            print("!!!!!!!!!!!!!!state in save_memory:")
    except Exception:
        print("!!!!!!!!!!!!!!state in save_memory: <logging failed>")

    user_id = state.get("user_id", "anonymous")
    memory_path = os.path.join(MEMORY_DIR, f"{user_id}.json")

    def convert_message(msg):
        """递归转换消息对象为可序列化的字典"""
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
        if obj is None:
            return False
        if isinstance(obj, (str, bytes, dict, list, tuple)):
            return False
        if isinstance(obj, types.GeneratorType):
            return True
        try:
            from collections.abc import Iterator
            if isinstance(obj, Iterator):
                return True
        except Exception:
            pass
        return False

    def _strip_history_from_dict(d):
        """返回 d 的浅拷贝并移除内嵌的 'history'（如果存在），递归处理 dict 中的 memory 字段。"""
        if not isinstance(d, dict):
            return d
        out = {}
        for k, v in d.items():
            if k == "history":
                # skip nested history
                continue
            if k == "memory" and isinstance(v, dict):
                # 递归剥离 memory 字段里的 history（避免嵌套）
                out["memory"] = _strip_history_from_dict(v)
            else:
                out[k] = v
        return out

    # 构造 new_entry：尽量只包含本轮需要保存的字段
    new_entry = {
        "user_id": user_id,
        "query": state.get("query"),
        "route": state.get("route"),
        "messages": state.get("messages"),
        "memory": {},  # 默认空，随后填充来自 existing 的简化 memory（不包含 history）
        "is_grounded": state.get("is_grounded"),
    }

    answer_obj = state.get("answer")
    if _is_generator_like(answer_obj):
        new_entry["answer"] = "<STREAMING_ANSWER_NOT_SAVED>"
        if ENABLE_VERBOSE_LOGGING:
            print(f"🟡 Detected streaming answer for {user_id}, saving placeholder.")
    else:
        new_entry["answer"] = answer_obj

    # 读取已有文件（若存在），并构造 history（同时得到 existing_memory_summary）
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
                        # 简单修复末尾多余逗号然后再次尝试
                        try:
                            fixed = content.replace(",}", "}").replace(",]", "]")
                            existing = json.loads(fixed)
                            if ENABLE_VERBOSE_LOGGING:
                                print("⚠️ Recovered existing memory JSON after simple fix.")
                        except Exception:
                            existing = None
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"⚠️ Error while reading existing memory file: {e}")
            traceback.print_exc()
        existing = None

    # 构造 history 列表
    history = []
    existing_memory_summary = {}
    if isinstance(existing, dict):
        if "history" in existing and isinstance(existing["history"], list):
            history = existing["history"]
        else:
            # 旧格式：把整个 dict 视为一条历史
            history = [existing]
        # 取 existing 中的 memory 字段做简化摘要（去掉嵌套 history）
        existing_memory_field = existing.get("memory", {})
        if isinstance(existing_memory_field, dict):
            existing_memory_summary = _strip_history_from_dict(existing_memory_field)
        else:
            existing_memory_summary = existing_memory_field if existing_memory_field is not None else {}
    elif isinstance(existing, list):
        history = existing
        existing_memory_summary = {}
    else:
        history = []
        existing_memory_summary = {}

    # 把简化的 existing memory 填入 new_entry['memory']（避免把整个 history 嵌入进去）
    if existing_memory_summary:
        new_entry["memory"] = existing_memory_summary
    else:
        # 尝试把 existing 的顶层摘要作为 memory（不带 history）
        if isinstance(existing, dict):
            new_entry["memory"] = _strip_history_from_dict(existing)
        else:
            new_entry["memory"] = {}

    # 去重：如果最后一条与本条 (query+answer) 相同，则用 new_entry 覆盖最后一条（避免重复）
    should_append = True
    if history:
        last = history[-1]
        try:
            last_q = last.get("query")
            last_ans = last.get("answer")
            if last_q == new_entry.get("query") and last_ans == new_entry.get("answer"):
                # 相同 -> 更新而非追加（保持时间序列长度不膨胀）
                history[-1] = new_entry
                should_append = False
                if ENABLE_VERBOSE_LOGGING:
                    print("🔁 Detected duplicate last entry; updating last entry instead of appending.")
        except Exception:
            pass

    if should_append:
        history.append(new_entry)

    # 构造写回的对象：保留最新条目字段顶层，同时包含完整 history 列表
    to_dump = new_entry.copy()
    to_dump["history"] = history

    # 深度转换可序列化
    try:
        serializable_memory = convert_message(to_dump)
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"⚠️ convert_message failed: {e}; fallback to str")
        serializable_memory = {"raw": str(to_dump)}

    # 写文件（原子）
    try:
        preview = str(serializable_memory)
        if ENABLE_VERBOSE_LOGGING and len(preview) > 1000:
            preview = preview[:1000] + " ...(truncated)"
        if ENABLE_VERBOSE_LOGGING:
            print("!!!!!!!!!!!!!!serializable_memory preview:")

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
