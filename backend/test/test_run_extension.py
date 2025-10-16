# test_call_django.py
import requests
import json

URL = "http://localhost:8000/extension/start-extension/"

def main():
    print("请求 Django 接口：", URL)
    try:
        r = requests.get(URL, timeout=120)
        print("HTTP 状态码：", r.status_code)
        data = r.json()
        print("返回 JSON：")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        print("请求失败：", e)

if __name__ == '__main__':
    main()
