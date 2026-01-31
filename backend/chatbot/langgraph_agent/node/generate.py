# backend/chatbot/langgraph_agent/node/generate.py

import json
import re
import time
import asyncio  # [OK] 新增
from typing import Dict, Any, Optional, List, Tuple
from langchain_core.messages import BaseMessage, AIMessage

# 导入强类型定义
from ..schemas import (
    RetrievedDocument,
    Citation,
    Source,
    SSEEvent,
    StudentInfo,
    Memory,
    FinalOutput
)
from ..state import ChatState

# 导入核心功能
from ..core import (
    QWEN_MODEL,
    ENABLE_VERBOSE_LOGGING,
    call_qwen,  # [OK] 保留（给其他同步代码用）
    call_qwen_httpx,  # [OK] 新增异步版本
    _messages_to_dicts,
    emit_stream_token,
    extract_course_codes,
)
from .prompt_loader import load_prompts

# =================================================================
# 辅助函数（保持不变）
# =================================================================

def _build_context_with_citations(docs: List[RetrievedDocument], budget_chars: int = 1800) -> Tuple[str, Dict[str, Dict[str, str]]]:
    parts, source_map, used = [], {}, 0
    for i, doc in enumerate(docs, 1):
        source_id = doc.get("source_id", f"SOURCE_{i}")
        title = doc.get("title", f"来源 {i}")
        url = doc.get("source_url", "")
        snippet = (doc.get("snippet") or doc.get("_text", ""))[:400]
        chunk = f"[{source_id}] {title}\nURL: {url}\n内容: {snippet}\n"
        if used + len(chunk) > budget_chars:
            break
        parts.append(chunk)
        used += len(chunk)
        source_map[source_id] = {"title": title, "url": url}
    return ("\n---\n".join(parts) or "无检索到的相关信息。"), source_map


def _extract_citations_from_answer(
    answer: str, 
    source_map: Dict[str, Dict[str, str]]
) -> Dict[str, Any]:
    """从 LLM 回答中提取引用。"""
    pattern = r'\[([^\]]+)\]'
    matches = re.findall(pattern, answer)
    
    cited_ids = []
    for m in matches:
        if m in source_map:
            cited_ids.append(m)
        elif m.isdigit() and f"SOURCE_{m}" in source_map:
            cited_ids.append(f"SOURCE_{m}")
        
    cited_source_ids = sorted(list(set(cited_ids)))
    
    citations: List[Citation] = []
    for source_id in cited_source_ids:
        if source_id in source_map:
            try:
                index_match = re.search(r'\d+', source_id)
                index = int(index_match.group()) if index_match else (len(citations) + 1)
            except (AttributeError, ValueError):
                index = len(citations) + 1

            citations.append({
                "id": source_id,
                "index": index,
                "title": source_map[source_id]["title"],
                "url": source_map[source_id]["url"],
            })
    
    if ENABLE_VERBOSE_LOGGING and citations:
        print(f"[Cite] [Generate] 检测到 {len(citations)} 个引用: {[c['id'] for c in citations]}")
    
    return {"cited_source_ids": cited_source_ids, "citations": citations}


def _retrieved_docs_to_sources(docs: List[RetrievedDocument]) -> List[Source]:
    """将 RetrievedDocument 转换为前端需要的 Source 格式。"""
    sources: List[Source] = []
    for doc in docs:
        if doc.get("metadata", {}).get("source_type") == "tool_result":
            continue
            
        source: Source = {"title": doc["title"], "url": doc["source_url"]}
        snippet = doc.get("snippet") or doc.get("_text", "")[:150]
        if snippet: source["snippet"] = snippet
        if "score" in doc: source["relevance_score"] = doc["score"]
        sources.append(source)
    return sources


# =================================================================
# 节点主函数 [OK] 改为异步
# =================================================================

