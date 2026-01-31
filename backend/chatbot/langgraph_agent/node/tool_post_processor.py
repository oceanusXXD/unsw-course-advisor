# backend/chatbot/langgraph_agent/node/tool_post_processor.py

from typing import Dict, Any, Optional, List, Literal
import json
import re
import time  #  需要用于打字机效果

from ..state import ChatState
from ..core import emit_stream_token

# =================================================================
# 辅助函数
# =================================================================
def _parse_last_tool_result(state: ChatState) -> Optional[Any]:
    """解析最近一条工具消息的结果（JSON 或纯文本）"""
    messages = state.get("messages", [])
    for msg in reversed(messages or []):
        # LangChain 的 ToolMessage 对象或字典
        if (hasattr(msg, 'type') and msg.type == "tool") or \
           (isinstance(msg, dict) and msg.get("role") == "tool"):
            content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
            if isinstance(content, str):
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return content
            return content
    return None

def _handle_generate_selection_reply(parsed_result: Any) -> Optional[str]:
    """处理选课文件生成的固定回复"""
    if not (isinstance(parsed_result, dict) and "data" in parsed_result and "encrypted" in parsed_result):
        return None
    data = parsed_result.get("data", {})
    encrypted = parsed_result.get("encrypted", {})
    url = encrypted.get("url")
    selected = data.get("selected", [])
    courses = [item.get("course_code") for item in selected if isinstance(item, dict)]
    courses_str = ", ".join(courses) if courses else "未知课程"
    if url:
        return (
            f"[OK] 选课文件生成成功！\n\n"
            f"[Docs] 包含课程：{courses_str}\n"
            f"[Link] 下载链接：{url}\n\n"
            f"[Steps] 使用步骤：\n"
            f"1. 点击链接下载加密文件\n"
            f"2. 打开浏览器选课插件\n"
            f"3. 导入下载的文件\n"
            f"4. 插件将自动为你完成选课\n\n"
            f"[Note] 文件有效期：24小时\n\n"
            f"祝你选课顺利！如有其他问题，随时问我。"
        )
    else:
        error_msg = encrypted.get("error", "未知错误")
        return f"[ERR] 选课文件生成失败：{error_msg}\n\n请稍后重试或联系技术支持。"

def _handle_plugin_install_reply(parsed_result: Any) -> Optional[str]:
    """处理插件安装的固定回复"""
    if not parsed_result:
        return None
    success = False
    if isinstance(parsed_result, dict):
        if parsed_result.get("status") == "success":
            success = True
        if "message" in parsed_result and ("成功" in str(parsed_result["message"]) or "success" in str(parsed_result["message"]).lower()):
            success = True
    elif isinstance(parsed_result, str):
        if "成功" in parsed_result or "success" in parsed_result.lower():
            success = True
    if success:
        return (
            "[OK] 插件安装成功！\n\n"
            "现在你可以：\n"
            "1. 询问我课程信息（如\"COMP1511 的先修课程\"）\n"
            "2. 让我帮你选课（如\"帮我选 COMP1511\"）\n"
            "3. 使用插件自动完成选课流程"
        )
    return None

def _has_recent_tool_message(messages: List[Any], lookback: int = 4) -> bool:
    """最近几条消息中是否存在工具返回"""
    if not messages:
        return False
    window = messages[-lookback:]
    for m in window:
        if (hasattr(m, "type") and getattr(m, "type", None) == "tool") or \
           (isinstance(m, dict) and m.get("role") == "tool"):
            return True
    return False

# =================================================================
# 条件边函数
# =================================================================
def check_if_fixed_reply_exists(state: ChatState) -> Literal["generate_fixed_reply", "generate_with_llm"]:
    """
    [条件边] 仅当工具名命中，且最近确实有工具返回时，才走固定回复
    """
    tool_name = state.get("tool_name")
    if tool_name in ("generate_selection", "plugin_install", "install_plugin"):
        messages = state.get("messages", []) or []
        if _has_recent_tool_message(messages, lookback=4):
            return "generate_fixed_reply"
    return "generate_with_llm"

# =================================================================
# 节点主函数
# =================================================================
def node_tool_post_processor(state: ChatState) -> Dict[str, Any]:
    """
    [节点] 工具后处理器：将工具返回转换为固定的自然语言回复
    """
    tool_name = state.get("tool_name")
    session_id = str(state.get("run_id")) if state.get("run_id") else ""
    
    parsed_result = _parse_last_tool_result(state)
    answer_text = None

    if tool_name == "generate_selection":
        answer_text = _handle_generate_selection_reply(parsed_result)
    elif tool_name in ("plugin_install", "install_plugin"):
        answer_text = _handle_plugin_install_reply(parsed_result)
        
    if answer_text:
        # 打字机效果输出
        if session_id:
            for char in answer_text:
                emit_stream_token(session_id, char)
                time.sleep(0.01)
        
        # 关键：清理状态，避免重复触发固定回复
        # 注意：ChatState 对 pending_* 使用 keep_if_not_none reducer，None 不会覆盖旧值
        # 因此这里使用 {} 来“清空”，其布尔值为 False，后续分支不会再命中
        return {
            "answer": answer_text,
            "tool_name": None,
            "tool_args": None,
            "pending_file_generation": {},  # 用空 dict 表示清空，避免 keep_if_not_none 屏蔽
            "pending_plugin_install": {},   # 同上
        }
        
    # 没有固定回复，交给 generate 节点继续
    return {}