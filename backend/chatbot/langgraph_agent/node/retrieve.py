# backend/chatbot/langgraph_agent/node/retrieve.py

import traceback
from typing import Dict, Any, List, Optional
from ..core import TOP_K, ENABLE_VERBOSE_LOGGING, RESPONSE_TEMPLATES

# 导入强类型定义
from ..schemas import (
    RetrievedDocument,
    Source,
    SSEEvent,
    StatusEvent
)
from ..state import ChatState

try:
    from ..parallel_search_and_rerank import parallel_search_and_rerank
    
    HYBRID_SEARCH_INITIALIZED = True
    if ENABLE_VERBOSE_LOGGING:
        print("[OK] (Retrieve Node) 成功导入 'parallel_search_and_rerank' 服务")
except ImportError as e:
    HYBRID_SEARCH_INITIALIZED = False
    print(f"[WARN] (Retrieve Node) 导入 'parallel_search_and_rerank' 失败: {e}")
    
    def parallel_search_and_rerank(query: str, top_k: int) -> List:
        return []


def _doc_to_source(d: dict, idx: int) -> Source:
    """
    辅助函数：将检索到的文档（doc）转换为强类型的 Source 对象。
    
    这个函数现在返回符合 Source TypedDict 的字典。
    """
    
    # 1. 获取 metadata
    meta = d.get("_metadata") or d.get("metadata") or {}
    
    # 2. 提取核心字段
    source_url = meta.get("url") or meta.get("source_url") or ""
    title = meta.get("title") or f"来源 {idx}"
    
    # 3. 提取辅助字段
    score = d.get("_score") or meta.get("rerank_score") or 0.0
    
    # 4. 提取预览片段
    preview = (
        d.get("_text") or 
        meta.get("snippet") or 
        ""
    )
    if preview:
        preview = str(preview).strip()[:240]
    
    # 5. 返回强类型的 Source 对象
    source: Source = {
        "title": title,
        "url": source_url,
    }
    
    # 添加可选字段
    if preview:
        source["snippet"] = preview
    if score:
        source["relevance_score"] = float(score)
    
    return source


def _doc_to_retrieved_document(doc: dict, idx: int) -> RetrievedDocument:
    """
    辅助函数：将原始文档转换为强类型的 RetrievedDocument 对象。
    """
    doc_metadata = doc.get("_metadata") or doc.get("metadata") or {}
    
    # 构建必需字段
    retrieved_doc: RetrievedDocument = {
        "source_id": f"SOURCE_{idx}",
        "title": doc_metadata.get("title") or f"文档 {idx}",
        "source_url": doc_metadata.get("url") or doc_metadata.get("source_url") or "",
        "_text": doc.get("_text") or "",
    }
    
    # 添加可选字段
    if doc.get("_id"):
        retrieved_doc["source_id"] = doc["_id"]
    
    snippet = doc_metadata.get("snippet")
    if snippet:
        retrieved_doc["snippet"] = snippet
    
    score = doc.get("_score") or doc_metadata.get("rerank_score")
    if score:
        retrieved_doc["score"] = float(score)
    
    # 保存完整的 metadata
    retrieved_doc["metadata"] = doc_metadata
    
    return retrieved_doc


