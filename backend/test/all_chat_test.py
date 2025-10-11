# backend/test/all_chat_test.py
import requests

# ---------------- 配置 ----------------
URL = "http://127.0.0.1:8000/api/chat/"   # 非流式接口
QUERY = "ZHSS2511课程内容是什么？"

# ---------------- 打印请求内容 ----------------
print("发送的请求内容:", {"query": QUERY})

# ---------------- 调用接口 ----------------
resp = requests.post(URL, json={"query": QUERY})

# ---------------- 打印返回 ----------------
if resp.headers.get("Content-Type", "").startswith("application/json"):
    # 返回 JSON
    print("接口返回结果:", resp.json())
else:
    # 返回非 JSON（比如 HTML 错误页）
    print("接口返回非 JSON 内容:", resp.text)
