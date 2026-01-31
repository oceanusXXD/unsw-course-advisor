#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# test_e2e_profile_and_chat.py
# 描述：一个自动化的端到端测试脚本。
# 1. 调用 /chatbot_profile/ 注入学生档案（硬规则）。
# 2. 调用 /chat_multiround/ 询问规划问题，验证 Agent 是否能利用已注入的档案。
# 3. 继续追问特定课程为什么不能选（COMP6713、COMP9101）。

import json
import requests
import time
import traceback
import uuid

# --- 配置 ---
BASE_URL = "http://127.0.0.1:8000/api/chatbot"
PROFILE_URL = f"{BASE_URL}/chatbot_profile/"
CHAT_URL = f"{BASE_URL}/chat_multiround/"

# 使用唯一的 Session ID 确保同一会话
SESSION_ID = f"e2e-test-{uuid.uuid4()}"

# [OK] 1. 学生档案（包含 major_code）
STUDENT_INFO = {
    "major_code": "COMPIH",
    "target_term": "2026T1",
    "completed_courses": ["COMP3411", "COMP9517", "COMP9417"],
    "degree_level":"PG"
}
STUDENT_INFO["current_uoc"] = 6 * len(STUDENT_INFO["completed_courses"])
STUDENT_INFO["wam"] = 80.0

# [OK] 2. 初次询问
FIRST_QUERY = "我下学期（2026 T1）该选什么课？"


# --- 辅助函数 ---
def print_header(title: str):
    print("\n" + "=" * 80)
    print(f" {title.upper()} ".center(80, "="))
    print("=" * 80)


def print_status(url: str, status_code: int):
    status_str = f"[{status_code}]"
    if 200 <= status_code < 300:
        print(f"[OK] {url} - 成功 {status_str}")
    else:
        print(f"[ERR] {url} - 失败 {status_str}")


def pretty_print_json(data: dict):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def parse_sse_stream(resp: requests.Response):
    """解析 SSE 流并打印关键事件"""
    print("\n机器人: ", end="", flush=True)
    full_answer = ""
    current_event_type = None
    event_counts = {}

    try:
        for line in resp.iter_lines():
            if not line:
                continue
            decoded_line = line.decode("utf-8")
            if decoded_line.startswith(":"):
                continue
            if decoded_line.startswith("event:"):
                current_event_type = decoded_line[6:].strip()
                event_counts[current_event_type] = event_counts.get(current_event_type, 0) + 1
                continue
            elif decoded_line.startswith("data:"):
                json_str = decoded_line[5:].strip()
                if not json_str:
                    continue
                try:
                    data_payload = json.loads(json_str)
                    if current_event_type == "token":
                        if isinstance(data_payload, str):
                            print(data_payload, end="", flush=True)
                            full_answer += data_payload
                    elif current_event_type == "status":
                        if isinstance(data_payload, dict):
                            node = data_payload.get("node", "...")
                            msg = data_payload.get("message", "")
                            if node == "router_llm_planner":
                                decision = data_payload.get("decision", {})
                                route = decision.get("route")
                                reason = decision.get("reason", "")
                                print(f"\n\n[ROUTE] [路由决策]")
                                print(f"   -> 目标: {route}")
                                print(f"   -> 理由: {reason[:150]}...")
                                print(f"\n机器人: ", end="", flush=True)
                            elif node == "planner":
                                print(f"\n[Steps] [规划器执行中] {msg}", end="", flush=True)
                            else:
                                print(f"\n[{node}] {msg}", end="", flush=True)
                    elif current_event_type == "source":
                        if isinstance(data_payload, dict):
                            title = data_payload.get("title", "N/A")
                            print(f"\n[Docs] 来源: {title}", end="", flush=True)
                    elif current_event_type == "citation":
                        if isinstance(data_payload, dict):
                            cid = data_payload.get("id", "?")
                            print(f"\n[Cite] 引用 [{cid}]", end="", flush=True)
                    elif current_event_type == "error":
                        print(f"\n\n[ERR] 后端错误:")
                        pretty_print_json(data_payload)
                    elif current_event_type == "final_state":
                        print(f"\n\n[OK] 会话状态已更新")
                    elif current_event_type == "end":
                        print(f"\n--- 流结束 ---")
                except json.JSONDecodeError:
                    print(f"\n[警告] 无法解析的 JSON 数据: {json_str[:100]}")
    except KeyboardInterrupt:
        print("\n\n...用户中断了流式输出")
    except Exception as e:
        print(f"\n\n[ERR] 解析流时出错: {e}")
        traceback.print_exc()

    print("\n\n[Stats] 事件统计:")
    for event_type, count in event_counts.items():
        print(f"   {event_type}: {count} 次")
    return full_answer


