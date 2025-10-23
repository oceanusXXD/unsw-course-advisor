# generate.py

import json
from typing import Dict, Any, Optional, Iterator
from core import TOOL_REGISTRY, USE_FAST_ROUTER, ROUTING_MODEL_URL, ROUTING_MODEL_NAME, ROUTING_MODEL_KEY, QWEN_MODEL, ENABLE_VERBOSE_LOGGING, call_qwen_sync
from .prompt_loader import load_prompts


model = QWEN_MODEL
base_url = ROUTING_MODEL_URL if USE_FAST_ROUTER and ROUTING_MODEL_URL and ROUTING_MODEL_NAME else None
api_key = ROUTING_MODEL_KEY if USE_FAST_ROUTER and ROUTING_MODEL_KEY else None
purpose = "generation"


def _get_last_tool_message_content(messages: list) -> Optional[Dict | str]:
    """
    更鲁棒地获取最近的工具消息内容，支持多种消息形态：
    - dict 格式：{'role':'tool', 'content':...} 或 {'type':'tool', 'content':...}
    - 对象格式：具有 .type/.content 属性的对象（例如自定义 Message 对象）
    返回值可能是 dict 或 str 或 None
    """
    if not messages:
        return None

    for msg in reversed(messages):
        # dict-like 消息
        if isinstance(msg, dict):
            # 优先识别显式标识为工具消息的 dict
            if msg.get("role") == "tool" or msg.get("type") == "tool":
                # 常见字段：content / data / message
                return msg.get("content") or msg.get("data") or msg.get("message")
            # 若无 role/type，但包含 content，仍可能是工具返回
            if "content" in msg:
                return msg.get("content")
            # 其它可能包含工具结果的 key
            if "result" in msg:
                return msg.get("result")
            # 继续找上一个消息

        else:
            # 对象型消息，尝试读取属性
            try:
                cls_name = getattr(msg, "__class__", None).__name__
            except Exception:
                cls_name = None

            # 如果类名为 ToolMessage 或者有 type == 'tool'
            if cls_name == "ToolMessage" or getattr(msg, "type", None) == "tool":
                return getattr(msg, "content", None) or getattr(msg, "data", None) or getattr(msg, "message", None)

            # 通用 fallback：如果有 content 属性就返回
            if hasattr(msg, "content"):
                return getattr(msg, "content", None)

    return None

def _parse_last_tool_message(messages: list) -> Optional[Dict]:
    """
    尝试把最后的工具消息解析为 Python dict（如果可能）。
    解析策略：
      1) 如果已经是 dict，直接返回
      2) 若为字符串，尝试 json.loads
      3) 如果 json.loads 失败，尝试 ast.literal_eval（能解析 Python 字面量）
      4) 最后尝试将单引号替换成双引号再 json.loads
    """
    content = _get_last_tool_message_content(messages)
    if not content:
        return None

    # 已经是 dict
    if isinstance(content, dict):
        return content

    # 已经是 dict-like object? 尝试转换
    if hasattr(content, "to_dict"):
        try:
            return content.to_dict()
        except Exception:
            pass

    # 字符串解析
    if isinstance(content, str):
        s = content.strip()
        # 1) 标准 JSON
        try:
            return json.loads(s)
        except Exception:
            pass
        # 2) ast.literal_eval: 可以解析 Python dict/repr 风格
        try:
            val = ast.literal_eval(s)
            if isinstance(val, dict):
                return val
        except Exception:
            pass
        # 3) 宽松替换单引号 -> 双引号，再尝试 json.loads
        try:
            fixed = s.replace("'", '"')
            return json.loads(fixed)
        except Exception:
            pass
        # 4) 若都失败，返回 None
        return None

    return None


