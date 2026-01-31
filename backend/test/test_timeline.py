# test_timeline_sse.py
"""
Timeline 测试脚本（支持 SSE 流式接口）
运行: python test_timeline_sse.py
"""
import requests
import json
import time
from typing import Dict, Any, Optional

# ==================== 配置 ====================
BASE_URL = "http://localhost:8000"
CHAT_ENDPOINT = f"{BASE_URL}/api/chatbot/chat_multiround/"
TIMELINE_ENDPOINT = f"{BASE_URL}/api/chatbot/turn/{{turn_id}}/timeline/"

# 测试查询列表
TEST_QUERIES = [
    "介绍一下 COMP9517",
    "我想选 COMP9024",
    "帮我生成选课计划",
]

# ==================== 颜色输出 ====================
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_section(title: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}{Colors.ENDC}\n")

def print_success(msg: str):
    print(f"{Colors.GREEN}[OK] {msg}{Colors.ENDC}")

def print_error(msg: str):
    print(f"{Colors.RED}[ERR] {msg}{Colors.ENDC}")

def print_info(msg: str):
    print(f"{Colors.CYAN}[INFO]  {msg}{Colors.ENDC}")

def print_warning(msg: str):
    print(f"{Colors.YELLOW}[WARN]  {msg}{Colors.ENDC}")

# ==================== SSE 解析 ====================

def parse_sse_stream(response: requests.Response) -> Dict[str, Any]:
    """
    解析 SSE 流式响应，提取关键信息
    
    返回:
    {
        "answer": "完整答案",
        "turn_id": "xxx",
        "sources": [...],
        "tokens": ["token1", "token2", ...],
        "events": [所有事件],
        "final_state": {...}
    }
    """
    result = {
        "answer": "",
        "turn_id": None,
        "sources": [],
        "tokens": [],
        "events": [],
        "final_state": None,
        "errors": [],
    }
    
    try:
        for line in response.iter_lines():
            if not line:
                continue
            
            line = line.decode('utf-8').strip()
            
            # 跳过注释行（keep-alive）
            if line.startswith(':'):
                continue
            
            # 解析 SSE 数据行
            if line.startswith('data: '):
                data_str = line[6:]  # 去掉 "data: "
                
                try:
                    event = json.loads(data_str)
                    event_type = event.get("type")
                    event_data = event.get("data")
                    
                    # 保存所有事件
                    result["events"].append(event)
                    
                    # 根据类型处理
                    if event_type == "token":
                        # 文本 token（逐字输出）
                        token = event_data if isinstance(event_data, str) else ""
                        result["tokens"].append(token)
                        result["answer"] += token
                    
                    elif event_type == "final_state":
                        # 最终状态（包含 turn_id）
                        result["final_state"] = event_data
                        if isinstance(event_data, dict):
                            result["turn_id"] = event_data.get("turn_id")
                            result["sources"] = event_data.get("sources", [])
                            # 如果 answer 为空，从 final_state 中提取
                            if not result["answer"] and event_data.get("answer"):
                                result["answer"] = event_data["answer"]
                    
                    elif event_type == "error":
                        # 错误事件
                        result["errors"].append(event_data)
                        print_warning(f"SSE 错误事件: {event_data}")
                    
                    elif event_type == "end":
                        # 结束标记
                        print_info("SSE 流结束")
                        break
                
                except json.JSONDecodeError as e:
                    print_warning(f"解析 SSE 事件失败: {e}, 原始数据: {data_str[:100]}")
    
    except Exception as e:
        print_error(f"SSE 流解析异常: {e}")
        import traceback
        traceback.print_exc()
    
    return result


def send_chat_message(query: str, user_id: str = "test_user") -> Dict[str, Any]:
    """发送聊天消息（SSE 流式），返回完整结果"""
    print_info(f"发送消息: '{query}'")
    
    try:
        response = requests.post(
            CHAT_ENDPOINT,
            json={"query": query, "user_id": user_id},
            stream=True,  #  关键：流式接收
            timeout=60
        )
        response.raise_for_status()
        
        # 检查 Content-Type
        content_type = response.headers.get('Content-Type', '')
        if 'text/event-stream' not in content_type:
            print_warning(f"Content-Type 不是 SSE: {content_type}")
        
        print_info("开始接收 SSE 流...")
        
        # 解析流
        result = parse_sse_stream(response)
        
        # 统计
        token_count = len(result["tokens"])
        event_count = len(result["events"])
        
        print_success(f"SSE 流接收完成 ({token_count} tokens, {event_count} events)")
        
        return result
    
    except requests.exceptions.RequestException as e:
        print_error(f"请求失败: {e}")
        import traceback
        traceback.print_exc()
        return {}


