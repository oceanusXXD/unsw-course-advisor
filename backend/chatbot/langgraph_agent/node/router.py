# ./node/router.py
import json, uuid
from typing import Dict, Any
from core import TOOL_REGISTRY, USE_FAST_ROUTER, ROUTING_MODEL_URL, ROUTING_MODEL_NAME, ROUTING_MODEL_KEY, QWEN_MODEL, ENABLE_VERBOSE_LOGGING, call_qwen_sync

def node_router(state: Dict[str, Any]) -> Dict[str, Any]:
    query = state.get("query", "")
    tool_definitions = json.dumps([
        {"name": name, "description": details["description"], "args": details["args"]}
        for name, details in TOOL_REGISTRY.items()
    ], ensure_ascii=False)
    prompt = f"""你是一个智能路由机器人。根据用户的问题，决定下一步的最佳行动。可用的行动如下：
1. `retrieve_rag`: 当用户询问课程的具体信息，如先修课程、学分、课程代码、教学大纲(syllabus)等。
2. `call_tool`: 当用户意图可以通过调用工具来完成时。
3. `needs_clarification`: 当用户的问题含糊不清，需要更多信息才能准确回答时。
4. `general_chat`: 对于其他所有问题，如问候、常识性问题、自我介绍等。

可用的工具如下:
{tool_definitions}

用户问题: "{query}"

请只返回一个JSON对象，格式如下:
- 如果选择 `retrieve_rag` 或 `general_chat` 或 `needs_clarification`，返回: {{\"route\": \"行动名称\"}}
- 如果选择 `call_tool`，返回: {{\"route\": \"call_tool\", \"tool_name\": \"工具名称\", \"tool_args\": {{\"参数1\": \"值1\", ...}}}}
"""
    try:
        if USE_FAST_ROUTER and ROUTING_MODEL_URL and ROUTING_MODEL_NAME:
            if ENABLE_VERBOSE_LOGGING:
                print(f"🚀 Using fast router: {ROUTING_MODEL_NAME}")
            response_str = call_qwen_sync(
                [{"role": "user", "content": prompt}],
                model=ROUTING_MODEL_NAME,
                base_url=ROUTING_MODEL_URL,
                api_key=ROUTING_MODEL_KEY if ROUTING_MODEL_KEY else None,
                temperature=0.0,
                purpose="routing_fast"
            )
        else:
            response_str = call_qwen_sync(
                [{"role": "user", "content": prompt}],
                model=QWEN_MODEL,
                temperature=0.0,
                purpose="routing"
            )
        decision = json.loads(response_str)
        route = decision.get("route")
        if ENABLE_VERBOSE_LOGGING:
            print(f"🧭 ROUTE: {route}")
        if route == "call_tool":
            decision["tool_call_id"] = f"call_{uuid.uuid4().hex[:16]}"
        return decision
    except Exception:
        if ENABLE_VERBOSE_LOGGING:
            import traceback; traceback.print_exc()
        return {"route": "general_chat"}
