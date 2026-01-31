# test_complete_flow.py

import asyncio
import httpx

async def test_complete_rag_flow():
    """测试完整的 RAG 流程（包括所有异步节点）"""
    url = "http://127.0.0.1:8000/api/chatbot/chat_multiround/"
    
    # 测试 1: 规划类问题（触发 agentic_router）
    payload1 = {
        "query": "我想学习人工智能方向的课程，该选什么？",
        "user_id": "test_user",
        "frontend_state": {
            "messages": [],
            "student_info": {
                "major_code": "COMP",
                "year": 2,
                "completed_courses": ["COMP1511", "COMP1521"]
            }
        }
    }
    
    print("=" * 80)
    print("测试 1: 规划类问题（多节点异步流程）")
    print("=" * 80)
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=payload1) as response:
            print(f"Status: {response.status_code}\n")
            
            events = []
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data = line[5:].strip()
                    print(f"[{event_type}] {data[:100]}")
                    events.append(event_type)
    
    print(f"\n收到的事件类型: {set(events)}")
    print("[OK] 测试 1 完成\n")
    
    # 测试 2: 简单检索问题（触发 grounding_check）
    payload2 = {
        "query": "COMP3231 这门课的先修课程是什么？",
        "user_id": "test_user",
    }
    
    print("=" * 80)
    print("测试 2: 简单检索问题（RAG + Grounding）")
    print("=" * 80)
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=payload2) as response:
            print(f"Status: {response.status_code}\n")
            
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data = line[5:].strip()
                    if event_type == "token":
                        print(data, end="", flush=True)
                    else:
                        print(f"\n[{event_type}] {data[:100]}")
    
    print("\n[OK] 测试 2 完成\n")

if __name__ == "__main__":
    asyncio.run(test_complete_rag_flow())