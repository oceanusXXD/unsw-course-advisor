# test_chat_multiround_cli.py
import requests
import json
import time

# UPDATE THE URL TO THE NEW STREAMING ENDPOINT
URL = "http://127.0.0.1:8000/api/chat_multiround/" 
history = []  # [{"user":"...","bot":"..."}, ...]

print("多轮交互测试 (Streaming CLI)。输入 'exit' 或 'quit' 结束。")
user_id = input("可选：输入 user_id（直接回车跳过）: ").strip() or None

while True:
    try:
        query = input("你：").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n结束。")
        break

    if not query:
        continue
    if query.lower() in ("exit", "quit"):
        break

    payload = {"query": query, "history": history}
    if user_id:
        payload["user_id"] = user_id

    full_answer = ""
    sources = []
    
    try:
        # Set stream=True to handle the response as a stream
        with requests.post(URL, json=payload, timeout=60, stream=True) as resp:
            if resp.status_code != 200:
                print(f"调用失败: {resp.status_code}\n{resp.text[:1000]}")
                continue
            
            print("\n--- 机器人 回复 ---")
            # Iterate over the response line by line
            for line in resp.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    # Check if the line is an SSE data line
                    if decoded_line.startswith('data:'):
                        try:
                            # Strip the 'data: ' prefix and parse JSON
                            event_data = json.loads(decoded_line[6:])
                            event_type = event_data.get("type")
                            data = event_data.get("data")

                            if event_type == "token":
                                print(data, end="", flush=True) # Print token as it arrives
                                full_answer += data
                            elif event_type == "sources":
                                sources = data
                            elif event_type == "history":
                                # The final history is sent at the end
                                history = data
                            elif event_type == "error":
                                print(f"\n\n--- 错误 ---")
                                print(json.dumps(data, ensure_ascii=False, indent=2))
                            elif event_type == "end":
                                break # Graceful end of stream

                        except json.JSONDecodeError:
                            print(f"\n[Warning] Failed to decode JSON from line: {decoded_line}")
                            continue
        
        # After the stream is complete, print the sources
        print("\n--- 来源 (简略) ---")
        if sources:
            print(json.dumps(sources, ensure_ascii=False, indent=2))
        else:
            print("[]")
            
        print("--- 当前 history (最近几轮) ---")
        print(json.dumps(history[-10:], ensure_ascii=False, indent=2))
        print("--------------------\n")


    except requests.exceptions.RequestException as e:
        print(f"请求异常: {e}")
        time.sleep(1)
        continue
    except Exception as e:
        print(f"处理响应时发生未知错误: {e}")
        break