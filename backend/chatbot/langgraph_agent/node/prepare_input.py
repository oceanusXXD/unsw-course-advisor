# ./node/prepare_input.py
from typing import Dict, Any

def node_prepare_input(state: Dict[str, Any]) -> Dict[str, Any]:
    """准备输入：合并用户记忆并构建消息列表"""
    query = state.get("query", "").strip()
    
    # 获取已加载的记忆
    memory = state.get("memory", {})
    previous_messages = memory.get("messages", [])
    
    # 构建新的用户消息
    new_user_message = {"role": "user", "content": query}
    
    # 合并历史消息和当前消息
    messages = previous_messages + [new_user_message]
    
    return {"messages": messages}