def node_retrieve(state: ChatState) -> Dict[str, Any]:
    """
    [LangGraph 节点] - 检索
    
    这是 LangGraph 流程中的一个节点，负责执行混合检索和重排。
    现在使用强类型数据契约。
    """
    try:
        # 1. 从状态中获取当前查询和历史文档
        original_query = state.get("query", "")
        query_to_use = state.get("rewritten_query") or original_query
        old_docs: List[RetrievedDocument] = state.get("retrieved_docs", []) or []
        current_round = int(state.get("retrieval_round", 0) or 0)

        # 2. [安全检查] 
        if not HYBRID_SEARCH_INITIALIZED:
            if ENABLE_VERBOSE_LOGGING:
                print("[WARN]  RETRIEVE: 混合检索服务未初始化，跳过检索")
            
            # 构造状态事件
            status_event: SSEEvent = {
                "event": "error",
                "data": {
                    "message": "RAG 混合检索系统未初始化，无法执行检索。",
                    "node": "retrieve"
                }
            }
            
            return {
                "retrieved_docs": old_docs,
                "retrieval_round": current_round + 1,
                "sources": [],
                "sse_events": [status_event],
                "messages": [{
                    "role": "system",
                    "content": "RAG 混合检索系统未初始化，无法执行检索。"
                }]
            }

        # 3. 执行检索
        if ENABLE_VERBOSE_LOGGING:
            print("\n" + "="*30 + " Retrieve Node " + "="*30)
            if query_to_use != original_query:
                print(f"  [Rewritten] 使用重写后的查询: '{query_to_use}'")
            else:
                print(f"  [Original] 使用原始查询: '{query_to_use}'")
            print("="*80 + "\n")
        
        # 添加检索开始状态事件
        start_event: SSEEvent = {
            "event": "status",
            "data": {
                "message": f"正在检索相关文档...",
                "node": "retrieve",
                "progress": 0.3
            }
        }
        
        raw_docs = parallel_search_and_rerank(query_to_use , top_k=TOP_K) or []
        
        if ENABLE_VERBOSE_LOGGING:
            print(f"[Docs] RETRIEVE: 混合检索+重排后，找到 {len(raw_docs)} 个文档")
            if raw_docs:
                print(f"   示例文档 _metadata: {raw_docs[0].get('_metadata', {})}")

        # 4. 转换文档格式（使用强类型）
        normalized_docs: List[RetrievedDocument] = []
        sources: List[Source] = []
        
        for idx, doc in enumerate(raw_docs, start=len(old_docs) + 1):
            # 4a. 构建强类型 RetrievedDocument
            retrieved_doc = _doc_to_retrieved_document(doc, idx)
            normalized_docs.append(retrieved_doc)
            
            # 4b. 构建强类型 Source（给前端）
            source = _doc_to_source(doc, idx)
            sources.append(source)
        
        # 5. 验证文档结构完整性
        for doc in normalized_docs:
            # 验证必需字段存在
            assert "source_id" in doc, "RetrievedDocument missing source_id"
            assert "title" in doc, "RetrievedDocument missing title"
            assert "source_url" in doc, "RetrievedDocument missing source_url"
            assert "_text" in doc, "RetrievedDocument missing _text"

        # 6. 累积文档（保留历史）
        all_docs: List[RetrievedDocument] = old_docs + normalized_docs
        
        # 7. 构建 SSE 事件列表
        sse_events: List[SSEEvent] = [start_event]
        
        # 添加检索完成事件
        complete_event: SSEEvent = {
            "event": "status",
            "data": {
                "message": f"检索完成，找到 {len(normalized_docs)} 个相关文档",
                "node": "retrieve",
                "progress": 1.0
            }
        }
        sse_events.append(complete_event)
        
        # 如果找到文档，添加预览事件
        if normalized_docs:
            preview_event: SSEEvent = {
                "event": "data",
                "data": {
                    "type": "rag.preview",
                    "round": current_round + 1,
                    "count": len(normalized_docs),
                    "sources": sources  # 使用强类型 Source 列表
                }
            }
            sse_events.append(preview_event)
            
            # 添加每个来源的事件
            for source in sources[:3]:  # 只发送前3个
                source_event: SSEEvent = {
                    "event": "source",
                    "data": source  # 直接使用强类型 Source # type: ignore
                }
                sse_events.append(source_event)
        
        # 8. 准备返回结果
        result = {
            "retrieved_docs": all_docs,           # List[RetrievedDocument]
            "retrieval_round": current_round + 1, # int
            "sources": sources,                   # List[Source]
            "sse_events": sse_events,             # List[SSEEvent]
            "rewritten_query": None,
        }
        
        # 9. 如果未找到文档，添加系统消息
        if not normalized_docs:
            no_docs_msg = {
                "role": "system",
                "content": RESPONSE_TEMPLATES.get(
                    "fallback_no_rag_docs",
                    "未找到相关文档，将基于已有知识回答。"
                )
            }
            result["messages"] = [no_docs_msg]
            
            # 添加无文档事件
            no_docs_event: SSEEvent = {
                "event": "status",
                "data": {
                    "message": "未找到相关文档，将基于已有知识回答",
                    "node": "retrieve"
                }
            }
            result["sse_events"].append(no_docs_event)
        
        if ENABLE_VERBOSE_LOGGING:
            print(f"   [OK] 返回 {len(all_docs)} 个文档，{len(sources)} 个来源")
            if sources:
                # 验证第一个 source 的结构
                first_source = sources[0]
                print(f"   示例 Source 结构: title='{first_source['title'][:30]}...', url='{first_source['url'][:50]}...'")
        
        return result

    except Exception as e:
        # 10. 异常处理
        error_msg = f"检索过程出错：{str(e)}"
        
        if ENABLE_VERBOSE_LOGGING:
            print(f"[WARN]  RETRIEVE ERROR: {e}")
            traceback.print_exc()
        
        # 构造错误事件
        error_event: SSEEvent = {
            "event": "error",
            "data": {
                "message": error_msg,
                "node": "retrieve",
                "error": str(e)
            }
        }
        
        # 即使出错也要增加轮次，避免死循环
        return {
            "retrieved_docs": state.get("retrieved_docs", []) or [],
            "retrieval_round": int(state.get("retrieval_round", 0) or 0) + 1,
            "sources": [],
            "sse_events": [error_event],
            "messages": [{
                "role": "system",
                "content": RESPONSE_TEMPLATES.get("error_rag", error_msg)
            }]
            
        }