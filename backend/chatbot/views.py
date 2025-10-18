# backend/chatbot/views.py
from django.http import JsonResponse, StreamingHttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import traceback
from chatbot.langgraph_agent import langgraph_agent
from chatbot.langgraph_agent.tools import crypto as crypto_module

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
        
        def event_stream_generator():
            try:
                # Convert history from {"user":... "bot":...} to LangChain format
                init_messages = []
                for turn in history:
                    if "user" in turn:
                        init_messages.append({"type": "human", "content": turn["user"]})
                    if "bot" in turn:
                        init_messages.append({"type": "ai", "content": turn["bot"]})

                for event in langgraph_agent.main_graph.run_chat(query, init_messages=init_messages):
                    json_event = json.dumps(event, ensure_ascii=False)
                    yield f"data: {json_event}\n\n".encode('utf-8')
            
            except Exception as e:
                tb = traceback.format_exc()
                print(f"Error in stream generator: {e}\n{tb}")
                error_event = {"type": "error", "data": {"message": "An error occurred in the stream generator.", "trace": str(e)}}
                json_event = json.dumps(error_event, ensure_ascii=False)
                yield f"data: {json_event}\n\n".encode('utf-8')

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
    
@csrf_exempt
@require_POST
def activate_license_api(request):
    """
    接口: POST /api/activate_license/
    请求 body JSON: {"user_id": "...", "device_id": "..."}
    返回: {"license_key": "...", "user_key": "...", "message": "..."}
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    user_id = payload.get("user_id")
    device_id = payload.get("device_id")
    if not user_id or not device_id:
        return HttpResponseBadRequest("Missing user_id or device_id")

    res = crypto_module.activate_license(user_id, device_id)
    return JsonResponse(res, safe=True)


@csrf_exempt
@require_POST
def get_file_key_api(request):
    """
    接口: POST /api/get_file_key/
    请求 body JSON: {"user_id": "...", "file_id": "..."}
    返回: {"file_id": "...", "nonce": "...", "tag": "...", "encrypted_file_key": "...", "message": "..."} 或 {"error": "..."}
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    user_id = payload.get("user_id")
    file_id = payload.get("file_id")
    if not user_id or not file_id:
        return HttpResponseBadRequest("Missing user_id or file_id")

    res = crypto_module.get_file_decrypt_key(user_id, file_id)
    return JsonResponse(res, safe=True)


@csrf_exempt
@require_POST
def validate_license_api(request):
    """
    接口: POST /api/validate_license/
    请求 body JSON: {"user_id": "...", "license_key": "..."}
    返回: {"valid": True/False, ...}
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    user_id = payload.get("user_id")
    license_key = payload.get("license_key")
    if not user_id or not license_key:
        return HttpResponseBadRequest("Missing user_id or license_key")

    res = crypto_module.validate_license(user_id, license_key)
    return JsonResponse(res, safe=True)
