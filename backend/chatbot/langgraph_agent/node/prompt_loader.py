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
    from ..core import ENABLE_VERBOSE_LOGGING
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
    - 只替换 {CORE_PERSONA}，不动其他变量。
    """
    global _PROMPTS_CACHE
    if _PROMPTS_CACHE is not None:
        return _PROMPTS_CACHE

    with _PROMPTS_LOCK:
        if _PROMPTS_CACHE is not None:
            return _PROMPTS_CACHE

        try:
            if ENABLE_VERBOSE_LOGGING:
                print(f"[Dynamic Loader] Loading prompts from {PROMPT_FILE_PATH}")

            with open(PROMPT_FILE_PATH, "r", encoding="utf-8") as f:
                templates = json.load(f)

            core_persona = templates.pop("CORE_PERSONA", "AI助手")

            processed_prompts = {}

            for key, template_string in templates.items():
                if not isinstance(template_string, str):
                    processed_prompts[key] = template_string
                    continue

                final_key = key
                final_value = template_string

                # [OK] 只替换 {CORE_PERSONA}
                if "{CORE_PERSONA}" in final_value:
                    final_value = final_value.replace("{CORE_PERSONA}", core_persona)

                if ENABLE_VERBOSE_LOGGING:
                    print(f"  > Loaded: {final_key}")

                processed_prompts[final_key] = final_value

            _PROMPTS_CACHE = processed_prompts
            return _PROMPTS_CACHE

        except Exception as e:
            if ENABLE_VERBOSE_LOGGING:
                print(f"[ERR] ERROR: Failed to load prompts dynamically from {PROMPT_FILE_PATH}: {e}")
            _PROMPTS_CACHE = {"DEFAULT_PROMPT": "你好，请问有什么可以帮到你？"}
            return _PROMPTS_CACHE
