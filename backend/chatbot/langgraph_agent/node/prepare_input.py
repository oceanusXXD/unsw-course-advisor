# ./node/prepare_input.py
from typing import Dict, Any
def node_prepare_input(state: Dict[str, Any]) -> Dict[str, Any]:
    """准备输入：加载用户记忆并构建消息列表"""
    query = state.get("query", "").strip()
    messages = [{"role": "user", "content": query}]
 
    return {"messages": messages}
