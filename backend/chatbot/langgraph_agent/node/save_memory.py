# backend/chatbot/langgraph_agent/node/save_memory.py
import json
import copy
import traceback
import re
import asyncio  # [OK] 用 asyncio 取代 threading
from datetime import datetime
from typing import Dict, Any, List, Optional

from ..core import ENABLE_VERBOSE_LOGGING, ROUTER_MODEL, call_qwen_httpx  # [OK] 异步 LLM
from ...db_manager import get_async_db_connection, Error  # [OK] 异步 DB

# 类型兜底
try:
    from ..schemas import Memory  # type: ignore
except Exception:
    Memory = Dict[str, Any]  # type: ignore

# === 常量 ===
RECENT_HISTORY_LIMIT = 3
ARCHIVED_BATCH_SIZE = 10

LONG_TERM_FIELDS = ["identity", "goals", "preferences", "constraints", "skills"]
MAX_ITEMS_PER_FIELD = 5
MAX_FIELD_CHARS = 400
SUMMARY_MAX_CHARS = 1600

DEFAULT_MEMORY_STRUCTURE: Memory = {
    "long_term_summary": "",
    "recent_conversations": [],
    "archived_summaries": [],
}

# [OK] 用 asyncio.Lock 取代 threading.Lock
_USER_MEMORY_LOCKS: Dict[str, asyncio.Lock] = {}
_GLOBAL_LOCK_DICT_LOCK = asyncio.Lock()

async def _get_user_lock(user_id: str) -> asyncio.Lock:
    async with _GLOBAL_LOCK_DICT_LOCK:
        lock = _USER_MEMORY_LOCKS.get(user_id)
        if lock is None:
            lock = asyncio.Lock()
            _USER_MEMORY_LOCKS[user_id] = lock
        return lock

# ========== 工具函数（保持不变） ==========
def _ensure_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        parts = re.split(r"[;\n；、，,]\s*", v.strip())
        return [p for p in parts if p]
    return [str(v)]

