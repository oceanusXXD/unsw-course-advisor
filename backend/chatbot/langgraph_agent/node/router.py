# ./node/router.py
import json, uuid
from typing import Dict, Any, Iterator
from core import TOOL_REGISTRY, USE_FAST_ROUTER, ROUTING_MODEL_URL, ROUTING_MODEL_NAME, ROUTING_MODEL_KEY, QWEN_MODEL, ENABLE_VERBOSE_LOGGING, call_qwen_sync

def node_router(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据用户问题进行路由决策。
    每次迭代返回增量 JSON 字符串（与node_generate类似）。
    """
    print("!!!!!!!!!!!!!!state in router:", state)
    query = state.get("query", "")
    tool_definitions = json.dumps([
        {"name": name, "description": details["description"], "args": details["args"]}
        for name, details in TOOL_REGISTRY.items()
    ], ensure_ascii=False)

    prompt = f"""你是一个智能路由机器人。根据用户的问题，决定下一步的最佳行动。可用的行动如下：
1. `retrieve_rag`: 当用户询问课程的具体信息，如先修课程、学分、课程代码、教学大纲(syllabus)等。
2. `call_tool`: 当用户意图可以通过调用工具来完成时。
3. `general_chat`: 对于其他所有问题，如问候、常识性问题、自我介绍等。

可用的工具如下:
{tool_definitions}

用户问题: "{query}"

请只返回一个JSON对象，格式如下:
- 如果选择 `retrieve_rag` 或 `general_chat`，返回: {{\"route\": \"行动名称\"}}
- 如果选择 `call_tool`，返回: {{\"route\": \"call_tool\", \"tool_name\": \"工具名称\", \"tool_args\": {{\"参数1\": \"值1\", ...}}}}
"""

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
        print("!!!!!!!!!!!!!!answer_or_generator:", answer_or_generator)
        response_str = answer_or_generator  # 一次性输出
        if ENABLE_VERBOSE_LOGGING:
            print("!!!!!!!!!!!!!!response_str:", response_str)
        decision = json.loads(response_str)
        if ENABLE_VERBOSE_LOGGING:
            print("!!!!!!!!!!!!!!decision:", decision)

        route = decision.get("route")
        if route == "call_tool":
            decision["tool_call_id"] = f"call_{uuid.uuid4().hex[:16]}"
        if ENABLE_VERBOSE_LOGGING:
            print(f"🧭 ROUTE: {route}")
        return decision
    except Exception:
        if ENABLE_VERBOSE_LOGGING:
            import traceback; traceback.print_exc()
        return {"route": "general_chat"}
