# node_generate.py

import json
from typing import Dict, Any, Optional, Iterator
from core import TOOL_REGISTRY, USE_FAST_ROUTER, ROUTING_MODEL_URL, ROUTING_MODEL_NAME, ROUTING_MODEL_KEY, QWEN_MODEL, ENABLE_VERBOSE_LOGGING, call_qwen_sync
from .prompt_loader import load_prompts


model = QWEN_MODEL
base_url = ROUTING_MODEL_URL if USE_FAST_ROUTER and ROUTING_MODEL_URL and ROUTING_MODEL_NAME else None
api_key = ROUTING_MODEL_KEY if USE_FAST_ROUTER and ROUTING_MODEL_KEY else None
purpose = "generation"


def _get_last_tool_message_content(messages: list) -> Optional[Dict | str]:
    if not messages: return None
    for msg in reversed(messages):
        if msg.__class__.__name__ == "ToolMessage":
            return getattr(msg, "content", None)
    return None

def _parse_last_tool_message(messages: list) -> Optional[Dict]:
    content = _get_last_tool_message_content(messages)
    if not content: return None
    if isinstance(content, dict): return content
    if isinstance(content, str):
        try:
            try: return json.loads(content)
            except json.JSONDecodeError:
                fixed = content.strip().replace("'", '"')
                return json.loads(fixed)
        except Exception: return None
    return None

def contains_successful_plugin_installation(messages: list) -> bool:
    content = _get_last_tool_message_content(messages)
    if not content: return False
    data = None
    if isinstance(content, str):
        try: data = json.loads(content.strip().replace("'", '"'))
        except json.JSONDecodeError:
            return "成功" in content or "success" in content.lower()
    elif isinstance(content, dict): data = content
    if isinstance(data, dict):
        if data.get("status") == "success": return True
        if "message" in data and ("成功" in data["message"] or "success" in str(data["message"]).lower()):
            return True
    return False

def _string_to_llm_stream(text: str) -> Iterator[str]:
    if not text: return
    for char in text:
        simulated_chunk = {
            "choices": [{"delta": {"content": char}, "finish_reason": None, "index": 0}],
        }
        yield json.dumps(simulated_chunk, ensure_ascii=False)
        


def node_generate(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成答案
    """
    messages = state.get("messages", [])
    retrieved = state.get("retrieved") or []
    route = state.get("route")

    # --- 情况 1: generate_selection ---
    if route == "call_tool":
        parsed = _parse_last_tool_message(messages)
        if parsed and isinstance(parsed, dict):
            generated_by = parsed.get("data", {}).get("meta", {}).get("generated_by")
            if generated_by == "generate_selection":
                encrypted = parsed.get("encrypted") or {}
                url = encrypted.get("url")
                if url:
                    answer_text = f"好的，我已经帮你选好课了：{url}，你只需要下载后复制到插件中即可选课成功"
                    return {"answer": _string_to_llm_stream(answer_text)}
                else:
                    answer_text = "好的，已生成选课结果，但尚未生成加密文件（encrypted.url 未返回）。请稍后重试或联系管理员。"
                    return {"answer": _string_to_llm_stream(answer_text)}

    # --- 情况 2: 插件安装成功 ---
    if route == "call_tool" and contains_successful_plugin_installation(messages):
        if ENABLE_VERBOSE_LOGGING:
            print("[Plugin Install Detector] 插件安装成功，返回固定提示。")
        answer_text = "插件安装成功！您现在可以使用这个插件了。"
        return {"answer": _string_to_llm_stream(answer_text)}
    prompts = load_prompts()
    
    system_prompt = ""
    if retrieved:
        context_str = "\n\n".join([
            f"来源 {i+1}: {doc.get('source_file', '未知')}\n内容: {(doc.get('_text') or doc.get('content') or '')[:500]}"
            for i, doc in enumerate(retrieved) if doc
        ])
        
        system_prompt = prompts["RETRIEVED_PROMPT_TEMPLATE"].format(
            context_str=context_str
        )
        
        if ENABLE_VERBOSE_LOGGING:
            print("检索到的内容：", context_str)
    
    elif route == "needs_clarification":
        system_prompt = prompts["NEEDS_CLARIFICATION_PROMPT"]
    
    elif route == "general_chat":
        system_prompt = prompts["GENERAL_CHAT_PROMPT"]
    
    else:
        system_prompt = prompts["DEFAULT_PROMPT"]

    if ENABLE_VERBOSE_LOGGING:
        print("message:", messages)
        print("system_prompt:", system_prompt)

    answer = call_qwen_sync(messages, system_prompt=system_prompt, temperature=0.2, purpose=purpose)

    if ENABLE_VERBOSE_LOGGING:
        print("!!!!!!!!!!!!!!answer in generate:")

    return {"answer": answer}