def _json_dumps_cn(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

def _clip(s: str, max_chars: int = SUMMARY_MAX_CHARS) -> str:
    return s[:max_chars] if isinstance(s, str) else str(s)[:max_chars]

def _parse_dt(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return datetime.now()

def _merge_profile(old: dict, new: dict) -> dict:
    out = {k: [] for k in LONG_TERM_FIELDS}
    for k in LONG_TERM_FIELDS:
        old_list = _ensure_list(old.get(k))
        new_list = _ensure_list(new.get(k))
        merged, seen = [], set()
        for item in old_list + new_list:
            s = str(item).strip()
            if not s or s.lower() in ("n/a", "none", "null"):
                continue
            if s in seen:
                continue
            seen.add(s)
            merged.append(s[:MAX_FIELD_CHARS])
        out[k] = merged[:MAX_ITEMS_PER_FIELD]
    return out

def _parse_profile_json(text: str) -> dict:
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            cleaned = {}
            for k in LONG_TERM_FIELDS:
                cleaned[k] = _ensure_list(data.get(k))[:MAX_ITEMS_PER_FIELD]
            return cleaned
    except Exception:
        pass
    return {
        "identity": [],
        "goals": [],
        "preferences": [_clip(text, SUMMARY_MAX_CHARS)],
        "constraints": [],
        "skills": [],
    }

def _build_archive_text(batch: List[dict]) -> str:
    return "\n".join(
        f"[{e.get('T','')}]\nQ: {e.get('Q','')}\nA: {_clip(e.get('A',''), 400)}"
        for e in batch if e.get("Q") and e.get("A")
    )

def _load_existing_profile(memory: Memory) -> dict:
    raw = memory.get("long_term_summary", "") or ""
    if not raw:
        return {k: [] for k in LONG_TERM_FIELDS}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {k: _ensure_list(data.get(k)) for k in LONG_TERM_FIELDS}
    except Exception:
        pass
    return {
        "identity": [],
        "goals": [],
        "preferences": [_clip(raw, SUMMARY_MAX_CHARS)],
        "constraints": [],
        "skills": [],
    }

# ========== 异步 DB API（已全量 async） ==========

async def load_memory_structure_async(user_id: str, tab_id: str) -> Memory:
    memory = copy.deepcopy(DEFAULT_MEMORY_STRUCTURE)
    try:
        async with get_async_db_connection() as (conn, cursor):
            # 1) 长期摘要
            await cursor.execute(
                "SELECT long_term_summary FROM user_memory WHERE user_id = %s",
                (user_id,),
            )
            row = await cursor.fetchone()
            if row and row.get("long_term_summary"):
                memory["long_term_summary"] = row["long_term_summary"]

            # 2) 近期对话（只作为快照保存；真正用于 LLM 的最近 k 条由 load_memory 节点单独查询）
            await cursor.execute(
                """
                SELECT timestamp, question, answer, metadata
                FROM tab_memory
                WHERE user_id = %s AND tab_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (user_id, tab_id, RECENT_HISTORY_LIMIT + 20),
            )
            recent_db = await cursor.fetchall() or []
            memory["recent_conversations"] = []
            for r in recent_db:
                meta = {}
                try:
                    meta = json.loads(r["metadata"]) if r.get("metadata") else {}
                except Exception:
                    meta = {}
                memory["recent_conversations"].append({
                    "Q": r.get("question", "") or "",
                    "A": r.get("answer", "") or "",
                    "T": (r.get("timestamp") or datetime.now()).isoformat(),
                    "metadata": meta,
                })
            memory["recent_conversations"].reverse()

            # 3) 归档索引
            await cursor.execute(
                """
                SELECT period, count, archived_at
                FROM archived_summaries
                WHERE user_id = %s
                ORDER BY archived_at DESC
                LIMIT 50
                """,
                (user_id,),
            )
            archived_db = await cursor.fetchall() or []
            memory["archived_summaries"] = [
                {
                    "period": row.get("period", ""),
                    "count": row.get("count", 0),
                    "archived_at": (row.get("archived_at") or datetime.now()).isoformat(),
                }
                for row in archived_db
            ]
        return memory
    except Error as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"CRITICAL: Failed to load memory for {user_id}/{tab_id}: {e}")
            traceback.print_exc()
        return copy.deepcopy(DEFAULT_MEMORY_STRUCTURE)

async def _atomic_save_to_db_async(user_id: str, tab_id: str, obj: Memory) -> None:
    try:
        async with get_async_db_connection() as (conn, cursor):
            await conn.begin()
            try:
                # 1) user_memory
                await cursor.execute(
                    """
                    INSERT INTO user_memory (user_id, long_term_summary)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE long_term_summary = VALUES(long_term_summary)
                    """,
                    (user_id, obj.get("long_term_summary", "")),
                )
                # 2) tab_memory 覆盖本 tab 的 recent_conversations
                await cursor.execute(
                    "DELETE FROM tab_memory WHERE user_id = %s AND tab_id = %s",
                    (user_id, tab_id),
                )
                convs = obj.get("recent_conversations", []) or []
                if convs:
                    conv_data = []
                    for e in convs:
                        ts = _parse_dt(e.get("T", datetime.now().isoformat()))
                        metadata_obj = e.get("metadata", {}) or {}
                        conv_data.append((user_id, tab_id, ts, e.get("Q", ""), e.get("A", ""), _json_dumps_cn(metadata_obj)))
                    await cursor.executemany(
                        """
                        INSERT INTO tab_memory (user_id, tab_id, timestamp, question, answer, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        conv_data,
                    )

                # 3) archived_summaries 覆盖
                await cursor.execute("DELETE FROM archived_summaries WHERE user_id = %s", (user_id,))
                archives = obj.get("archived_summaries", []) or []
                if archives:
                    archive_data = []
                    for a in archives:
                        archived_at = _parse_dt(a.get("archived_at", datetime.now().isoformat()))
                        archive_data.append((user_id, a.get("period", ""), a.get("count", 0), archived_at))
                    await cursor.executemany(
                        """
                        INSERT INTO archived_summaries (user_id, period, count, archived_at)
                        VALUES (%s, %s, %s, %s)
                        """,
                        archive_data,
                    )

                await conn.commit()
            except Exception:
                await conn.rollback()
                raise
    except Error as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"CRITICAL: DB transaction failed for {user_id}/{tab_id}: {e}")
            traceback.print_exc()
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"CRITICAL: _atomic_save_to_db_async unknown error for {user_id}/{tab_id}: {e}")
            traceback.print_exc()

def _clean(memory: Memory) -> Memory:
    out: Memory = {
        "long_term_summary": memory.get("long_term_summary", ""),
        "recent_conversations": [],
        "archived_summaries": memory.get("archived_summaries", []),
    }
    for e in memory.get("recent_conversations", []):
        if isinstance(e, dict):
            out["recent_conversations"].append(e)
    return out

async def save_memory_structure_async(user_id: str, tab_id: str, memory: Memory) -> None:
    hist_len = len(memory.get("recent_conversations", [])) if memory else 0

    # [OK] 触发异步归档（用 asyncio 锁 + create_task）
    if hist_len > RECENT_HISTORY_LIMIT:
        lock = await _get_user_lock(user_id)
        if not lock.locked():  # 非阻塞尝试
            await lock.acquire()
            if ENABLE_VERBOSE_LOGGING:
                print(f"Triggering async archive for {user_id}/{tab_id}, length={hist_len}")
            asyncio.create_task(_async_archive_and_summarize_async(user_id, tab_id, lock, copy.deepcopy(memory)))

    await _atomic_save_to_db_async(user_id, tab_id, _clean(memory))
    if ENABLE_VERBOSE_LOGGING:
        print(f"[SAVE] Saved memory to DB for {user_id}/{tab_id}")

# [OK] 异步归档协程（不要再用线程）
async def _async_archive_and_summarize_async(user_id: str, tab_id: str, lock: asyncio.Lock, memory: Memory) -> None:
    try:
        if len(memory.get("recent_conversations", [])) <= RECENT_HISTORY_LIMIT:
            return

        batch = memory["recent_conversations"][:ARCHIVED_BATCH_SIZE]
        memory["recent_conversations"] = memory["recent_conversations"][ARCHIVED_BATCH_SIZE:]
        archive_text = _build_archive_text(batch)
        if not archive_text.strip():
            await _atomic_save_to_db_async(user_id, tab_id, memory)
            return

        existing_profile = _load_existing_profile(memory)
        system_msg = (
            "你是一个记忆管理助手。请将“旧的用户长期摘要”和“新的对话摘要”合并，"
            "产出简洁、结构化、中文的用户长期画像（JSON）。"
            f"字段固定为：{', '.join(LONG_TERM_FIELDS)}；每字段最多 {MAX_ITEMS_PER_FIELD} 条，单条不超过 {MAX_FIELD_CHARS} 字。"
        )
        user_msg = (
            f"【旧摘要（JSON或文本）】\n{_json_dumps_cn(existing_profile)}\n\n"
            f"【新对话记录（候选摘要源）】\n{archive_text}\n\n"
            "请输出合并后的长期摘要，严格 JSON 格式。"
        )
        messages = [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]

        # [OK] 异步 LLM（带重试/限流）
        resp = await call_qwen_httpx(messages, model=ROUTER_MODEL, purpose="memory_summarization", stream=False, temperature=0.2)
        resp_text = (resp.get("content", "") if isinstance(resp, dict) else str(resp)).strip()

        new_profile = _parse_profile_json(resp_text)
        merged_profile = _merge_profile(existing_profile, new_profile)

        memory["long_term_summary"] = _json_dumps_cn(merged_profile)
        memory.setdefault("archived_summaries", [])
        memory["archived_summaries"].append({
            "period": f"{batch[0].get('T','')} to {batch[-1].get('T','')}",
            "count": len(batch),
            "archived_at": datetime.now().isoformat(),
        })
        memory["archived_summaries"] = memory["archived_summaries"][-50:]

        await _atomic_save_to_db_async(user_id, tab_id, memory)

    except Exception:
        if ENABLE_VERBOSE_LOGGING:
            print(f"CRITICAL: _async_archive failed for {user_id}/{tab_id}")
            traceback.print_exc()
    finally:
        # [OK] 释放 asyncio.Lock
        if lock.locked():
            lock.release()

# ===== 可选：保留同步包装器（如果还有同步调用方） =====
def load_memory_structure(user_id: str, tab_id: str) -> Memory:
    return asyncio.run(load_memory_structure_async(user_id, tab_id))

def save_memory_structure(user_id: str, tab_id: str, memory: Memory) -> None:
    asyncio.run(save_memory_structure_async(user_id, tab_id, memory))