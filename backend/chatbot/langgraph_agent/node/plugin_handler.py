# ./node/plugin_handler.py
from typing import Dict, Any
from core import ENABLE_VERBOSE_LOGGING

def node_plugin_handler(state: Dict[str, Any]) -> Dict[str, Any]:
    query = state.get("query", "")
    answer = None
    plugin_triggered = any(kw in query.lower() for kw in ["chrome", "插件", "打开网页"])
    if plugin_triggered:
        if ENABLE_VERBOSE_LOGGING:
            print("🔌 Plugin handler triggered.")
        answer = "（已唤起 Chrome 插件执行任务……）"
    return {"answer": answer}
