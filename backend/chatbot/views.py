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
    return JsonResponse({"error": "This endpoint is deprecated. Use /chat_multiround/ instead."}, status=410)

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

        state = langgraph_chat.run_chat(query)
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