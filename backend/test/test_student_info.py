#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import argparse
import requests

URL = "http://127.0.0.1:8000/api/chatbot/chatbot_profile/"

STUDENT_INFO = {
    "major_code": "COMPIH",
    "target_term": "2026T1",
    "completed_courses": [
        {"course_code": "COMP1511", "term": "2024T1", "grade": "HD"},
        {"course_code": "COMP1521", "term": "2024T2", "grade": "DN"}
    ],
    "current_uoc": 36,
    "wam": 83.2,
    "max_uoc_per_term": 20,
    "requirement_types": ["core", "elective"],
    # 可选：你也可以附带更多 StudentInfo 字段
    # "degree_level": "UG",
    # "exclude_courses": ["MATH1231"],
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default="2", help="与聊天端一致的用户ID（字符串）")
    parser.add_argument("--tab-id", default=None, help="指定档案用tab_id，不传则使用 tab_profile_{user_id}")
    args = parser.parse_args()

    user_id = str(args.user_id)
    tab_id = args.tab_id or f"tab_profile_{user_id}"

    headers = {
        "Content-Type": "application/json",
        "X-User-Id": user_id,   # 关键：与聊天使用的 user_id 保持一致
        "X-Tab-Id": tab_id,     # 档案用的 tab（按 user_id 固定一个最简单）
    }

    # POST: 写入/更新档案
    payload = {"student_info": STUDENT_INFO, "tab_id": tab_id}
    print("[POST] headers:", headers)
    print("[POST] payload:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    r = requests.post(URL, headers=headers, json=payload, timeout=60)
    print("\n[POST] status:", r.status_code)
    try:
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
    except Exception:
        print(r.text)

    # GET: 读取 memory 摘要（同一个 user_id + tab_id）
    print("\n[GET] memory excerpt:")
    r2 = requests.get(URL, headers=headers, timeout=30)  # GET里也用同样的 headers
    print("[GET] status:", r2.status_code)
    try:
        print(json.dumps(r2.json(), ensure_ascii=False, indent=2))
    except Exception:
        print(r2.text)

if __name__ == "__main__":
    main()