# backend/chatbot/views.py

from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
import json
import traceback
import uuid
import time

from chatbot.langgraph_agent.timeline_store import get as timeline_get
from chatbot.langgraph_agent.main_graph import run_chat


import asyncio

@csrf_exempt
async def chat_multiround(request):
    """
    SSE 流式接口，支持客户端中止。
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed"}, status=405)

    try:
        body = request.body
        data = json.loads(body.decode("utf-8"))
        
        query = data.get("query", "").strip()
        if not query:
            return JsonResponse({"error": "Missing query field"}, status=400)

        user_id = data.get("user_id", "anonymous")
        frontend_state = data.get("frontend_state")

        # 生成或复用 tab_id
        req_tab_id = data.get("tab_id")
        tab_id = str(req_tab_id).strip() if isinstance(req_tab_id, str) and req_tab_id.strip() else None
        if not tab_id:
            tab_id = f"tab_{uuid.uuid4().hex[:12]}_{int(time.time() * 1000)}"

        # 兼容旧 history 格式
        if frontend_state is None:
            history = data.get("history", [])
            messages_list = []
            for turn in history:
                if "user" in turn:
                    messages_list.append({"role": "user", "content": turn["user"]})
                if "bot" in turn:
                    messages_list.append({"role": "assistant", "content": turn["bot"]})
            frontend_state = {"messages": messages_list}

        # 创建取消事件
        cancel_event = asyncio.Event()

        async def sse_iterator():
            try:
                async for event in run_chat(
                    query,
                    user_id=user_id,
                    frontend_state=frontend_state,
                    tab_id=tab_id,
                    cancel_event=cancel_event,  # 传递取消事件
                ):
                    event_type = event.get("event", "message")
                    event_data = event.get("data", {})
                    json_data = json.dumps(event_data, ensure_ascii=False)
                    
                    # 尝试 yield，如果客户端断开会抛出异常
                    try:
                        yield f"event: {event_type}\ndata: {json_data}\n\n".encode("utf-8")
                    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as e:
                        # 客户端主动断开
                        #logger.info(f"[{tab_id}] Client disconnected during yield: {type(e).__name__}")
                        cancel_event.set()  # 设置取消标志
                        break
                    
            except GeneratorExit:
                # 客户端断开连接
                #logger.info(f"[{tab_id}] GeneratorExit, client disconnected")
                cancel_event.set()  #  设置取消标志
                
            except Exception as e:
                tb = traceback.format_exc()
                #logger.error(f"[{tab_id}] Stream error: {e}\n{tb}")
                cancel_event.set()  #  设置取消标志
                
                # 尝试发送错误事件（可能会失败）
                try:
                    err_data = json.dumps(
                        {"message": str(e), "trace": tb}, ensure_ascii=False
                    )
                    yield f"event: error\ndata: {err_data}\n\n".encode("utf-8")
                except:
                    pass  # 忽略发送失败

        resp = StreamingHttpResponse(
            sse_iterator(), 
            content_type="text/event-stream"
        )
        resp["X-Accel-Buffering"] = "no"
        resp["Cache-Control"] = "no-cache"
        return resp

    except Exception as e:
        tb = traceback.format_exc()
        #logger.error(f"chat_multiround error: {e}\n{tb}")
        return JsonResponse({"error": str(e), "trace": tb}, status=500)


async def turn_timeline(request, turn_id: str):
    """获取指定 turn_id 的时间线事件"""
    if request.method != "GET":
        return JsonResponse({"error": "Only GET"}, status=405)
    
    # 如果 timeline_get 是同步函数，需要导入 sync_to_async
    from asgiref.sync import sync_to_async
    events = await sync_to_async(timeline_get)(turn_id)
    
    return JsonResponse(
        {"status": "ok", "turn_id": turn_id, "events": events}, 
        status=200
    )