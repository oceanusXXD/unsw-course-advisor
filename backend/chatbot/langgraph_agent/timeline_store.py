# backend/chatbot/langgraph_agent/timeline_store.py
from typing import Dict, Any, List
import threading

# 简单内存版（生产可替换为 Redis/Django cache）
_TIMELINES: Dict[str, List[Dict[str, Any]]] = {}
_LOCK = threading.Lock()

def append(turn_id: str, event: Dict[str, Any]):
    if not turn_id or not isinstance(event, dict):
        return
    with _LOCK:
        _TIMELINES.setdefault(turn_id, []).append(event)

def get(turn_id: str) -> List[Dict[str, Any]]:
    with _LOCK:
        return list(_TIMELINES.get(turn_id, []))