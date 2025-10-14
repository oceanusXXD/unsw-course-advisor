# ./node/prepare_input.py
from typing import Dict, Any
def node_prepare_input(state: Dict[str, Any]) -> Dict[str, Any]:
    query = state.get("query", "").strip()
    messages = [{"role": "user", "content": query}]
    return {"messages": messages}
