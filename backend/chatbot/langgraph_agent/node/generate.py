import json
from typing import Dict, Any, Optional, Iterator
import random
import time
from core import TOOL_REGISTRY, USE_FAST_ROUTER, ROUTING_MODEL_URL, ROUTING_MODEL_NAME, ROUTING_MODEL_KEY, QWEN_MODEL, ENABLE_VERBOSE_LOGGING, call_qwen_sync
import threading
import os
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

def _string_to_llm_stream(text: str) -> Iterator[str]:
    """
    模拟打字机风格 LLM 流输出：
    - 每次输出随机长度的字符块
    - 每次输出之间间隔随机时间
    """
    if not text:
        return

    idx = 0
    while idx < len(text):
        # 随机决定本次输出长度，最少1，最多10个字符，可根据需求调整
        chunk_size = random.randint(1, 10)
        piece = text[idx: idx + chunk_size]
        idx += chunk_size

        simulated_chunk = {
            "choices": [
                {
                    "delta": {"content": piece},
                    "finish_reason": None,
                    "index": 0
                }
            ]
        }
        yield json.dumps(simulated_chunk, ensure_ascii=False)

        # 随机暂停时间，0.02~0.2秒之间，可调节
        time.sleep(random.uniform(0.02, 0.2))

# --- 【新增】Prompt 加载与缓存逻辑 ---
_PROMPTS_CACHE = None
_PROMPTS_LOCK = threading.Lock()
# 定义配置文件的路径 (与此文件在同一目录下)
PROMPT_FILE_PATH = os.path.join(os.path.dirname(__file__), ".prompts.json")

def load_prompts() -> Dict[str, str]:
    """
    加载并缓存 .prompts.json 文件。
    在 Python 端处理 CORE_PERSONA 的替换。
    """
    global _PROMPTS_CACHE
    # 1. 检查缓存 (无锁)
    if _PROMPTS_CACHE is not None:
        return _PROMPTS_CACHE

    # 2. 加锁
    with _PROMPTS_LOCK:
        # 3. 再次检查缓存 (防止竞态)
        if _PROMPTS_CACHE is not None:
            return _PROMPTS_CACHE

        try:
            if ENABLE_VERBOSE_LOGGING:
                print(f"Loading prompts from {PROMPT_FILE_PATH}")
                
            with open(PROMPT_FILE_PATH, 'r', encoding='utf-8') as f:
                templates = json.load(f)
            
            core_persona = templates.get("CORE_PERSONA", "AI助手")
            
            # 4. 手动执行模板替换
            processed_prompts = {
                # RAG 模板保留 {context_str} 占位符
                "RETRIEVED_PROMPT_TEMPLATE": templates.get("RETRIEVED_PROMPT_TEMPLATE", ""),
                
                # 其他模板替换 {CORE_PERSONA}
                "NEEDS_CLARIFICATION_PROMPT": templates.get("NEEDS_CLARIFICATION_PROMPT_TEMPLATE", "").format(CORE_PERSONA=core_persona),
                
                "GENERAL_CHAT_PROMPT": templates.get("GENERAL_CHAT_PROMPT_TEMPLATE", "").format(CORE_PERSONA=core_persona),
                
                "DEFAULT_PROMPT": templates.get("DEFAULT_PROMPT_TEMPLATE", "").format(CORE_PERSONA=core_persona)
            }

            # 5. 存入缓存
            _PROMPTS_CACHE = processed_prompts
            return _PROMPTS_CACHE

        except Exception as e:
            if ENABLE_VERBOSE_LOGGING:
                print(f"❌ ERROR: Failed to load prompts from {PROMPT_FILE_PATH}: {e}")
            # 返回一个安全的兜底值
            _PROMPTS_CACHE = {
                "RETRIEVED_PROMPT_TEMPLATE": "请基于以下信息回答：\n{context_str}",
                "NEEDS_CLARIFICATION_PROMPT": "你的问题不够清晰，请详细说明。",
                "GENERAL_CHAT_PROMPT": "你好，有什么可以帮你的吗？",
                "DEFAULT_PROMPT": "你好，请问有什么可以帮到你？"
            }
            return _PROMPTS_CACHE
def node_generate(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成答案。
    (描述保持不变...)
    """
    messages = state.get("messages", [])
    retrieved = state.get("retrieved") or []
    route = state.get("route")

    # --- 情况 1: generate_selection ---
    # (这部分逻辑保持不变)
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
    # (这部分逻辑保持不变)
    if route == "call_tool" and contains_successful_plugin_installation(messages):
        if ENABLE_VERBOSE_LOGGING:
            print("[Plugin Install Detector] 插件安装成功，返回固定提示。")
        answer_text = "插件安装成功！您现在可以使用这个插件了。"
        return {"answer": _string_to_llm_stream(answer_text)}

    # ==========================================================
    # --- 其余：构建 system_prompt 并调用 LLM ---
    # 【重大修改】从 .prompts.json 加载提示词
    # ==========================================================
    
    # 【新增】加载缓存的 prompts
    prompts = load_prompts()
    
    system_prompt = ""
    if retrieved:
        context_str = "\n\n".join([
            f"来源 {i+1}: {doc.get('source_file', '未知')}\n内容: {(doc.get('_text') or doc.get('content') or '')[:500]}"
            for i, doc in enumerate(retrieved) if doc
        ])
        
        # 【修改】使用 .format() 填充占位符
        system_prompt = prompts["RETRIEVED_PROMPT_TEMPLATE"].format(
            context_str=context_str
        )
        
        if ENABLE_VERBOSE_LOGGING:
            print("检索到的内容：", context_str)
    
    elif route == "needs_clarification":
        # 【修改】使用加载的 prompt
        system_prompt = prompts["NEEDS_CLARIFICATION_PROMPT"]
    
    elif route == "general_chat":
        # 【修改】使用加载的 prompt
        system_prompt = prompts["GENERAL_CHAT_PROMPT"]
    
    else:
        # 【修改】使用加载的 prompt
        system_prompt = prompts["DEFAULT_PROMPT"]

    # ==========================================================
    # (后续逻辑保持不变)
    # ==========================================================

    if ENABLE_VERBOSE_LOGGING:
        print("message:", messages)
        print("system_prompt:", system_prompt)

    answer = call_qwen_sync(messages, system_prompt=system_prompt, temperature=0.2, purpose=purpose)

    if ENABLE_VERBOSE_LOGGING:
        print("!!!!!!!!!!!!!!answer in generate:")

    return {"answer": answer}