def get_timeline(turn_id: str) -> Dict[str, Any]:
    """查询 Timeline"""
    url = TIMELINE_ENDPOINT.format(turn_id=turn_id)
    print_info(f"查询 Timeline: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        print_success(f"Timeline 查询成功 (HTTP {response.status_code})")
        return data
    
    except requests.exceptions.RequestException as e:
        print_error(f"Timeline 查询失败: {e}")
        return {}


def display_timeline(timeline_data: Dict[str, Any]):
    """格式化展示 Timeline"""
    if not timeline_data or timeline_data.get("status") != "ok":
        print_warning("Timeline 数据为空或查询失败")
        print(json.dumps(timeline_data, indent=2, ensure_ascii=False))
        return
    
    events = timeline_data.get("events", [])
    turn_id = timeline_data.get("turn_id", "N/A")
    
    print(f"\n{Colors.BOLD}[Stats] Timeline 详情{Colors.ENDC}")
    print(f"   Turn ID: {Colors.CYAN}{turn_id}{Colors.ENDC}")
    print(f"   事件数量: {Colors.CYAN}{len(events)}{Colors.ENDC}\n")
    
    if not events:
        print_warning("没有路由事件记录")
        return
    
    # 遍历展示每个事件
    for idx, event in enumerate(events, 1):
        event_type = event.get("type", "unknown")
        data = event.get("data", {})
        
        print(f"{Colors.BOLD}[事件 {idx}] {event_type}{Colors.ENDC}")
        print(f"  ├─ 时间: {data.get('ts', 'N/A')}")
        
        # 决策函数
        if data.get("function"):
            function_name = data["function"]
            color = Colors.GREEN if function_name != "general_chat" else Colors.YELLOW
            print(f"  ├─ 决策函数: {color}{function_name}{Colors.ENDC}")
        
        # 参数
        arguments = data.get("arguments", {})
        if arguments:
            print(f"  ├─ 参数:")
            for key, value in arguments.items():
                if key == "reasoning":
                    # 推理单独展示（换行）
                    print(f"  │  └─ {Colors.BOLD}reasoning:{Colors.ENDC}")
                    reasoning = str(value)
                    for i in range(0, len(reasoning), 60):
                        print(f"  │     {reasoning[i:i+60]}")
                else:
                    print(f"  │  └─ {key}: {value}")
        
        # 错误信息
        if data.get("error"):
            print(f"  └─ {Colors.RED}错误: {data['error']}{Colors.ENDC}")
        else:
            print(f"  └─ {Colors.GREEN}[OK] 成功{Colors.ENDC}")
        
        print()


def display_chat_response(response: Dict[str, Any]):
    """展示聊天响应摘要"""
    print(f"\n{Colors.BOLD} 聊天响应摘要{Colors.ENDC}")
    
    # Turn ID
    turn_id = response.get("turn_id")
    if turn_id:
        print(f"   Turn ID: {Colors.CYAN}{turn_id}{Colors.ENDC}")
    else:
        print_warning("   响应中没有 turn_id！")
    
    # 答案预览
    answer = response.get("answer", "")
    if answer:
        preview = answer[:150].replace('\n', ' ')
        if len(answer) > 150:
            preview += "..."
        print(f"   答案预览: {preview}")
        print(f"   答案总长度: {len(answer)} 字符")
    else:
        print_warning("   没有答案内容")
    
    # Sources
    sources = response.get("sources", [])
    if sources:
        print(f"   参考来源: {len(sources)} 个")
    
    # Token 统计
    token_count = len(response.get("tokens", []))
    if token_count > 0:
        print(f"   Token 数量: {token_count}")
    
    # 事件统计
    events = response.get("events", [])
    event_types = {}
    for evt in events:
        et = evt.get("type", "unknown")
        event_types[et] = event_types.get(et, 0) + 1
    
    if event_types:
        print(f"   SSE 事件统计:")
        for et, count in event_types.items():
            print(f"      - {et}: {count}")
    
    # 错误
    errors = response.get("errors", [])
    if errors:
        print_error(f"   错误数量: {len(errors)}")
        for err in errors:
            print(f"      - {err}")
    
    print()


# ==================== 主测试流程 ====================

def test_single_query(query: str):
    """测试单个查询"""
    print_section(f"测试查询: '{query}'")
    
    # Step 1: 发送聊天消息（SSE 流式）
    chat_response = send_chat_message(query)
    if not chat_response:
        print_error("聊天请求失败，跳过")
        return
    
    # Step 2: 展示聊天响应
    display_chat_response(chat_response)
    
    # Step 3: 提取 turn_id
    turn_id = chat_response.get("turn_id")
    if not turn_id:
        print_error("响应中没有 turn_id，无法查询 Timeline")
        
        # 尝试从 final_state 中获取
        final_state = chat_response.get("final_state")
        if final_state and isinstance(final_state, dict):
            turn_id = final_state.get("turn_id")
            if turn_id:
                print_info(f"从 final_state 中获取到 turn_id: {turn_id}")
        
        if not turn_id:
            print_warning("完整响应:")
            print(json.dumps(chat_response, indent=2, ensure_ascii=False)[:1000])
            return
    
    # Step 4: 等待一下（确保 Timeline 写入完成）
    print_info("等待 1 秒（确保 Timeline 写入）...")
    time.sleep(1)
    
    # Step 5: 查询 Timeline
    timeline_data = get_timeline(turn_id)
    
    # Step 6: 展示 Timeline
    display_timeline(timeline_data)


def test_all():
    """测试所有查询"""
    print_section("[START] 开始 Timeline 完整测试（SSE 版本）")
    
    print(f"测试配置:")
    print(f"  - 后端地址: {BASE_URL}")
    print(f"  - 聊天接口: {CHAT_ENDPOINT} (SSE 流式)")
    print(f"  - Timeline 接口: {TIMELINE_ENDPOINT}")
    print(f"  - 测试查询数: {len(TEST_QUERIES)}")
    
    # 测试连通性
    try:
        response = requests.get(BASE_URL, timeout=5)
        print_success(f"后端连通性检查通过 (HTTP {response.status_code})")
    except requests.exceptions.RequestException as e:
        print_error(f"后端无法访问: {e}")
        print_warning("请确保 Django 服务已启动！")
        return
    
    # 逐个测试
    for idx, query in enumerate(TEST_QUERIES, 1):
        test_single_query(query)
        
        # 不是最后一个查询时，等待一下
        if idx < len(TEST_QUERIES):
            print_info("等待 2 秒后进行下一个测试...\n")
            time.sleep(2)
    
    print_section("[DONE] 所有测试完成")


# ==================== 交互模式 ====================

def interactive_mode():
    """交互模式：手动输入查询"""
    print_section("交互模式（SSE 流式）")
    print("输入查询来测试 Timeline（输入 'quit' 退出）\n")
    
    while True:
        try:
            query = input(f"{Colors.BOLD}你的查询 > {Colors.ENDC}").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                print_info("退出交互模式")
                break
            
            if not query:
                continue
            
            test_single_query(query)
            print()
        
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}用户中断{Colors.ENDC}")
            break
        except Exception as e:
            print_error(f"发生错误: {e}")


# ==================== 入口 ====================

if __name__ == "__main__":
    import sys
    
    print(f"""
{Colors.HEADER}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════╗
║          Timeline 测试工具（SSE 流式版本）               ║
║                                                           ║
║  支持 Server-Sent Events (SSE) 流式接口                  ║
╚═══════════════════════════════════════════════════════════╝
{Colors.ENDC}
""")
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "interactive":
            interactive_mode()
        else:
            # 手动指定查询
            custom_query = " ".join(sys.argv[1:])
            test_single_query(custom_query)
    else:
        # 默认：运行所有预设测试
        test_all()