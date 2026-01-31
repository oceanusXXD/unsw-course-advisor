# backend/chatbot/langgraph_agent/node/evaluate_retrieval.py

import json
import re
from typing import Dict, Any, List, Optional

# 导入强类型定义
from ..schemas import (
    RetrievedDocument,
    RetrievalEvaluation,
    SSEEvent,
)
from ..state import ChatState

from ..core import (
    ENABLE_VERBOSE_LOGGING,
    call_qwen,  # [OK] 保留（向后兼容）
    call_qwen_httpx,  # [OK] 新增异步版本
    ROUTER_MODEL,
)
from .prompt_loader import load_prompts


def _validate_and_get_doc_text(doc: RetrievedDocument) -> str:
    """
    从强类型 RetrievedDocument 中安全提取文本
    """
    # 使用强类型的必需字段 _text
    if "_text" in doc:
        return doc["_text"]
    
    # 降级到其他可能的字段（向后兼容）
    text = doc.get("content", "") or doc.get("text", "") or doc.get("page_content", "")
    
    if ENABLE_VERBOSE_LOGGING and not text:
        print(f"[WARN] [Evaluate] 文档缺少文本内容: source_id={doc.get('source_id', 'unknown')}")
    
    return text


def _validate_retrieved_docs(docs: List[Any]) -> List[RetrievedDocument]:
    """
    验证和规范化文档列表，确保符合 RetrievedDocument 类型
    """
    validated_docs: List[RetrievedDocument] = []
    
    for i, doc in enumerate(docs):
        if not isinstance(doc, dict):
            if ENABLE_VERBOSE_LOGGING:
                print(f"[WARN] [Evaluate] 跳过非字典类型文档: {type(doc)}")
            continue
        
        # 检查必需字段
        if "_text" not in doc:
            # 尝试从其他字段获取文本
            text = doc.get("content", "") or doc.get("text", "") or doc.get("page_content", "")
            doc["_text"] = text
        
        if "source_id" not in doc:
            doc["source_id"] = f"SOURCE_{i + 1}"
        
        if "title" not in doc:
            doc["title"] = doc.get("source_file", "") or f"文档 {i + 1}"
        
        if "source_url" not in doc:
            doc["source_url"] = doc.get("url", "") or ""
        
        validated_docs.append(doc)
    
    return validated_docs


def _calculate_retrieval_quality(
    docs: List[RetrievedDocument], 
    query: str
) -> float:
    """
    计算检索质量得分 (0-1)
    使用强类型 RetrievedDocument
    """
    if not docs:
        return 0.0

    num_docs = len(docs)
    # 使用强类型字段 _text
    doc_texts = [_validate_and_get_doc_text(d).lower() for d in docs]
    
    # 1. 提取查询关键词
    query_keywords = set()
    course_codes = re.findall(r'\b[A-Za-z]{4}\d{4}\b', query)
    
    if course_codes:
        query_keywords = {c.upper() for c in course_codes}
        if ENABLE_VERBOSE_LOGGING:
            print(f"  [Search] 提取课程代码: {query_keywords}")
    else:
        query_lower = query.lower()
        stopwords = {
            "is", "a", "the", "what", "how", "why", "who", "for", "of", "to", 
            "in", "on", "and", "or", "my", "me", "you", "it", "unsw", 
            "介绍", "一下", "请", "帮", "我"
        }
        words = re.findall(r'\b[a-z]{3,}\b', query_lower)
        query_keywords = {w for w in words if w not in stopwords}
        if ENABLE_VERBOSE_LOGGING:
            print(f"  [Search] 提取通用关键词: {query_keywords}")

    # 如果查询没有有效关键词，给一个中立分数
    if not query_keywords:
        if ENABLE_VERBOSE_LOGGING:
            print(f"  [WARN] 无有效关键词，query='{query}'，返回中立分 0.5")
        return 0.5 

    # 2. 计算相关性得分
    matched_docs_count = 0
    total_matched_length = 0
    matched_doc_ids = []
    
    for i, (doc, text) in enumerate(zip(docs, doc_texts)):
        text_upper = text.upper()
        matched = False
        
        if course_codes:
            if any(kw in text_upper for kw in query_keywords):
                matched = True
        else:
            if any(kw in text for kw in query_keywords):
                matched = True
        
        if matched:
            matched_docs_count += 1
            total_matched_length += len(text)
            matched_doc_ids.append(doc["source_id"])

    # 如果完全没有匹配到，分数必须是 0
    if matched_docs_count == 0:
        if ENABLE_VERBOSE_LOGGING:
            print(f"  [ERR] 没有匹配的文档（关键词: {query_keywords}）")
        return 0.0

    # 3. 归一化得分
    relevance_ratio = matched_docs_count / num_docs
    length_score = min(total_matched_length / 1500.0, 1.0)

    # 4. 最终分数 (70% 相关性, 30% 长度)
    final_score = (relevance_ratio * 0.7) + (length_score * 0.3)
    
    if ENABLE_VERBOSE_LOGGING:
        print(f"  [Stats] 匹配文档: {matched_docs_count}/{num_docs} ({relevance_ratio:.1%})")
        print(f"  [Stats] 匹配的文档ID: {matched_doc_ids[:3]}...")
        print(f"  [Stats] 总长度: {total_matched_length} chars (score: {length_score:.2f})")
        print(f"  [Stats] 最终分数: {final_score:.2f}")
    
    return min(final_score, 1.0)


