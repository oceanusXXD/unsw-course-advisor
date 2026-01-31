# backend/chatbot/langgraph_agent/node/grounding_check.py

import traceback
import json
from typing import Dict, Any, List

# 导入强类型定义
from ..schemas import RetrievedDocument, SSEEvent
from ..state import ChatState

# 导入核心功能和 prompt 加载器
from ..core import (
    ENABLE_GROUNDING_CHECK, 
    ENABLE_VERBOSE_LOGGING, 
    call_qwen,  # [OK] 保留（向后兼容）
    call_qwen_httpx,  # [OK] 新增异步版本
    GROUNDING_MODEL, 
    RESPONSE_TEMPLATES, 
    build_context_string
)
from .prompt_loader import load_prompts

# 缓存 (cache_key) -> grounding 结果 (保持不变)
_GROUNDING_CACHE: Dict[str, bool] = {}


async def node_grounding_check(  # [OK] async def
    state: ChatState, 
    force_check: bool = False
) -> Dict[str, Any]:
    """
    [LangGraph 节点] - Grounding 检查
    
    - 检查 'answer' 是否被 'retrieved_docs' 支持。
    - 如果没有 'retrieved_docs' (非 RAG)，则跳过检查。
    - 使用强类型数据契约。
    
    [WARN] 注意：这是异步节点，必须在 async/await 上下文中调用。
    """
    if ENABLE_VERBOSE_LOGGING:
        print("\n" + "[Search]" * 40)
        print("【Grounding Check 节点】(强类型版本)")
        retrieved = state.get('retrieved_docs', [])
        print(f"  - Answer (to check): {str(state.get('answer'))[:100]}...")
        print(f"  - Retrieved Docs: {len(retrieved)} 个")
        print(f"  - Enable Grounding: {state.get('enable_grounding', ENABLE_GROUNDING_CHECK)}")
        print("[Search]" * 40 + "\n")

    # 检查是否禁用了 grounding
    if not state.get("enable_grounding", ENABLE_GROUNDING_CHECK):
        if ENABLE_VERBOSE_LOGGING:
            print("⏭  GROUNDING CHECK: Disabled by config")
        return {"is_grounded": True}

    # 1. 获取要检查的文本和上下文 (使用强类型)
    answer_to_check = state.get("answer")
    retrieved_docs: List[RetrievedDocument] = state.get("retrieved_docs", [])

    # 2. 如果没有 RAG 结果，无法进行 grounding，跳过。
    if not retrieved_docs:
        if ENABLE_VERBOSE_LOGGING:
            print("⏭  GROUNDING CHECK: No retrieved docs, skipping (is_grounded=True)")
        return {"is_grounded": True}

    # 3. 如果有 RAG 结果，但没有有效答案，也跳过。
    if not answer_to_check or not isinstance(answer_to_check, str):
        if ENABLE_VERBOSE_LOGGING:
            print("[WARN]  GROUNDING CHECK: No valid answer string, skipping (is_grounded=True)")
        return {"is_grounded": True}
    
    # 4. 规范化文本作为缓存 key
    cache_key = answer_to_check.strip()

    # 5. 如果是模板内容，直接认为 grounded
    if answer_to_check in RESPONSE_TEMPLATES.values():
        if ENABLE_VERBOSE_LOGGING:
            print("⏭  GROUNDING CHECK: Answer matches template, considered grounded")
        _GROUNDING_CACHE[cache_key] = True
        return {"is_grounded": True}

    # 6. 检查缓存
    if not force_check and cache_key in _GROUNDING_CACHE:
        if ENABLE_VERBOSE_LOGGING:
            print(f"[Timer]  GROUNDING CHECK: Result from cache: {_GROUNDING_CACHE[cache_key]}")
        return {"is_grounded": _GROUNDING_CACHE[cache_key]}

    # 7. 准备 Prompt (使用强类型文档)
    sse_events: List[SSEEvent] = []
    try:
        prompts = load_prompts()
        template = prompts.get("GROUNDING_PROMPT")
        if not template:
            raise ValueError("GROUNDING_PROMPT not found in prompts config.")
        
        # 使用 build_context_string，它应该能处理 List[RetrievedDocument]
        context_str = build_context_string(retrieved_docs)
        
        prompt = template.format(context_str=context_str, answer=answer_to_check)

    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"[ERR] GROUNDING CHECK: Failed to build prompt: {e}")
            traceback.print_exc()
        # 无法构建 prompt，安全起见，跳过
        return {"is_grounded": True}

    # 8. [OK] 调用异步 grounding 模型进行验证
    start_event: SSEEvent = {
        "event": "status",
        "data": { "message": "正在进行答案事实性核查...", "node": "grounding_check" }
    }
    sse_events.append(start_event)
    
    try:
        verification = await call_qwen_httpx(  # [OK] await call_qwen_httpx
            [{"role": "user", "content": prompt}],
            model=GROUNDING_MODEL,
            temperature=0.0,
            purpose="grounding",
            stream=False,
        )
        text = (verification.get("content", "") if isinstance(verification, dict) else str(verification)).lower()
        
        # 检查 'yes' 或 'true'
        is_grounded = "yes" in text or "true" in text
        _GROUNDING_CACHE[cache_key] = is_grounded

        if ENABLE_VERBOSE_LOGGING:
            print(f"[OK] GROUNDING CHECK: Model returned '{text}'. Result: {is_grounded}")

        # 创建完成事件
        complete_event: SSEEvent = {
            "event": "status",
            "data": { "message": f"事实性核查完成: {'通过' if is_grounded else '未通过'}", "node": "grounding_check" }
        }
        sse_events.append(complete_event)
        
        return {"is_grounded": is_grounded, "sse_events": sse_events}
    
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"[ERR] GROUNDING CHECK: Model call failed: {e}")
            traceback.print_exc()
        
        # 模型调用失败，安全起见，默认为 grounded
        _GROUNDING_CACHE[cache_key] = True
        
        error_event: SSEEvent = {
            "event": "error",
            "data": { "message": "事实性核查失败，跳过检查。", "node": "grounding_check" }
        }
        sse_events.append(error_event)
        
        return {"is_grounded": True, "sse_events": sse_events}