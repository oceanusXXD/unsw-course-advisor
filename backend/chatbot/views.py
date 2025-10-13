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
    Multi-round chat interface with streaming response (Server-Sent Events).
    POST body:
        {
            "query": "...",
            "history": [{"user": "...", "bot": "..."}, ...]   # Optional
        }
    
    Returns a text/event-stream response.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        query = data.get("query", "").strip()
        history = data.get("history", [])

        if not query:
            return JsonResponse({"error": "Missing query field"}, status=400)
        
        # This generator will produce the event stream content
        def event_stream_generator():
            try:
                # Convert history from {"user":... "bot":...} to LangChain format
                init_messages = []
                for turn in history:
                    if "user" in turn:
                        init_messages.append({"type": "human", "content": turn["user"]})
                    if "bot" in turn:
                        init_messages.append({"type": "ai", "content": turn["bot"]})

                # Call the new streaming function from langgraph_chat
                for event in langgraph_chat.run_chat(query, init_messages=init_messages):
                    # Format as a Server-Sent Event (SSE)
                    json_event = json.dumps(event, ensure_ascii=False)
                    sse_message = f"data: {json_event}\n\n"
                    yield sse_message.encode('utf-8')
            
            except Exception as e:
                tb = traceback.format_exc()
                print(f"Error in stream generator: {e}\n{tb}")
                error_event = {
                    "type": "error",
                    "data": {"message": "An error occurred in the stream generator.", "trace": str(e)}
                }
                json_event = json.dumps(error_event, ensure_ascii=False)
                sse_message = f"data: {json_event}\n\n"
                yield sse_message.encode('utf-8')

        # Return the StreamingHttpResponse
        response = StreamingHttpResponse(event_stream_generator(), content_type='text/event-stream')
        response['X-Accel-Buffering'] = 'no'  # Important for NGINX buffering
        response['Cache-Control'] = 'no-cache'
        return response

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON in request body"}, status=400)
    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        return JsonResponse({"error": str(e), "trace": tb}, status=500, json_dumps_params={'ensure_ascii': False})