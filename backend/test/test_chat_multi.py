import requests

URL = "http://127.0.0.1:8000/api/chat_multi/"
history = []

print("输入 'exit' 或 'quit' 结束对话")

while True:
    query = input("你：")
    if query.lower() in ("exit", "quit"):
        break

    print("发送请求内容:", {"query": query, "history": history})
    resp = requests.post(URL, json={"query": query, "history": history})
    if resp.status_code == 200:
        data = resp.json()
        print("机器人：", data.get("answer", ""))
        history = data.get("history", [])  # 保存历史，下一轮带上
    else:
        print("调用失败:", resp.status_code, resp.text)
