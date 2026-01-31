# backend/chatbot/langgraph_agent/node/prepare_input.py
from typing import Dict, Any, List
import json

from langchain_core.messages import HumanMessage, SystemMessage

from ..state import ChatState

def _build_long_term_snippet(long_term_summary: Any) -> str:
    """
    将 long_term_summary（JSON 字符串或 dict）转为可读片段。
    期望字段: identity, goals, preferences, constraints, skills
    """
    if not long_term_summary:
        return ""
    data = None
    if isinstance(long_term_summary, dict):
        data = long_term_summary
    else:
        try:
            data = json.loads(str(long_term_summary))
            if not isinstance(data, dict):
                data = None
        except Exception:
            data = None

    if not data:
        # 非 JSON，直接作为偏好文本
        return str(long_term_summary)[:1200]

    labels = {
        "identity": "身份/背景",
        "goals": "目标",
        "preferences": "偏好",
        "constraints": "约束",
        "skills": "技能/已学",
    }
    lines: List[str] = []
    for k, label in labels.items():
        v = data.get(k)
        if not v:
            continue
        if isinstance(v, list):
            vv = [str(x) for x in v if x]
            if vv:
                lines.append(f"{label}: " + "；".join(vv[:5]))
        else:
            lines.append(f"{label}: {str(v)[:200]}")
    return "\n".join(lines)[:1200]


def _has_system_message(messages: Any) -> bool:
    """
    防御性判断是否已存在 SystemMessage，避免重复注入。
    兼容 BaseMessage 和 dict 形式。
    """
    if not messages:
        return False
    try:
        for m in messages:
            # LangChain BaseMessage 有 .type 属性
            t = getattr(m, "type", None)
            if t == "system":
                return True
            if isinstance(m, dict) and m.get("role") == "system":
                return True
    except Exception:
        pass
    return False


def node_prepare_input(state: ChatState) -> Dict[str, Any]:
    """
    [LangGraph 节点] - 准备输入消息
    1) 基于长期记忆注入一条 SystemMessage（如果当前对话里还没有）
    2) 把本轮 query 转成 HumanMessage
    """
    query = (state.get("query") or "").strip()
    new_messages: List[Any] = []

    # 从 state.memory 读取长期摘要（你在 run_chat 里已按 tab_id 加载）
    memory = state.get("memory") or {}
    long_term_summary = memory.get("long_term_summary", "")

    # 如果当前对话中还没有系统消息，则注入一条
    if not _has_system_message(state.get("messages")):
        user_profile_snippet = _build_long_term_snippet(long_term_summary)
        system_prompt = (
            "你是 UNSW 的学术助手。\n"
            "用户长期画像（跨页面积累）：\n"
            f"{user_profile_snippet or '(暂无)'}\n\n"
            "使用说明：\n"
            "- 仅当与当前问题相关时参考上述画像；不相关则忽略。\n"
            "- 回答准确、克制，不要臆测；默认中文简洁回答。\n"
        )
        new_messages.append(SystemMessage(content=system_prompt))

    # 注入本轮用户消息
    if query:
        new_messages.append(HumanMessage(content=query))

    # 返回新增消息，LangGraph 的 add_messages 聚合器会自动追加
    return {"messages": new_messages}