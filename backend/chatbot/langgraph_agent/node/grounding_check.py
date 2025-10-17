# ./node/grounding_check.py
import traceback
from typing import Dict, Any
from core import ENABLE_GROUNDING_CHECK, ENABLE_VERBOSE_LOGGING, call_qwen_sync, GROUNDING_MODEL, RESPONSE_TEMPLATES

# 缓存最近 tool_message 的 grounding 结果
_TOOL_MESSAGE_CACHE: Dict[str, bool] = {}

def node_grounding_check(state: Dict[str, Any], force_check: bool = False) -> Dict[str, Any]:
    """
    Grounding 检查，只针对最新 tool_message 或 answer，忽略历史 memory
    """
    print("!!!!!!!!!!!!!!state in grounding_check:", state)

    if not state.get("enable_grounding", ENABLE_GROUNDING_CHECK):
        if ENABLE_VERBOSE_LOGGING:
            print("⏭️  GROUNDING CHECK: Disabled")
        return {"is_grounded": True}

    # 获取最新 tool_message 或 answer
    tool_message = state.get("tool_message") or state.get("answer")
    if not tool_message:
        if ENABLE_VERBOSE_LOGGING:
            print("⚠️  No tool_message found, defaulting to grounded=True")
        return {"is_grounded": True}

    # 规范化文本作为缓存 key
    cache_key = tool_message.strip()

    # 如果是模板内容，直接认为 grounded
    if tool_message in RESPONSE_TEMPLATES.values():
        if ENABLE_VERBOSE_LOGGING:
            print("⏭️  Tool message matches template, considered grounded")
        _TOOL_MESSAGE_CACHE[cache_key] = True
        return {"is_grounded": True}

    # 检查缓存
    if not force_check and cache_key in _TOOL_MESSAGE_CACHE:
        if ENABLE_VERBOSE_LOGGING:
            print(f"⏱️  Grounding result from cache: {_TOOL_MESSAGE_CACHE[cache_key]}")
        return {"is_grounded": _TOOL_MESSAGE_CACHE[cache_key]}

    # 调用 grounding 模型进行验证
    prompt = "只回答yes"
    try:
        verification = call_qwen_sync(
            [{"role": "user", "content": prompt}],
            model=GROUNDING_MODEL,
            temperature=0.0,
            purpose="grounding"
        )
        is_grounded = "yes" in verification.lower()
        _TOOL_MESSAGE_CACHE[cache_key] = is_grounded

        if ENABLE_VERBOSE_LOGGING:
            print(f"✓ GROUNDING: {is_grounded}")
        return {"is_grounded": is_grounded}
    except Exception:
        traceback.print_exc()
        _TOOL_MESSAGE_CACHE[cache_key] = True
        return {"is_grounded": True}
