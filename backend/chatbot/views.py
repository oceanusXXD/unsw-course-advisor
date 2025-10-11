# backend/chatbot/views.py
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
import json
import os
import traceback
from . import langgraph_chat
# 优先导入 langgraph_integration（若存在），否则回退到 rag_chain_qwen
try:
    from . import langgraph_integration as langgraph  # langgraph.run_chat(query) -> 返回 state dict
    _HAS_LANGGRAPH = True
except Exception:
    langgraph = None
    _HAS_LANGGRAPH = False

from . import rag_chain_qwen as rag  # 相对导入，根据你的目录结构调整

# ====== 辅助：序列化检索结果 ======
def _serialize_docs(docs):
    """
    将检索到的 docs 做成 JSON 可序列化的简洁列表，
    字段：course_code / source_file / score / preview（优先用 _content）
    """
    out = []
    for d in docs:
        try:
            code = d.get("course_code") or d.get("CourseCode") or d.get("assoc_code") or ""
            # 优先使用 source_file 字段
            source_file = d.get("source_file") or d.get("source") or "unknown"
            score = d.get("_score", None)
            # 优先使用 _content，再用 _text、overview 等做 preview
            preview = (d.get("_content") or d.get("_text") or d.get("content") or d.get("overview") or "")[:400]
            out.append({
                "course_code": code,
                "source_file": source_file,
                "score": float(score) if score is not None else None,
                "preview": preview
            })
        except Exception:
            continue
    return out

# ====== 非流式 Chat API ======
@csrf_exempt
def chat(request):
    """
    非流式接口：返回完整 answer + 检索到的简洁来源列表
    POST body: {"query": "..."}
    返回 JSON:
      { "answer": "...", "sources": [ {course_code, source_file, score, preview}, ... ] }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        query = data.get("query", "").strip()
        if not query:
            return JsonResponse({"error": "缺少 query 字段"}, status=400)

        # 优先使用 LangGraph 的 run_chat（如果已集成）
        if _HAS_LANGGRAPH and hasattr(langgraph, "run_chat"):
            try:
                state = langgraph.run_chat(query) # type: ignore
                # 约定：run_chat 返回的 state 中包含 "answer" 与 "sources_brief" 或 "retrieved"
                answer = state.get("answer", "")
                # 优先使用 sources_brief（若 LangGraph 已整理），否则序列化 retrieved
                if state.get("sources_brief"):
                    sources = state.get("sources_brief")
                else:
                    retrieved = state.get("retrieved", [])
                    sources = _serialize_docs(retrieved)
                return JsonResponse({"answer": answer, "sources": sources}, json_dumps_params={'ensure_ascii': False})
            except Exception as e:
                # 如果 LangGraph 内部出错，记下错误但继续回退到 rag
                print("[WARN] langgraph.run_chat() failed, fallback to rag. Error:")
                traceback.print_exc()

        # 回退到直接调用 rag.answer_with_rag（非流式）
        try:
            # answer_with_rag(stream=False) 按我们约定返回 (answer, docs)
            answer, docs = rag.answer_with_rag(query, stream=False, base_url=None, temperature=0.0)
        except TypeError:
            # 兼容：某些旧版实现可能直接返回 answer 字符串或不同签名
            maybe = rag.answer_with_rag(query, stream=False, base_url=None, temperature=0.0)
            if isinstance(maybe, tuple) and len(maybe) == 2:
                answer, docs = maybe
            else:
                # 如果仅返回字符串，把 docs 设为 []
                answer = maybe if isinstance(maybe, str) else str(maybe)
                docs = []

        serialized = _serialize_docs(docs)
        return JsonResponse({"answer": answer, "sources": serialized}, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        tb = traceback.format_exc()
        print(tb)  # 打印到服务器日志，便于调试
        return JsonResponse({"error": str(e), "trace": tb}, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
def chat_multiround(request):
    """
    多轮对话接口：
    POST body:
        {
            "query": "...",
            "history": [{"user": "...", "bot": "..."}, ...]   # 可选
        }
    返回：
        {
            "answer": "...",
            "sources": [...],
            "history": [...]
        }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        query = data.get("query", "").strip()
        history = data.get("history", [])

        if not query:
            return JsonResponse({"error": "缺少 query 字段"}, status=400)

        state = langgraph_chat.run_chat(query, history=history)
        answer = state.get("answer", "")
        sources = state.get("sources_brief", [])

        return JsonResponse({
            "answer": answer,
            "sources": sources,
            "history": state.get("history", [])
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        return JsonResponse({"error": str(e), "trace": tb}, status=500, json_dumps_params={'ensure_ascii': False})