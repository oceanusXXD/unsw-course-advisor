import os
import json
import traceback
from typing import Dict, Any
from chatbot.langgraph_agent.core import MEMORY_DIR, ENABLE_VERBOSE_LOGGING

def node_load_memory(state: Dict[str, Any]) -> Dict[str, Any]:
    print("!!!!!!!!!!!!!!state in load_memory:", state)
    user_id = state.get("user_id", "anonymous")
    memory_path = os.path.join(MEMORY_DIR, f"{user_id}.json")
    memory = {}  # 默认空内存
    
    # 确保内存目录存在
    os.makedirs(MEMORY_DIR, exist_ok=True)
    
    if os.path.exists(memory_path):
        try:
            with open(memory_path, "r", encoding="utf-8") as f:
                file_content = f.read().strip()
                
                # 更严格的空内容检查
                if file_content and file_content != "{}" and file_content != "[]":
                    try:
                        memory = json.loads(file_content)
                        # 验证加载的内容是字典
                        if not isinstance(memory, dict):
                            memory = {}
                            raise ValueError("Loaded memory is not a dictionary")
                            
                        if ENABLE_VERBOSE_LOGGING:
                            print(f"🧠 Memory loaded for {user_id}")
                    except json.JSONDecodeError as e:
                        # 尝试修复常见的JSON格式问题
                        try:
                            # 尝试处理末尾可能有逗号的情况
                            fixed_content = file_content.replace(",}", "}").replace(",]", "]")
                            memory = json.loads(fixed_content)
                        except:
                            # 如果修复失败，记录原始错误
                            if ENABLE_VERBOSE_LOGGING:
                                print(f"⚠️ Failed to parse memory file for {user_id}: {e}")
                                print(f"Problematic content: {file_content[:100]}...")
                            memory = {}
                else:
                    if ENABLE_VERBOSE_LOGGING:
                        print(f"ℹ️ Empty memory file for {user_id}")
        except Exception as e:
            if ENABLE_VERBOSE_LOGGING:
                print(f"⚠️ Failed to load memory for {user_id}: {e}")
                traceback.print_exc()
            memory = {}  # 出错时重置为空
    
    return {"memory": memory}