def _create_evaluation_result(
    sufficient: bool,
    quality_score: float,
    docs: List[RetrievedDocument],
    missing_aspects: Optional[List[str]] = None,
    suggestions: Optional[List[str]] = None
) -> RetrievalEvaluation:
    """
    创建强类型的评估结果
    """
    evaluation: RetrievalEvaluation = {
        "sufficient": sufficient,
        "quality_score": quality_score,
    }
    
    if missing_aspects:
        evaluation["missing_aspects"] = missing_aspects
    
    if suggestions:
        evaluation["suggestions"] = suggestions
    
    return evaluation


async def node_evaluate_retrieval(state: ChatState) -> Dict[str, Any]:  # [OK] async def
    """
    评估检索结果是否充足（使用强类型数据契约）
    
    消费：
    - retrieved_docs: List[RetrievedDocument]
    - query: str
    - retrieval_round: int
    
    生产：
    - sufficient: bool
    - quality_score: float
    - retrieved_docs: List[RetrievedDocument] (规范化后的)
    - sse_events: List[SSEEvent]
    
    [WARN] 注意：这是异步节点，必须在 async/await 上下文中调用。
    """
    query = state.get("query", "") or ""
    raw_docs = state.get("retrieved_docs", []) or []
    retrieval_round = int(state.get("retrieval_round", 0) or 0)

    # 验证和规范化文档
    retrieved_docs: List[RetrievedDocument] = _validate_retrieved_docs(raw_docs)

    # 创建开始评估的 SSE 事件
    start_event: SSEEvent = {
        "event": "status",
        "data": {
            "message": f"正在评估检索结果质量（轮次 {retrieval_round}）...",
            "node": "evaluate_retrieval",
            "progress": 0.6
        }
    }
    sse_events: List[SSEEvent] = [start_event]

    # 计算质量分数
    quality_score = _calculate_retrieval_quality(retrieved_docs, query)

    if ENABLE_VERBOSE_LOGGING:
        print(f"\n{'='*60}")
        print(f"[Evaluate Retrieval] 使用强类型契约")
        print(f"  Round: {retrieval_round}")
        print(f"  Query: '{query[:50]}...'")
        print(f"  Retrieved Docs: {len(retrieved_docs)} (验证后)")
        print(f"  Quality Score: {quality_score:.2f}")

    # 构建缺失方面和建议（用于评估结果）
    missing_aspects = []
    suggestions = []

    # 情况1：没有文档
    if not retrieved_docs:
        if ENABLE_VERBOSE_LOGGING:
            print("  Result: [ERR] Insufficient (no docs)")
            print(f"{'='*60}\n")
        
        missing_aspects = ["没有检索到任何文档"]
        suggestions = ["尝试使用更具体的关键词", "检查查询中的课程代码是否正确"]
        
        evaluation = _create_evaluation_result(
            sufficient=False,
            quality_score=0.0,
            docs=[],
            missing_aspects=missing_aspects,
            suggestions=suggestions
        )
        
        no_docs_event: SSEEvent = {
            "event": "status",
            "data": {
                "message": "未检索到文档，需要继续检索",
                "node": "evaluate_retrieval"
            }
        }
        sse_events.append(no_docs_event)
        
        return {
            "sufficient": False,
            "retrieved_docs": [],
            "quality_score": 0.0,
            "sse_events": sse_events
        }

    # 情况2：低分
    if quality_score < 0.3:
        if ENABLE_VERBOSE_LOGGING:
            print("  Result: [ERR] Insufficient (score < 0.3)")
            print(f"{'='*60}\n")
        
        missing_aspects = ["文档相关性低", "缺少关键信息"]
        suggestions = ["需要更精确的检索", "可能需要调整查询策略"]
        
        evaluation = _create_evaluation_result(
            sufficient=False,
            quality_score=quality_score,
            docs=retrieved_docs[:8],
            missing_aspects=missing_aspects,
            suggestions=suggestions
        )
        
        low_score_event: SSEEvent = {
            "event": "status",
            "data": {
                "message": f"检索质量不足（分数: {quality_score:.2f}），需要继续检索",
                "node": "evaluate_retrieval"
            }
        }
        sse_events.append(low_score_event)
        
        return {
            "sufficient": False,
            "retrieved_docs": retrieved_docs[:8],
            "quality_score": quality_score,
            "sse_events": sse_events
        }

    # 情况3：高分
    if quality_score >= 0.7:
        if ENABLE_VERBOSE_LOGGING:
            print("  Result: [OK] Sufficient (score >= 0.7)")
            print(f"{'='*60}\n")
        
        evaluation = _create_evaluation_result(
            sufficient=True,
            quality_score=quality_score,
            docs=retrieved_docs[:8]
        )
        
        high_score_event: SSEEvent = {
            "event": "status",
            "data": {
                "message": f"检索质量充足（分数: {quality_score:.2f}），可以生成答案",
                "node": "evaluate_retrieval"
            }
        }
        sse_events.append(high_score_event)
        
        return {
            "sufficient": True,
            "retrieved_docs": retrieved_docs[:8],
            "quality_score": quality_score,
            "sse_events": sse_events
        }

    # 情况4：中分，使用 Function Calling 决策
    if ENABLE_VERBOSE_LOGGING:
        print(f"  [LLM] 中分 ({quality_score:.2f})，调用 LLM 评估...")

    tools_schema = [
        {
            "type": "function",
            "function": {
                "name": "continue_retrieve",
                "description": "当当前检索内容不足以回答用户问题时调用，继续检索。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reasoning": {"type": "string", "description": "为什么需要继续检索？"}
                    },
                    "required": ["reasoning"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "finish_retrieval",
                "description": "当当前检索内容已经可以支持生成高质量回答时调用，结束检索。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reasoning": {"type": "string", "description": "为什么可以结束检索？"}
                    },
                    "required": ["reasoning"]
                }
            }
        }
    ]

    # 准备上下文（使用强类型字段）
    prompts = load_prompts()
    context_str = ""
    for i, doc in enumerate(retrieved_docs[:5]):
        content = doc["_text"][:400]  # 使用强类型必需字段
        title = doc["title"]
        context_str += f"[文档 {i+1}] {title}\n{content}\n\n"

    try:
        eval_prompt_template = prompts.get("EVALUATE_RETRIEVAL_PROMPT") or \
            "用户问题: {query}\n\n检索内容:\n{context_str}\n\n请仅在 continue_retrieve 或 finish_retrieval 中选择一个，并说明 reasoning。"
        prompt = eval_prompt_template.format(query=query, context_str=context_str)
    except Exception:
        prompt = f"用户问题: {query}\n\n检索内容:\n{context_str}\n\n请仅在 continue_retrieve 或 finish_retrieval 中选择一个，并说明 reasoning。"

    # 添加 LLM 评估事件
    llm_eval_event: SSEEvent = {
        "event": "status",
        "data": {
            "message": "调用 AI 进行深度评估...",
            "node": "evaluate_retrieval"
        }
    }
    sse_events.append(llm_eval_event)

    messages = [{"role": "user", "content": prompt}]

    try:
        resp = await call_qwen_httpx(  # [OK] await call_qwen_httpx
            messages,
            model=ROUTER_MODEL,
            temperature=0.2,
            stream=False,
            tools=tools_schema,
            tool_choice="auto",
            purpose="evaluate_retrieval_fc",
        )
        if ENABLE_VERBOSE_LOGGING:
            print("  LLM 返回(FC):", json.dumps(resp, ensure_ascii=False)[:400])
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"  [ERR] LLM 调用失败: {e}")
        
        # 兜底：中分按 0.5 阈值判定
        is_sufficient = quality_score >= 0.5
        
        error_event: SSEEvent = {
            "event": "status",
            "data": {
                "message": f"AI 评估失败，使用规则判定：{'充足' if is_sufficient else '不足'}",
                "node": "evaluate_retrieval"
            }
        }
        sse_events.append(error_event)
        
        if ENABLE_VERBOSE_LOGGING:
            print(f"  Result: {'[OK] Sufficient' if is_sufficient else '[ERR] Insufficient'} (fallback)")
            print(f"{'='*60}\n")
        
        evaluation = _create_evaluation_result(
            sufficient=is_sufficient,
            quality_score=quality_score,
            docs=retrieved_docs[:8],
            missing_aspects=["LLM 评估失败"] if not is_sufficient else None,
            suggestions=["使用规则判定结果"] if not is_sufficient else None
        )
        
        return {
            "sufficient": is_sufficient,
            "retrieved_docs": retrieved_docs[:8],
            "quality_score": quality_score,
            "sse_events": sse_events
        }

    # 解析工具调用
    is_sufficient = False
    reasoning = ""
    
    if isinstance(resp, dict) and resp.get("tool_calls"):
        tool_call = resp["tool_calls"][0]
        fn_info = tool_call.get("function") or {}
        fn_name = fn_info.get("name")
        args = json.loads(fn_info.get("arguments", "{}"))
        reasoning = args.get("reasoning", "")
        
        if ENABLE_VERBOSE_LOGGING:
            print(f"  决策函数: {fn_name}")
            print(f"  推理: {reasoning[:100]}...")
        
        if fn_name == "finish_retrieval":
            is_sufficient = True
        elif fn_name == "continue_retrieve":
            is_sufficient = False
            missing_aspects = ["AI 判断需要更多信息"]
            suggestions = [reasoning] if reasoning else ["继续检索获取更多相关文档"]
    else:
        # 没有 tool_calls：兜底按 0.5 阈值
        is_sufficient = quality_score >= 0.5
        if ENABLE_VERBOSE_LOGGING:
            print("  [WARN] 无 tool_calls，按分数阈值兜底")

    # 创建最终评估结果
    evaluation = _create_evaluation_result(
        sufficient=is_sufficient,
        quality_score=quality_score,
        docs=retrieved_docs[:8],
        missing_aspects=missing_aspects if not is_sufficient else None,
        suggestions=suggestions if not is_sufficient else None
    )
    
    # 添加决策事件
    decision_event: SSEEvent = {
        "event": "status",
        "data": {
            "message": f"评估完成：检索{'充足' if is_sufficient else '不足'}（质量分数: {quality_score:.2f}）",
            "node": "evaluate_retrieval",
            "evaluation": {
                "sufficient": is_sufficient,
                "score": quality_score,
                "reasoning": reasoning[:200] if reasoning else None
            }
        }
    }
    sse_events.append(decision_event)

    if ENABLE_VERBOSE_LOGGING:
        result_emoji = "[OK]" if is_sufficient else "[ERR]"
        print(f"  Result: {result_emoji} {'Sufficient' if is_sufficient else 'Insufficient'}")
        print(f"{'='*60}\n")

    return {
        "sufficient": is_sufficient,
        "retrieved_docs": retrieved_docs[:8],
        "quality_score": quality_score,
        "sse_events": sse_events
    }