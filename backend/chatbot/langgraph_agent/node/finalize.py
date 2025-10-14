# ./node/finalize.py
import json
from typing import Dict, Any
from core import TOOL_REGISTRY, USE_FAST_ROUTER, ROUTING_MODEL_URL, ROUTING_MODEL_NAME, ROUTING_MODEL_KEY, QWEN_MODEL, ENABLE_VERBOSE_LOGGING, call_qwen_sync

model = QWEN_MODEL
base_url = ROUTING_MODEL_URL if USE_FAST_ROUTER and ROUTING_MODEL_URL and ROUTING_MODEL_NAME else None
api_key = ROUTING_MODEL_KEY if USE_FAST_ROUTER and ROUTING_MODEL_KEY else None
purpose = "generation"

def node_finalize(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据第一轮生成结果以及后续调用结果生成最终答案
    """
    messages = state.get("messages", [])
    retrieved = state.get("retrieved") or []
    route = state.get("route")

    system_prompt = ""

    if retrieved:
        # 构建来源文档摘要
        context_str = "\n\n".join([
            f"来源 {i+1}: {doc.get('source_file', '未知')}\n内容: {(doc.get('_text') or doc.get('content') or '')[:500]}"
            for i, doc in enumerate(retrieved) if doc and (doc.get('_text') or doc.get('content'))
        ])
        if context_str:
            system_prompt = (
                "你是一个知识型助手。下面是一些参考资料，请根据这些内容回答用户的问题。\n\n"
                f"{context_str}\n\n"
                "请确保你的回答基于提供的资料，并在可能的情况下给出来源编号。如果无法从资料中找到答案，可以说明无法确定。"
            )
        else:
            system_prompt = "你是一个知识型助手，请根据已有对话内容回答用户的问题。"
    elif route == "":
        system_prompt = "你是一个知识型助手，请根据已有对话内容回答用户问题。"
    else:
        system_prompt = "你是一个知识型助手，请根据已有对话内容和路由信息生成回答。"

    # 调用模型生成最终答案
    answer = call_qwen_sync(messages, system_prompt=system_prompt, temperature=0.2, purpose=purpose)

    return {"final_answer": answer}
