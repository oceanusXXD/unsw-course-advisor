# prompt_loader.py
"""
负责从 .prompts.json 加载、处理和缓存所有提示词模板。
所有节点都应从此文件导入 load_prompts 函数。
"""

import json
import os
import threading
from typing import Dict

# 导入 core 中的日志开关
try:
    from core import ENABLE_VERBOSE_LOGGING
except ImportError:
    print("Warning: [prompt_loader] 无法导入 ENABLE_VERBOSE_LOGGING。默认为 False。")
    ENABLE_VERBOSE_LOGGING = False

# --- 全局缓存与锁 ---
_PROMPTS_CACHE = None
_PROMPTS_LOCK = threading.Lock()
# 定义配置文件的路径 (与此文件在同一目录下)
PROMPT_FILE_PATH = os.path.join(os.path.dirname(__file__), ".prompts.json")

def load_prompts() -> Dict[str, str]:
    """
    加载并缓存 .prompts.json 文件。
    在 Python 端处理 CORE_PERSONA 的替换。
    这是一个线程安全的单例加载器。
    """
    global _PROMPTS_CACHE
    # 1. 检查缓存 (无锁)
    if _PROMPTS_CACHE is not None:
        return _PROMPTS_CACHE

    # 2. 加锁
    with _PROMPTS_LOCK:
        # 3. 再次检查缓存 (防止竞态)
        if _PROMPTS_CACHE is not None:
            return _PROMPTS_CACHE

        try:
            if ENABLE_VERBOSE_LOGGING:
                print(f"Loading prompts from {PROMPT_FILE_PATH}")
                
            with open(PROMPT_FILE_PATH, 'r', encoding='utf-8') as f:
                templates = json.load(f)
            
            core_persona = templates.get("CORE_PERSONA", "AI助手")
            
            # 4. 手动执行模板替换
            processed_prompts = {
                # --- Generator 提示词 ---
                "RETRIEVED_PROMPT_TEMPLATE": templates.get("RETRIEVED_PROMPT_TEMPLATE", ""),
                "NEEDS_CLARIFICATION_PROMPT": templates.get("NEEDS_CLARIFICATION_PROMPT_TEMPLATE", "").format(CORE_PERSONA=core_persona),
                "GENERAL_CHAT_PROMPT": templates.get("GENERAL_CHAT_PROMPT_TEMPLATE", "").format(CORE_PERSONA=core_persona),
                "DEFAULT_PROMPT": templates.get("DEFAULT_PROMPT_TEMPLATE", "").format(CORE_PERSONA=core_persona),
                
                # --- Router 提示词 ---
                "ROUTER_PROMPT_TEMPLATE": templates.get("ROUTER_PROMPT_TEMPLATE", "")
            }

            # 5. 存入缓存
            _PROMPTS_CACHE = processed_prompts
            return _PROMPTS_CACHE

        except Exception as e:
            if ENABLE_VERBOSE_LOGGING:
                print(f"❌ ERROR: Failed to load prompts from {PROMPT_FILE_PATH}: {e}")
            # 返回一个安全的兜底值
            _PROMPTS_CACHE = {
                "RETRIEVED_PROMPT_TEMPLATE": "请基于以下信息回答：\n{context_str}",
                "NEEDS_CLARIFICATION_PROMPT": "你的问题不够清晰，请详细说明。",
                "GENERAL_CHAT_PROMPT": "你好，有什么可以帮你的吗？",
                "DEFAULT_PROMPT": "你好，请问有什么可以帮到你？",
                "ROUTER_PROMPT_TEMPLATE": "User question: \"{query}\"\nAvailable tools: {tool_definitions}\nDecide route: [retrieve_rag, call_tool, general_chat]"
            }
            return _PROMPTS_CACHE