# test_chat_multiround_cli.py
import requests
import json
import time

URL = "http://127.0.0.1:8000/api/chat_multiround/"
history = []  # [{"user":"...","bot":"..."}, ...]

print("多轮交互测试（CLI）。输入 'exit' 或 'quit' 结束。")
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

    print("请求 payload:", json.dumps(payload, ensure_ascii=False)[:1000])
    try:
        resp = requests.post(URL, json=payload, timeout=30)
    except Exception as e:
        print("请求异常：", e)
        time.sleep(1)
        continue

    if resp.status_code != 200:
        print("调用失败:", resp.status_code, resp.text[:1000])
        continue

    try:
        data = resp.json()
    except Exception:
        print("返回非 JSON：", resp.text[:1000])
        continue

    answer = data.get("answer") or ""
    sources = data.get("sources") or data.get("sources_brief") or []
    history = data.get("history") or history  # 用后端返回的 history 覆盖本地
    print("返回 data:", json.dumps(data, ensure_ascii=False)[:1000])
    print("\n--- 机器人 回复 ---")
    print(answer)
    print("--- 来源 (简略) ---")
    print(json.dumps(sources, ensure_ascii=False, indent=2))
    print("--- 当前 history (最近几轮) ---")
    print(json.dumps(history[-10:], ensure_ascii=False, indent=2))
    print("--------------------\n")
