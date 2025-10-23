# node_router.py

import json, uuid
from typing import Dict, Any, Iterator
from core import TOOL_REGISTRY, USE_FAST_ROUTER, ROUTING_MODEL_URL, ROUTING_MODEL_NAME, ROUTING_MODEL_KEY, QWEN_MODEL, ENABLE_VERBOSE_LOGGING, call_qwen_sync

from .prompt_loader import load_prompts



def node_router(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据用户问题进行路由决策。
    （从 prompt_loader.py 加载提示词）
    """
    print("!!!!!!!!!!!!!!state in router:",state)
    query = state.get("query", "")
    
    # 添加插件安装工具定义 (逻辑不变)
    if "plugin_install" not in TOOL_REGISTRY:
        TOOL_REGISTRY["plugin_install"] = {
            "description": "当用户明确要求安装、更新或添加系统插件时使用此工具（无需参数）",
            "args": {}
        }

    tool_definitions = json.dumps([
        {"name": name, "description": details["description"], "args": details["args"]}
        for name, details in TOOL_REGISTRY.items()
    ], ensure_ascii=False)

    prompts = load_prompts()
    
    # 2. 获取路由模板
    router_template = prompts.get("ROUTER_PROMPT_TEMPLATE")
    
    # 3. 动态填充模板
    prompt = router_template.format(
        tool_definitions=tool_definitions,
        query=query
    )
    # ==========================================================

    try:
        model = ROUTING_MODEL_NAME if USE_FAST_ROUTER and ROUTING_MODEL_URL and ROUTING_MODEL_NAME else QWEN_MODEL
        base_url = ROUTING_MODEL_URL if USE_FAST_ROUTER and ROUTING_MODEL_URL and ROUTING_MODEL_NAME else None
        api_key = ROUTING_MODEL_KEY if USE_FAST_ROUTER and ROUTING_MODEL_KEY else None
        purpose = "routing_fast" if USE_FAST_ROUTER and ROUTING_MODEL_URL else "routing"

        answer_or_generator = call_qwen_sync(
            [{"role": "user", "content": prompt}],
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=0.0,
            purpose=purpose,
            stream=False  # 一次性返回完整答案
        )
        print("!!!!!!!!!!!!!!answer_or_generator:")
        response_str = answer_or_generator  # 一次性输出
        if ENABLE_VERBOSE_LOGGING:
            print("!!!!!!!!!!!!!!response_str:")
        decision = json.loads(response_str)
        if ENABLE_VERBOSE_LOGGING:
            print("!!!!!!!!!!!!!!decision:",decision)

        route = decision.get("route")
        if route == "call_tool":
            decision["tool_call_id"] = f"call_{uuid.uuid4().hex[:16]}"
            # 如果是安装插件调用，确保没有tool_args
            if decision.get("tool_name") == "plugin_install":
                decision.pop("tool_args", None)  # 移除可能存在的tool_args
                decision["is_plugin_installation"] = True
        if ENABLE_VERBOSE_LOGGING:
            print(f"🧭 ROUTE: {route}")
        return decision
    except Exception:
        if ENABLE_VERBOSE_LOGGING:
            import traceback; traceback.print_exc()
        return {"route": "general_chat"}