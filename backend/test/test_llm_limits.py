# backend/test/test_llm_limits.py
import os
import sys
import asyncio
import json
import time
from pathlib import Path

# 让 Python 能找到你的项目
PROJ_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJ_ROOT))

import httpx

# 设置较小的并发和重试参数，便于观察
os.environ.setdefault("LLM_MAX_CONCURRENCY", "3")
os.environ.setdefault("LLM_MAX_RETRIES", "3")
os.environ.setdefault("LLM_RETRY_BASE", "0.05")
os.environ.setdefault("LLM_RETRY_MAX", "0.25")

from backend.chatbot.langgraph_agent.core import call_qwen_httpx, get_http_client

# -----------------------
# 统计并发的 CountingSemaphore 替身
# -----------------------
from backend.chatbot.langgraph_agent import core as core_mod

counts = {"active": 0, "max_active": 0}

class CountingSemaphore:
    def __init__(self, sem):
        self.sem = sem
    async def __aenter__(self):
        await self.sem.acquire()
        counts["active"] += 1
        counts["max_active"] = max(counts["max_active"], counts["active"])
        return self
    async def __aexit__(self, exc_type, exc, tb):
        counts["active"] -= 1
        self.sem.release()

# 替换 core.get_llm_semaphore，注入统计版
async def fake_get_llm_semaphore():
    if not hasattr(fake_get_llm_semaphore, "_underlying"):
        fake_get_llm_semaphore._underlying = asyncio.Semaphore(int(os.getenv("LLM_MAX_CONCURRENCY", "3")))
    return CountingSemaphore(fake_get_llm_semaphore._underlying)

# -----------------------
# MockTransport：模拟 429/503 与成功响应
# -----------------------
attempts_by_req: dict[str, int] = {}

def mock_handler(request: httpx.Request) -> httpx.Response:
    """
    模拟 LLM 接口：
      - 第一次尝试：根据目标 purpose 返回 429 或 503
      - 随后重试：返回 200 成功
      - 使用 Retry-After 提示退避
    """
    # 解析请求 JSON 体
    payload = {}
    try:
        if request.content:
            payload = json.loads(request.content.decode("utf-8"))
    except Exception:
        pass

    req_id = str(payload.get("request_id", "no-id"))
    purpose = payload.get("purpose", "unknown")
    attempts_by_req[req_id] = attempts_by_req.get(req_id, 0) + 1

    # 模拟请求耗时，制造重叠，便于观察并发
    time.sleep(0.1)

    # 第一次尝试：失败（429 或 503）
    if attempts_by_req[req_id] == 1:
        if purpose == "test_stream":
            return httpx.Response(
                status_code=503,
                headers={"Retry-After": "0.05"},
                content=b"Service Unavailable"
            )
        else:
            return httpx.Response(
                status_code=429,
                headers={"Retry-After": "0.05"},
                content=b"Too Many Requests"
            )

    # 第二次及以后：成功
    if payload.get("stream"):
        # 流式：返回 SSE 格式的 data: ... 行
        body = (
            'data: {"choices":[{"delta":{"content":"Hello "}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"World"}}]}\n\n'
            'data: [DONE]\n\n'
        ).encode("utf-8")
        return httpx.Response(status_code=200, content=body)
    else:
        # 非流式：返回和 Qwen 类似的 JSON
        content = {"choices": [{"message": {"role": "assistant", "content": f"OK {req_id}"}}]}
        return httpx.Response(status_code=200, json=content)

# -----------------------
# 将 MockTransport 注入 core 的全局 AsyncClient
# -----------------------
async def patch_http_client():
    transport = httpx.MockTransport(mock_handler)
    client = httpx.AsyncClient(
        transport=transport,
        timeout=httpx.Timeout(60.0, connect=10.0),
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        http2=False,
        base_url="https://mock.llm.local"
    )
    # 覆盖 core 的全局客户端
    core_mod._GLOBAL_HTTP_CLIENT = client

async def run_non_streaming_burst(n_tasks: int = 20):
    print("\n=== Non-streaming burst test ===")
    tasks = []
    start = time.perf_counter()
    for i in range(n_tasks):
        messages = [{"role": "user", "content": f"Ping nonstream {i}"}]
        # 注入 request_id 与 purpose（会被传到 payload）
        task = call_qwen_httpx(
            messages,
            stream=False,
            purpose="test_nonstream",
            request_id=f"ns-{i}"
        )
        tasks.append(task)
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.perf_counter() - start

    ok = sum(1 for r in results if not isinstance(r, Exception))
    err = [r for r in results if isinstance(r, Exception)]
    print(f"Completed: {ok}/{n_tasks}, errors: {len(err)}")
    print(f"Max concurrency observed: {counts['max_active']}")
    print(f"Elapsed: {elapsed:.2f}s (LLM_MAX_CONCURRENCY={os.getenv('LLM_MAX_CONCURRENCY')})")
    # 打印几个结果示例
    for r in results[:3]:
        print("Sample:", r if not isinstance(r, Exception) else f"ERR: {r}")

async def run_streaming_burst(n_tasks: int = 10):
    print("\n=== Streaming burst test ===")
    async def consume_stream(i: int):
        messages = [{"role": "user", "content": f"Ping stream {i}"}]
        gen = await call_qwen_httpx(
            messages,
            stream=True,
            purpose="test_stream",
            request_id=f"st-{i}"
        )
        collected = ""
        async for line in gen:
            # line 是 data: 后面的内容原样（call_qwen_httpx 不解析）
            if line.startswith("{"):  # 简单过滤
                try:
                    payload = json.loads(line)
                    delta = payload.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    collected += delta
                except Exception:
                    pass
        return collected or "<empty>"

    tasks = [consume_stream(i) for i in range(n_tasks)]
    start = time.perf_counter()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.perf_counter() - start
    ok = sum(1 for r in results if not isinstance(r, Exception))
    print(f"Completed: {ok}/{n_tasks}")
    print(f"Max concurrency observed: {counts['max_active']}")
    print(f"Elapsed: {elapsed:.2f}s (LLM_MAX_CONCURRENCY={os.getenv('LLM_MAX_CONCURRENCY')})")
    print("Sample stream decoded:", results[0])

async def main():
    # 打补丁：CountingSemaphore + MockTransport
    core_mod.get_llm_semaphore = fake_get_llm_semaphore
    await patch_http_client()

    # 重置计数器
    counts["active"] = 0
    counts["max_active"] = 0
    attempts_by_req.clear()

    # 非流式突发
    await run_non_streaming_burst(n_tasks=20)

    # 重置计数器
    counts["active"] = 0
    counts["max_active"] = 0
    attempts_by_req.clear()

    # 流式突发
    await run_streaming_burst(n_tasks=10)

    # 关闭 mock client
    client = await get_http_client()
    await client.aclose()

if __name__ == "__main__":
    asyncio.run(main())