# ./node/generate.py
import json
from typing import Dict, Any, Iterator, Union
from core import TOOL_REGISTRY, USE_FAST_ROUTER, ROUTING_MODEL_URL, ROUTING_MODEL_NAME, ROUTING_MODEL_KEY, QWEN_MODEL, ENABLE_VERBOSE_LOGGING, call_qwen_sync
model = QWEN_MODEL
base_url = ROUTING_MODEL_URL if USE_FAST_ROUTER and ROUTING_MODEL_URL and ROUTING_MODEL_NAME else None
api_key = ROUTING_MODEL_KEY if USE_FAST_ROUTER and ROUTING_MODEL_KEY else None
purpose = "generation"
def node_generate(state: Dict[str, Any]) -> Dict[str, Any]:
    """生成答案"""
    messages = state.get("messages", [])
    retrieved = state.get("retrieved") or []
    route = state.get("route")
    
    system_prompt = "你是一个中立且乐于助人的 AI 助手。请根据对话历史和你的知识来回答。"

    if retrieved:
        context_str = "\n\n".join([
            f"来源 {i+1}: {doc.get('source_file', '未知')}\n内容: {(doc.get('_text') or doc.get('content') or '')[:500]}"
            for i, doc in enumerate(retrieved) if doc
        ])
        system_prompt = (f"你是一个课程问答助手。请严格基于以下检索到的信息和对话历史来回答问题。\n\n"
                         f"### 检索到的信息 ###\n{context_str}\n\n"
                         "请用中文简洁回答，并引用相关来源（如来源1、来源2等）。如果信息不足，请明确说明。")
    elif route == "needs_clarification":
        system_prompt = "你是一个乐于助人的AI助手。用户的问题不够清晰，请你生成一个问题来向用户请求澄清。"
    elif route == "general_chat":
        system_prompt = "你是一个友好、乐于助人的 AI 助手。请自然地回答用户的问题，保持对话的连贯性。"

    answer = call_qwen_sync(messages, system_prompt=system_prompt, temperature=0.2, purpose="generation")
    print("!!!!!!!!!!!!!!answer in generate:", answer)
    return {"answer": answer}