def contains_successful_plugin_installation(messages: list) -> bool:
    """
    更鲁棒的插件安装成功检测：
    - 优先解析为 dict 后看 status/message
    - 其次在原始字符串中查找 '成功' 或 'success'
    """
    parsed = _parse_last_tool_message(messages)
    if isinstance(parsed, dict):
        # 常见的 success 标记
        if parsed.get("status") == "success":
            return True
        # message 字段里含 '成功' 或 'success'
        if "message" in parsed and (("成功" in str(parsed["message"])) or ("success" in str(parsed["message"]).lower())):
            return True
        # 有时会放在 data.meta.message
        meta_msg = parsed.get("data", {}).get("meta", {}) if isinstance(parsed.get("data"), dict) else None
        if isinstance(meta_msg, dict) and (("成功" in str(meta_msg.get("message", ""))) or ("success" in str(meta_msg.get("message", "")).lower())):
            return True

    # fallback: 检查原始返回字符串
    raw = _get_last_tool_message_content(messages)
    if isinstance(raw, str) and (("成功" in raw) or ("success" in raw.lower())):
        return True

    return False

def _string_to_llm_stream(text: str) -> Iterator[str]:
    import random
    import time
    """
    【适配器】将普通字符串包装成模拟的 LLM 流。
    
    改进点：
    1. 每次 yield 随机长度的“token”块（1~5 个字符）。
    2. 每次 yield 之间随机 sleep（1~50ms）。
    """
    if not text:
        return

    i = 0
    while i < len(text):
        # 随机 token 长度
        token_len = random.randint(1, 5)
        token = text[i:i+token_len]
        i += token_len

        simulated_chunk = {
            "choices": [
                {
                    "delta": {"content": token},
                    "finish_reason": None,
                    "index": 0
                }
            ]
        }
        yield json.dumps(simulated_chunk, ensure_ascii=False)

        # 随机 sleep，模拟网络延迟或生成速度
        time.sleep(random.uniform(0.001, 0.05))
        


