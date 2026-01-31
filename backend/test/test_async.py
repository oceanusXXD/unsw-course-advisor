import asyncio
import httpx

async def test_streaming():
    url = "http://127.0.0.1:8000/api/chatbot/chat_multiround/"
    payload = {
        "query": "介绍一下人工智能",
        "user_id": "test_user",
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, json=payload) as response:
            print(f"Status: {response.status_code}")
            async for line in response.aiter_lines():
                print(line)

if __name__ == "__main__":
    asyncio.run(test_streaming())