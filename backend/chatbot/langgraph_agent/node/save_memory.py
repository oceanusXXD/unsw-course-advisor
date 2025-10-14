import os
import json
import traceback
from typing import Dict, Any
from core import MEMORY_DIR, ENABLE_VERBOSE_LOGGING

def node_save_memory(state: Dict[str, Any]) -> Dict[str, Any]:
    print("!!!!!!!!!!!!!!state in save_memory:", state)
    user_id = state.get("user_id", "anonymous")
    memory = state.get("memory", {})
    memory_path = os.path.join(MEMORY_DIR, f"{user_id}.json")
    
    def convert_message(msg):
        """递归转换消息对象为可序列化的字典"""
        if hasattr(msg, 'dict'):  # 如果是LangChain消息对象
            return msg.dict()
        elif hasattr(msg, 'role') and hasattr(msg, 'content'):  # 简单消息对象
            return {"role": msg.role, "content": msg.content}
        elif isinstance(msg, dict):
            return {k: convert_message(v) for k, v in msg.items()}
        elif isinstance(msg, (list, tuple)):
            return [convert_message(item) for item in msg]
        return msg
    
    try:
        # 深度转换整个memory对象
        serializable_memory = convert_message(memory)
        
        os.makedirs(MEMORY_DIR, exist_ok=True)
        with open(memory_path, "w", encoding="utf-8") as f:
            json.dump(serializable_memory, f, ensure_ascii=False, indent=2)
            
        if ENABLE_VERBOSE_LOGGING:
            print(f"💾 Memory saved for {user_id}")
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"⚠️ Failed to save memory for {user_id}: {e}")
            traceback.print_exc()
    
    return {}