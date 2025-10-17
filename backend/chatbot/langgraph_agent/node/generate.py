# ./node/generate.py
import json
from typing import Dict, Any
from core import TOOL_REGISTRY, USE_FAST_ROUTER, ROUTING_MODEL_URL, ROUTING_MODEL_NAME, ROUTING_MODEL_KEY, QWEN_MODEL, ENABLE_VERBOSE_LOGGING, call_qwen_sync

model = QWEN_MODEL
base_url = ROUTING_MODEL_URL if USE_FAST_ROUTER and ROUTING_MODEL_URL and ROUTING_MODEL_NAME else None
api_key = ROUTING_MODEL_KEY if USE_FAST_ROUTER and ROUTING_MODEL_KEY else None
purpose = "generation"


def contains_successful_plugin_installation(messages) -> bool:
    """
    检查最新消息中是否包含插件安装成功（只检测最新 ToolMessage）
    支持字符串json和dict两种格式
    """
    if not messages:
        return False

    # 倒序遍历，但只处理最后一个ToolMessage
    for msg in reversed(messages):
        if msg.__class__.__name__ != "ToolMessage":
            continue

        content = getattr(msg, "content", None)
        if not content:
            continue

        # 🔹 如果是字符串（如 "{'status': 'success', ...}"）
        if isinstance(content, str):
            try:
                # 将单引号替换成双引号，然后尝试解析为JSON
                fixed_str = content.strip().replace("'", '"')
                data = json.loads(fixed_str)
            except json.JSONDecodeError:
                data = None

            # 直接文本匹配（避免解析失败）
            if "成功" in content or "success" in content.lower():
                return True

            if data and isinstance(data, dict):
                if data.get("status") == "success":
                    return True
                if "message" in data and "成功" in data["message"]:
                    return True

        # 🔹 如果是字典形式
        elif isinstance(content, dict):
            if content.get("status") == "success":
                return True
            if "message" in content and "成功" in content["message"]:
                return True

        # 找到最后一个 ToolMessage 就退出（不再往前看）
        break

    return False

def node_generate(state: Dict[str, Any]) -> Dict[str, Any]:
    """生成答案，插件安装成功固定输出"""
    messages = state.get("messages", [])
    retrieved = state.get("retrieved") or []
    route = state.get("route")

    # 如果消息中有插件安装成功，直接返回固定答案
    if route == "call_tool" and contains_successful_plugin_installation(messages):
        if ENABLE_VERBOSE_LOGGING:
            print("[Plugin Install Detector] 插件安装成功，返回固定提示。")
        return {"answer": "插件安装成功！您现在可以使用这个插件了。"}

    # 构建系统提示
    system_prompt = "你是一个中立且乐于助人的 AI 助手。请根据对话历史和你的知识来回答。"

    if retrieved:
        context_str = "\n\n".join([
            f"来源 {i+1}: {doc.get('source_file', '未知')}\n内容: {(doc.get('_text') or doc.get('content') or '')[:500]}"
            for i, doc in enumerate(retrieved) if doc
        ])
        system_prompt = (f"你是一个课程问答助手。请严格基于以下检索到的信息和对话历史来回答问题。\n\n"
                         f"### 检索到的信息 ###\n{context_str}\n\n"
                         "请用中文简洁回答，并引用相关来源（如来源1、来源2等）。如果信息不足，请明确说明。")
        if ENABLE_VERBOSE_LOGGING:
            print("检索到的内容：", context_str)
    elif route == "needs_clarification":
        system_prompt = "你是一个乐于助人的AI助手。用户的问题不够清晰，请你生成一个问题来向用户请求澄清。"
    elif route == "general_chat":
        system_prompt = "你是一个友好、乐于助人的 AI 助手。请自然地回答用户的问题，保持对话的连贯性。"

    if ENABLE_VERBOSE_LOGGING:
        print("message:", messages)

    # 调用生成模型
    answer = call_qwen_sync(messages, system_prompt=system_prompt, temperature=0.2, purpose="generation")

    if ENABLE_VERBOSE_LOGGING:
        print("!!!!!!!!!!!!!!answer in generate:", answer)

    return {"answer": answer}
