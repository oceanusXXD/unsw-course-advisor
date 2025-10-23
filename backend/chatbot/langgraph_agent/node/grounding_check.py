# ./node/grounding_check.py
import traceback
import json
from typing import Dict, Any, List
from core import ENABLE_GROUNDING_CHECK, ENABLE_VERBOSE_LOGGING, call_qwen_sync, GROUNDING_MODEL, RESPONSE_TEMPLATES
# 导入加载器
from .prompt_loader import load_prompts

# 缓存 (cache_key) -> grounding 结果
_GROUNDING_CACHE: Dict[str, bool] = {}

def _format_context(retrieved: List[Dict[str, Any]]) -> str:
    """将检索到的文档列表格式化为字符串上下文。"""
    if not retrieved:
        return "无上下文。"
    
    context_parts = []
    for i, doc in enumerate(retrieved):
        # 使用 _text 字段 (在 node_retrieve 中标准化的)
        text = doc.get("_text") or doc.get("content") or ""
        source = doc.get("source_file", f"来源 {i+1}")
        context_parts.append(f"--- 来源 {i+1} ({source}) ---\n{text}\n")
    
    return "\n".join(context_parts)

def node_grounding_check(state: Dict[str, Any], force_check: bool = False) -> Dict[str, Any]:
    """
    Grounding 检查:
    - 检查 "answer" 是否被 "retrieved" 支持。
    - 如果没有 "retrieved" 文档 (非 RAG)，则跳过检查 (默认为 True)。
    """
    print("!!!!!!!!!!!!!!state in grounding_check:")

    if not state.get("enable_grounding", ENABLE_GROUNDING_CHECK):
        if ENABLE_VERBOSE_LOGGING:
            print("⏭️  GROUNDING CHECK: Disabled by config")
        return {"is_grounded": True}

    # 1. 获取要检查的文本
    answer_to_check = state.get("answer")
    
    # 2. 获取上下文 (RAG 结果)
    retrieved_docs = state.get("retrieved")

    # 3. 如果没有 RAG 结果，无法进行 grounding，跳过。
    if not retrieved_docs:
        if ENABLE_VERBOSE_LOGGING:
            print("⏭️  GROUNDING CHECK: No retrieved docs, skipping (is_grounded=True)")
        return {"is_grounded": True}

    # 4. 如果有 RAG 结果，但没有答案 (或答案不是字符串)，也跳过
    if not answer_to_check or not isinstance(answer_to_check, str):
        if ENABLE_VERBOSE_LOGGING:
            print("⚠️  GROUNDING CHECK: No valid answer string found to check, skipping (is_grounded=True)")
        return {"is_grounded": True}
    
    # 5. 规范化文本作为缓存 key
    cache_key = answer_to_check.strip()

    # 6. 如果是模板内容 (如 "未找到文档")，直接认为 grounded
    if answer_to_check in RESPONSE_TEMPLATES.values():
        if ENABLE_VERBOSE_LOGGING:
            print("⏭️  GROUNDING CHECK: Answer matches template, considered grounded")
        _GROUNDING_CACHE[cache_key] = True
        return {"is_grounded": True}

    # 7. 检查缓存
    if not force_check and cache_key in _GROUNDING_CACHE:
        if ENABLE_VERBOSE_LOGGING:
            print(f"⏱️  GROUNDING CHECK: Result from cache: {_GROUNDING_CACHE[cache_key]}")
        return {"is_grounded": _GROUNDING_CACHE[cache_key]}

    # 8. 准备 Prompt
    try:
        # 加载模板
        prompts = load_prompts()
        template = prompts.get("GROUNDING_PROMPT_TEMPLATE")
        if not template:
            raise ValueError("GROUNDING_PROMPT_TEMPLATE not found in prompts config.")
        
        # 格式化上下文
        context_str = _format_context(retrieved_docs)
        
        # 格式化完整 prompt
        prompt = template.format(
            context=context_str,
            answer=answer_to_check
        )

    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"❌ GROUNDING CHECK: Failed to build prompt: {e}")
            traceback.print_exc()
        # 无法构建 prompt，安全起见，跳过
        return {"is_grounded": True}

    # 9. 调用 grounding 模型进行验证
    try:
        verification = call_qwen_sync(
            [{"role": "user", "content": prompt}],
            model=GROUNDING_MODEL,
            temperature=0.0,
            purpose="grounding"
        )
        
        # 严格检查 'yes'
        is_grounded = "yes" in verification.lower().strip()
        _GROUNDING_CACHE[cache_key] = is_grounded

        if ENABLE_VERBOSE_LOGGING:
            print(f"✓ GROUNDING CHECK: Model returned '{verification}'. Result: {is_grounded}")
        return {"is_grounded": is_grounded}
    
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"❌ GROUNDING CHECK: Model call failed: {e}")
            traceback.print_exc()
        # 模型调用失败，安全起见，默认为 grounded
        _GROUNDING_CACHE[cache_key] = True
        return {"is_grounded": True}