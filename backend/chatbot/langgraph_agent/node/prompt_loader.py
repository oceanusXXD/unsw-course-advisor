# prompt_loader.py
"""
【单一职责 - 动态加载版】
此文件负责从 .prompts.json 动态加载、处理和缓存所有提示词模板。
它会自动格式化包含 {CORE_PERSONA} 的模板。
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
    【动态加载版】
    加载并缓存 .prompts.json 文件。
    - 自动处理 {CORE_PERSONA} 的替换。
    - 自动重命名 _TEMPLATE -> 最终键名。
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
                print(f"[Dynamic Loader] Loading prompts from {PROMPT_FILE_PATH}")
                
            with open(PROMPT_FILE_PATH, 'r', encoding='utf-8') as f:
                templates = json.load(f)
            
            # 4. 提取并移除 CORE_PERSONA，它不是一个模板
            core_persona = templates.pop("CORE_PERSONA", "AI助手")
            
            processed_prompts = {}

            # 5. 【核心】动态遍历所有剩余的键
            for key, template_string in templates.items():
                if not isinstance(template_string, str):
                    processed_prompts[key] = template_string
                    continue

                final_key = key
                final_value = template_string

                # 6. 检查是否需要格式化
                if "{CORE_PERSONA}" in template_string:
                    try:
                        final_value = template_string.format(CORE_PERSONA=core_persona)
                        
                        # 7. 自动重命名：
                        # 如果格式化成功，并且键名以 _TEMPLATE 结尾
                        if key.endswith("_TEMPLATE"):
                            final_key = key[:-9] # 移除 "_TEMPLATE"
                            if ENABLE_VERBOSE_LOGGING:
                                print(f"  > Processing: {key} -> {final_key} (Formatted)")
                                
                    except Exception as e:
                        # 捕获格式化错误 (比如模板中还有 {context_str} 等)
                        if ENABLE_VERBOSE_LOGGING:
                            print(f"  > Warning: Skipping format for {key} (multiple placeholders?): {e}")
                        final_value = template_string
                
                else:
                    # 不需要格式化 (例如 RETRIEVED_PROMPT_TEMPLATE)
                    if ENABLE_VERBOSE_LOGGING:
                         print(f"  > Processing: {key} (As-is)")
                    pass

                processed_prompts[final_key] = final_value
            
            # 8. 存入缓存
            _PROMPTS_CACHE = processed_prompts
            return _PROMPTS_CACHE

        except Exception as e:
            if ENABLE_VERBOSE_LOGGING:
                print(f"❌ ERROR: Failed to load prompts dynamically from {PROMPT_FILE_PATH}: {e}")
            # 返回一个安全的兜底值
            _PROMPTS_CACHE = {
                "DEFAULT_PROMPT": "你好，请问有什么可以帮到你？"
            }
            return _PROMPTS_CACHE