# --- 主流程 ---
def main():
    print(f"\n{'=' * 80}")
    print(f"自动化端到端测试 (E2E Test)".center(80))
    print(f"{'=' * 80}")
    print(f"会话 ID (Session ID): {SESSION_ID}")

    headers = {"Content-Type": "application/json", "X-Session-ID": SESSION_ID}

    # 步骤 1: 注入学生档案
    print_header("步骤 1: POST /api/chatbot/chatbot_profile/")
    post_payload = {"student_info": STUDENT_INFO}
    print("提交数据:")
    pretty_print_json(post_payload)

    try:
        r_profile = requests.post(PROFILE_URL, headers=headers, data=json.dumps(post_payload), timeout=60)
        print_status(PROFILE_URL, r_profile.status_code)
        if r_profile.status_code != 200:
            print("[ERR] 档案注入失败")
            print(r_profile.text)
            return
        print("[OK] 档案注入成功。返回：")
        pretty_print_json(r_profile.json())
    except requests.exceptions.RequestException as e:
        print(f"[ERR] 请求失败: {e}")
        return

    # 步骤 2: GET 验证内存
    print_header("步骤 2: GET /api/chatbot/chatbot_profile/")
    try:
        r_get = requests.get(PROFILE_URL, headers=headers, timeout=30)
        print_status(PROFILE_URL, r_get.status_code)
        if r_get.status_code == 200:
            print("[OK] 内存读取成功。内容摘要：")
            pretty_print_json(r_get.json())
    except requests.exceptions.RequestException as e:
        print(f"[ERR] 请求失败: {e}")

    time.sleep(1)

    # 步骤 3: 第一次问答
    print_header(f"步骤 3: POST /api/chatbot/chat_multiround/")
    print(f"询问: '{FIRST_QUERY}'")

    chat_payload = {
        "query": FIRST_QUERY,
        "user_id": SESSION_ID,
        "frontend_state": {"messages": [], "pending_file_generation": None, "pending_plugin_install": None},
    }

    try:
        with requests.post(CHAT_URL, json=chat_payload, headers=headers, timeout=120, stream=True) as resp:
            print_status(CHAT_URL, resp.status_code)
            if resp.status_code != 200:
                print("[ERR] 错误响应:")
                print(resp.text)
                return
            answer = parse_sse_stream(resp)
            print_header("验证结果")
            validation_passed = True
            if STUDENT_INFO["major_code"].upper() in answer.upper():
                print(f"[OK] 答案提到了专业代码: {STUDENT_INFO['major_code']}")
            else:
                print(f"[WARN] 答案未明确提到专业代码 ({STUDENT_INFO['major_code']})")
                validation_passed = False
            if STUDENT_INFO["target_term"] in answer:
                print(f"[OK] 答案提到了目标学期: {STUDENT_INFO['target_term']}")
            else:
                print(f"[WARN] 答案未明确提到目标学期 ({STUDENT_INFO['target_term']})")
            mentioned_courses = [c for c in STUDENT_INFO["completed_courses"] if c in answer.upper()]
            if mentioned_courses:
                print(f"[OK] 答案提到了已修课程: {', '.join(mentioned_courses)}")
            else:
                print("[WARN] 答案未提到任何已修课程")
                validation_passed = False
            if len(answer) > 50:
                print(f"[OK] 答案长度合理: {len(answer)} 字符")
            else:
                print(f"[ERR] 答案过短: {len(answer)} 字符")
                validation_passed = False

            print("\n" + "=" * 80)
            if validation_passed:
                print("[DONE] 端到端测试通过！Agent 成功使用了注入的学生档案。")
            else:
                print("[WARN] 测试完成，但部分验证未通过。")
            print("=" * 80)

    except requests.exceptions.RequestException as e:
        print(f"[ERR] 请求失败: {e}")
        traceback.print_exc()
        return

    # --- 步骤 4: 追加提问 ---
    follow_up_questions = ["为什么不能选 COMP6713？", "为什么不能选 COMP9101？"]
    for q in follow_up_questions:
        print_header(f"追加询问: {q}")
        chat_payload = {
            "query": q,
            "user_id": SESSION_ID,  # 继续同一会话
            "frontend_state": {"messages": [], "pending_file_generation": None, "pending_plugin_install": None},
        }
        try:
            with requests.post(CHAT_URL, json=chat_payload, headers=headers, timeout=120, stream=True) as resp:
                print_status(CHAT_URL, resp.status_code)
                if resp.status_code != 200:
                    print("[ERR] 追加询问失败:")
                    print(resp.text)
                    continue
                _ = parse_sse_stream(resp)
        except requests.exceptions.RequestException as e:
            print(f"[ERR] 追加请求失败: {e}")


if __name__ == "__main__":
    main()