async def node_generate(state: ChatState) -> Dict[str, Any]:  # [OK] async def
    """
    [节点] 生成答案
    - 核心职责：调用 LLM 生成自然语言回复。
    - 支持处理由守卫节点直接提供的预设答案 (answer)。
    - 在答案结尾追加 CTA，并设置 pending_file_generation。
    """
    try:
        messages: List[BaseMessage] = state.get("messages", [])
        route = state.get("route")
        run_id = state.get("run_id")
        session_id = str(run_id) if run_id is not None else ""

        context_docs: List[RetrievedDocument] = state.get("retrieved_docs", [])
        student_info: StudentInfo = state.get("student_info", {})
        memory: Memory = state.get("memory", {})
        source_map: Dict[str, Dict[str, str]] = {}

        if ENABLE_VERBOSE_LOGGING:
            print("\n" + "" * 40)
            print("【Generate 节点】启动 (LLM 生成模式)")
            print(f"   - Route: {route}")
            print(f"   - SessionId: {session_id}")
            print(f"   - Retrieved Docs: {len(context_docs)} 个")
            print("" * 40 + "\n")

        # --- 1. 处理预设答案 (来自守卫节点) ---
        prefilled_answer = state.get("answer")
        if isinstance(prefilled_answer, str) and prefilled_answer.strip():
            if ENABLE_VERBOSE_LOGGING: 
                print("   -> 接收到预设答案，直接流式输出。")

            # [OK] 异步流式输出（保持原逻辑）
            for char in prefilled_answer:
                emit_stream_token(session_id, char)
                await asyncio.sleep(0.01)  # [OK] 异步 sleep
            return {"answer": prefilled_answer}

        # --- 2. 准备 Prompt ---
        prompts = load_prompts()
        system_prompt = ""

        if context_docs:
            context_str, source_map = _build_context_with_citations(context_docs)
            system_prompt_template = prompts.get("RETRIEVED_PROMPT") or """
    你是 UNSW 课程顾问助手。请根据以下【检索到的信息】和【学生信息】来回答用户的问题。
    - 当你的回答内容基于【检索到的信息】时，必须在相应的句子末尾加上引用标记，例如 [SOURCE_1] 或 [tool_...]
    - 引用标记必须与【检索到的信息】中的ID完全对应。
    - 如果信息不足，请明确说明。

    【检索到的信息】
    {context_str}

    【学生信息】
    {student_info}
    """
            info_parts = []
            if student_info.get("major_code"): 
                info_parts.append(f"专业: {student_info['major_code']}")
            if student_info.get("year"): 
                info_parts.append(f"年级: {student_info['year']}")
            if student_info.get("completed_courses"): 
                info_parts.append(f"已修课程: {', '.join(student_info['completed_courses'][:5])}")
            student_info_str = "\n".join(info_parts) or "(未提供)"

            system_prompt = system_prompt_template.format(
                context_str=context_str,
                student_info=student_info_str
            )
        else:
            system_prompt = prompts.get("GENERAL_CHAT_PROMPT", "你是一个乐于助人的课程顾问助手。")
            if memory.get("long_term_summary"):
                system_prompt = f"{system_prompt}\n\n## 用户背景\n{memory['long_term_summary']}"

        # --- 3. 准备消息历史 ---
        filtered_messages = []
        for m in _messages_to_dicts(messages):
            if m.get("role") in ("system", "tool"): continue
            if m.get("role") == "assistant" and m.get("tool_calls"): continue
            if m.get("content") is None: continue
            filtered_messages.append(m)

        # --- 4. [OK] 调用异步 LLM 并流式输出 ---
        stream_gen = await call_qwen_httpx(  # [OK] await
            filtered_messages,
            system_prompt=system_prompt,
            temperature=0.7,
            purpose="generation",
            stream=True,
            model=QWEN_MODEL
        )

        final_answer = ""
        sse_events: List[SSEEvent] = []

        if context_docs:
            sse_events.append({
                "event": "status", 
                "data": {"message": "正在生成答案...", "node": "generate"}
            })

        try:
            async for chunk in stream_gen:  # [OK] async for
                if not chunk: 
                    continue
                try:
                    chunk_data = json.loads(chunk)
                    content = (
                        chunk_data.get("choices", [{}])[0] or {}
                    ).get("delta", {}).get("content", "")

                    if content:
                        final_answer += content
                        if session_id: 
                            emit_stream_token(session_id, content)

                except (json.JSONDecodeError, IndexError):
                    continue

        except Exception as e:
            if ENABLE_VERBOSE_LOGGING:
                print(f"[Generate] 流读取异常: {e}")

        # --- 5. 后处理 ---
        if not final_answer.strip():
            final_answer = "你好！我是UNSW课程助手，有什么可以帮你的吗？"
            if session_id: 
                emit_stream_token(session_id, final_answer)

        # 提取引用
        citation_result = _extract_citations_from_answer(final_answer, source_map)
        citations: List[Citation] = citation_result["citations"]
        for citation in citations:
            sse_events.append({"event": "citation", "data": citation})

        # --- 5.1 在答案末尾追加 CTA，并设置 pending_file_generation ---
        file_generation_declined = bool(state.get("file_generation_declined", False))
        has_pending = bool(state.get("pending_file_generation"))
        updates: Dict[str, Any] = {}

        if (not file_generation_declined) and (not has_pending):
            proposed_codes = extract_course_codes(final_answer) or extract_course_codes(
                (messages[-1].content if messages and hasattr(messages[-1], "content") else "")
            ) or extract_course_codes(state.get("query", ""))

            completed = set((state.get("student_info") or {}).get("completed_courses") or [])
            proposed_codes = [c for c in proposed_codes if c not in completed]

            if proposed_codes and not state.get("pending_file_generation"):
                cta_text = (
                    "\n\n——\n需要我为上述课程直接生成选课文件吗？"
                    "回复\"确认\"即可开始生成；如无需生成，也可以继续让我完善方案或调整课程。"
                )
                final_answer += cta_text
                if session_id:
                    for ch in cta_text:
                        emit_stream_token(session_id, ch)
                        await asyncio.sleep(0.01)  # [OK] 异步 sleep
                updates["pending_file_generation"] = {"courses": proposed_codes}

        # --- 6. 构建最终返回 ---
        sources: List[Source] = _retrieved_docs_to_sources(context_docs)
        final_output: FinalOutput = {
            "answer": final_answer,
            "sources": sources,
            "is_grounded": bool(context_docs),
            "citations": citations
        }

        if ENABLE_VERBOSE_LOGGING:
            print(f"[Generate] [OK] 完成. 答案长度: {len(final_answer)}")

        return {
            "answer": final_answer,
            "sources": sources,
            "citations": citations,
            "final_output": final_output,
            "sse_events": sse_events,
            **updates,
        }
    except Exception as e:
        # 兜底：记录日志 + 返回友好错误
        msg = "抱歉，我暂时遇到了一点问题，请稍后再试。"
        sse_events = [{"event": "error", "data": {"message": str(e), "node": "generate"}}]
        # 同时给 answer 填充兜底文本，确保用户能收到回复
        return {
            "error": msg,
            "answer": msg,
            "sse_events": sse_events,
            # 可选：标记为非检索回答
            "is_grounded": False,
            "sources": [],
            "citations": [],
        }