import json
from typing import Dict, Any, Optional

from core import TOOL_REGISTRY, USE_FAST_ROUTER, ROUTING_MODEL_URL, ROUTING_MODEL_NAME, ROUTING_MODEL_KEY, QWEN_MODEL, ENABLE_VERBOSE_LOGGING, call_qwen_sync

model = QWEN_MODEL
base_url = ROUTING_MODEL_URL if USE_FAST_ROUTER and ROUTING_MODEL_URL and ROUTING_MODEL_NAME else None
api_key = ROUTING_MODEL_KEY if USE_FAST_ROUTER and ROUTING_MODEL_KEY else None
purpose = "generation"

def _get_last_tool_message_content(messages: list) -> Optional[Dict | str]:
    """
    辅助：返回最新 ToolMessage 的 content（可能是字符串或 dict），若无则返回 None。
    """
    if not messages:
        return None
    for msg in reversed(messages):
        if msg.__class__.__name__ == "ToolMessage":
            return getattr(msg, "content", None)
    return None

def _parse_last_tool_message(messages: list) -> Optional[Dict]:
    """
    解析最新 ToolMessage 的 content（若为 JSON 字符串则解析为 dict）。
    返回解析后的 dict 或 None。
    """
    content = _get_last_tool_message_content(messages)
    if not content:
        return None
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                fixed = content.strip().replace("'", '"')
                return json.loads(fixed)
        except Exception:
            return None
    return None

def contains_successful_plugin_installation(messages: list) -> bool:
    """
    检查最新 ToolMessage 中是否包含插件安装成功的信息
    """
    content = _get_last_tool_message_content(messages)
    if not content:
        return False

    data = None
    if isinstance(content, str):
        try:
            data = json.loads(content.strip().replace("'", '"'))
        except json.JSONDecodeError:
            return "成功" in content or "success" in content.lower()
    elif isinstance(content, dict):
        data = content

    if isinstance(data, dict):
        if data.get("status") == "success":
            return True
        if "message" in data and ("成功" in data["message"] or "success" in str(data["message"]).lower()):
            return True

    return False

def node_generate(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成答案。
    优先处理 generate_selection 的加密输出（直接返回固定模板），
    然后处理插件安装成功（固定提示），最后走 LLM 生成路径。
    """
    messages = state.get("messages", [])
    retrieved = state.get("retrieved") or []
    route = state.get("route")

    # --- 情况 1: 最新 ToolMessage 来自 generate_selection，返回 encrypted.url ---
    if route == "call_tool":
        parsed = _parse_last_tool_message(messages)
        if parsed and isinstance(parsed, dict):
            # 检查是否是 generate_selection 生成的数据（位于 parsed["data"]["meta"]["generated_by"]）
            generated_by = parsed.get("data", {}).get("meta", {}).get("generated_by")
            if generated_by == "generate_selection":
                # 读取 encrypted.url
                encrypted = parsed.get("encrypted") or {}
                url = encrypted.get("url")
                if url:
                    answer_text = f"好的，我已经帮你选好课了：{url}，你只需要下载后复制到插件中即可选课成功"
                    return {"answer": answer_text}
                else:
                    # 没有加密 URL 的兜底提示
                    return {"answer": "好的，已生成选课结果，但尚未生成加密文件（encrypted.url 未返回）。请稍后重试或联系管理员。"}

    # --- 情况 2: 插件安装成功 ---
    if route == "call_tool" and contains_successful_plugin_installation(messages):
        if ENABLE_VERBOSE_LOGGING:
            print("[Plugin Install Detector] 插件安装成功，返回固定提示。")
        return {"answer": "插件安装成功！您现在可以使用这个插件了。"}

    # --- 其余：构建 system_prompt 并调用 LLM ---
    system_prompt = ""
    if retrieved:
        context_str = "\n\n".join([
            f"来源 {i+1}: {doc.get('source_file', '未知')}\n内容: {(doc.get('_text') or doc.get('content') or '')[:500]}"
            for i, doc in enumerate(retrieved) if doc
        ])
        system_prompt = (
            f"你是一个课程问答助手。请严格基于以下检索到的信息和对话历史来回答问题。\n\n"
            f"### 检索到的信息 ###\n{context_str}\n\n"
            "请用中文简洁回答，并引用相关来源（如来源1、来源2等）。如果信息不足，请明确说明。"
        )
        if ENABLE_VERBOSE_LOGGING:
            print("检索到的内容：", context_str)
    elif route == "needs_clarification":
        system_prompt = "你是一个乐于助人的AI助手。用户的问题不够清晰，请你生成一个问题来向用户请求澄清。"
    elif route == "general_chat":
        system_prompt = "你是一个友好、乐于助人的 AI 助手。请自然地回答用户的问题，保持对话的连贯性。"
    else:
        system_prompt = "你是一个中立且乐于助人的 AI 助手。请根据对话历史和你的知识来回答。"

    if ENABLE_VERBOSE_LOGGING:
        print("message:", messages)
        print("system_prompt:", system_prompt)

    answer = call_qwen_sync(messages, system_prompt=system_prompt, temperature=0.2, purpose=purpose)

    if ENABLE_VERBOSE_LOGGING:
        print("!!!!!!!!!!!!!!answer in generate:")

    return {"answer": answer}