def node_generate(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成答案（增强版）
    - 更鲁棒地解析 tool 消息
    - 将混合消息净化为 LLM-friendly 的 messages 列表
    """
    import re, ast, json

    messages = state.get("messages", []) or []
    retrieved = state.get("retrieved") or []
    route = state.get("route")
    user_query = state.get("query") or ""

    # ---- 辅助：更宽松地在 messages 中寻找并解析 tool 返回 ----
    def _find_tool_parsed(msgs):
        # 先尝试已有解析器
        parsed = None
        try:
            parsed = _parse_last_tool_message(msgs)
            print("!!!!!!!!!!!!!!!!!!!!!!_find_tool_parsed",parsed)
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            return parsed

        # 回溯扫描所有消息内容，尝试 json / ast 解析，寻找关键字段
        for m in reversed(msgs):
            content = None
            if isinstance(m, dict):
                # 常见字段
                for k in ("content", "data", "message", "result"):
                    if k in m:
                        content = m[k]
                        break
            else:
                content = getattr(m, "content", None) or getattr(m, "data", None) or getattr(m, "message", None)

            # 若已是 dict
            if isinstance(content, dict):
                # 常见位置：data.meta.generated_by, generated_by, status/message
                if content.get("data", {}).get("meta", {}).get("generated_by") == "generate_selection":
                    return content
                if content.get("generated_by") == "generate_selection":
                    return content
                if content.get("status") == "success" or ("message" in content and ("成功" in str(content["message"]) or "success" in str(content["message"]).lower())):
                    return content

            # 若为字符串，尝试解析
            if isinstance(content, str):
                s = content.strip()
                # 快速文本搜索：如果包含关键词，尝试解析为 dict
                if any(k in s for k in ('generate_selection', '"generated_by"', "'generated_by'", 'encrypted', '"status"', '插件安装成功', '成功')):
                    # 尝试 json
                    try:
                        j = json.loads(s)
                        if isinstance(j, dict):
                            return j
                    except Exception:
                        pass
                    # 尝试 ast literal_eval（处理 python repr 风格）
                    try:
                        j = ast.literal_eval(s)
                        if isinstance(j, dict):
                            return j
                    except Exception:
                        pass
                    # 最后尝试单引号->双引号再 json.loads
                    try:
                        fixed = s.replace("'", '"')
                        j = json.loads(fixed)
                        if isinstance(j, dict):
                            return j
                    except Exception:
                        pass
        return None

    # ---- 辅助：把混合消息净化为 LLM-friendly 的 dict 列表 ----
    def _sanitize_messages(msgs, fallback_query=""):
        out = []
        for m in msgs:
            role = None
            content = None
            if isinstance(m, dict):
                role = m.get("role") or m.get("type")
                # prefer content-like fields
                content = m.get("content") or m.get("data") or m.get("message") or m.get("result")
            else:
                role = getattr(m, "role", None) or getattr(m, "type", None)
                content = getattr(m, "content", None) or getattr(m, "data", None) or getattr(m, "message", None)

            # 将 tool 视为 assistant（工具返回通常是辅助信息）
            if role == "tool":
                role = "assistant"

            if role in ("user", "assistant"):
                # normalize content to string
                if content is None:
                    content_str = ""
                elif isinstance(content, (dict, list)):
                    try:
                        content_str = json.dumps(content, ensure_ascii=False)
                    except Exception:
                        content_str = str(content)
                else:
                    content_str = str(content)
                out.append({"role": "user" if role == "user" else "assistant", "content": content_str})

        # 确保至少存在 user 消息：若没有，从 fallback_query 补上
        if not any(m["role"] == "user" for m in out) and fallback_query:
            out.insert(0, {"role": "user", "content": str(fallback_query)})
        print("!!!!!!!!!!!!!!!!!!!!!_sanitize_messages:",out)
        return out

    # --- 针对 call_tool 路由，优先尝试解析工具输出（generate_selection / encrypted.url / success 等） ---
    if route == "call_tool":
        parsed = _find_tool_parsed(messages)
        print("!!!!!!!!!!!!!!!!!!call_tollparsed,",parsed)
        if parsed and isinstance(parsed, dict):
            # 优先识别生成选课文件的场景
            generated_by = parsed.get("data", {}).get("meta", {}).get("generated_by") or parsed.get("generated_by")
            if generated_by == "generate_selection":
                encrypted = parsed.get("data", {}).get("encrypted") or parsed.get("encrypted") or parsed.get("data", {}).get("meta", {}).get("encrypted")
                if isinstance(encrypted, dict):
                    url = encrypted.get("url")
                else:
                    url = None
                if url:
                    answer_text = f"好的，我已经帮你选好课了：{url}，你只需要下载后复制到插件中即可选课成功"
                    print("!!!!!!!!!!!!!!!!!!!call_toolanswer_text",answer_text)
                    return {"answer": _string_to_llm_stream(answer_text)}
                else:
                    answer_text = "好的，已生成选课结果，但尚未生成加密文件（encrypted.url 未返回）。"
                    return {"answer": _string_to_llm_stream(answer_text)}

        # 插件安装成功检测
        if contains_successful_plugin_installation(messages):
            if ENABLE_VERBOSE_LOGGING:
                print("[Plugin Install Detector] 插件安装成功，返回固定提示。")
            answer_text = "插件安装成功！您现在可以使用这个插件了。"
            return {"answer": _string_to_llm_stream(answer_text)}

    # --- RAG / 一般生成路径：构建 system_prompt 与净化 messages 再调用 LLM ---
    prompts = load_prompts()
    if retrieved:
        context_str = "\n\n".join([
            f"来源 {i+1}: {doc.get('source_file', '未知')}\n内容: {(doc.get('_text') or doc.get('content') or '')[:500]}"
            for i, doc in enumerate(retrieved) if doc
        ])
        system_prompt = prompts["RETRIEVED_PROMPT_TEMPLATE"].format(context_str=context_str)
        if ENABLE_VERBOSE_LOGGING:
            print("检索到的内容：", context_str)
    elif route == "needs_clarification":
        system_prompt = prompts["NEEDS_CLARIFICATION_PROMPT"]
    elif route == "general_chat":
        system_prompt = prompts["GENERAL_CHAT_PROMPT"]
    else:
        system_prompt = prompts["DEFAULT_PROMPT"]

    if ENABLE_VERBOSE_LOGGING:
        print("原始 messages:", messages)
        print("构建 system_prompt:", system_prompt)

    # 将消息净化为适合 call_qwen_sync 的格式（dict 列表）
    sanitized = _sanitize_messages(messages, fallback_query=user_query)
    if ENABLE_VERBOSE_LOGGING:
        print("sanitized messages (sent to LLM):", sanitized)

    # 最后调用模型
    answer = call_qwen_sync(sanitized, system_prompt=system_prompt, temperature=0.2, purpose=purpose)

    if ENABLE_VERBOSE_LOGGING:
        print("!!!!!!!!!!!!!!answer in generate:")

    return {"answer": answer}
