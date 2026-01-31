# test_chat_multiround_cli.py

import requests
import json
import time
import traceback

# --- 配置 ---
URL = "http://127.0.0.1:8000/api/chatbot/chat_multiround/" 

# --- 全局状态 ---
history = []
pending_file_state = None
pending_plugin_state = None

# --- 主程序 ---
if __name__ == "__main__":
    print("=" * 60)
    print(" 多轮交互测试命令行客户端 (Streaming & SSE v2)")
    print("=" * 60)
    print(" - 支持多轮对话历史")
    print(" - 支持 pending 状态（文件生成/插件安装）")
    print(" - 支持实时状态更新、来源、引用等事件")
    print(" - 输入 'exit' 或 'quit' 结束程序。")
    
    user_id = input("\n请输入一个 user_id (可选，直接回车则为 'anonymous'): ").strip() or "anonymous"
    print(f"当前用户 ID: {user_id}")

    while True:
        try:
            query = input("\n你: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n检测到中断，程序结束。")
            break

        if not query:
            continue
        if query.lower() in ("exit", "quit"):
            break

        # 1. 构建与前端一致的 payload
        messages = []
        for turn in history:
            if "user" in turn and turn["user"]:
                messages.append({"role": "user", "content": turn["user"]})
            if "bot" in turn and turn["bot"]:
                messages.append({"role": "assistant", "content": turn["bot"]})
        
        payload = {
            "query": query,
            "user_id": user_id,
            "frontend_state": {
                "messages": messages,
                "pending_file_generation": pending_file_state,
                "pending_plugin_install": pending_plugin_state
            }
        }

        # 2. 初始化本轮对话的状态变量
        full_answer = ""
        latest_sources = []
        latest_citations = []
        
        try:
            with requests.post(URL, json=payload, timeout=120, stream=True) as resp:
                if resp.status_code != 200:
                    print(f"\n[ERR] API 调用失败 (HTTP {resp.status_code})")
                    try:
                        error_text = resp.text[:1000]
                        print(f"   错误信息: {error_text}")
                    except:
                        pass
                    continue
                
                print("\n机器人: ", end="", flush=True)
                
                # 3. 核心 SSE 解析循环
                current_event_type = "message"
                
                for line in resp.iter_lines():
                    if not line:
                        continue
                    
                    decoded_line = line.decode('utf-8')
                    
                    if decoded_line.startswith(':'):
                        continue
                    
                    if decoded_line.startswith('event:'):
                        current_event_type = decoded_line[6:].strip()
                        
                    elif decoded_line.startswith('data:'):
                        json_str = decoded_line[5:].strip()
                        if not json_str:
                            continue
                        
                        try:
                            data_payload = json.loads(json_str)
                            
                            # --- 根据事件类型分发处理 ---
                            
                            if current_event_type == "token":
                                # token 事件的 data 是字符串
                                if isinstance(data_payload, str):
                                    print(data_payload, end="", flush=True)
                                    full_answer += data_payload
                                
                            elif current_event_type == "status":
                                # 确保是字典类型再调用 .get()
                                if isinstance(data_payload, dict):
                                    node = data_payload.get('node', '...')
                                    msg = data_payload.get('message', '')
                                    print(f"\n[状态: {node}] \n{msg}", end="", flush=True)
                            
                            elif current_event_type == "source":
                                if isinstance(data_payload, dict):
                                    latest_sources.append(data_payload)

                            elif current_event_type == "citation":
                                if isinstance(data_payload, dict):
                                    latest_citations.append(data_payload)
                            
                            elif current_event_type == "final_state":
                                if isinstance(data_payload, dict):
                                    pending_file_state = data_payload.get("pending_file_generation")
                                    pending_plugin_state = data_payload.get("pending_plugin_install")
                                    
                                    new_messages = data_payload.get("messages", [])
                                    if len(new_messages) >= 2:
                                        last_user_msg = new_messages[-2]
                                        last_bot_msg = new_messages[-1]
                                        if last_user_msg.get("role") == "user" and last_bot_msg.get("role") == "assistant":
                                            history.append({
                                                "user": last_user_msg.get("content"),
                                                "bot": last_bot_msg.get("content")
                                            })
                            
                            elif current_event_type == "error":
                                if isinstance(data_payload, dict):
                                    print(f"\n\n[ERR] 后端错误: {data_payload.get('message', str(data_payload))}")
                                else:
                                    print(f"\n\n[ERR] 后端错误: {data_payload}")
                                
                            elif current_event_type == "end":
                                # end 事件可能是字符串，不需要处理
                                break
                                
                        except json.JSONDecodeError:
                            print(f"\n[警告] 无法解析的 JSON 数据: {json_str}")
                        except Exception as e:
                            print(f"\n\n[ERR] 客户端处理事件 '{current_event_type}' 时出错: {e}")
                            traceback.print_exc()

                        current_event_type = "message"

            # 4. 在流结束后，打印收集到的摘要信息
            print()
            if latest_sources:
                print("\n[Docs] 参考来源:")
                for i, doc in enumerate(latest_sources[:5]):
                    title = doc.get("title", "未知标题")
                    url = doc.get("url", "")
                    snippet = doc.get("snippet", "")
                    print(f"  [{i+1}] {title}")
                    if url: print(f"      URL: {url}")
                    if snippet: print(f"      摘要: {snippet[:80]}...")
            
            if latest_citations:
                print("\n[Cite] 答案引用:")
                sorted_citations = sorted(latest_citations, key=lambda c: c.get('index', float('inf')))
                for citation in sorted_citations:
                    index = citation.get("index")
                    title = citation.get("title", "未知标题")
                    print(f"  [{index}] {title}")
            
            # 5. 打印调试信息
            if pending_file_state:
                print(f"\n[Debug: 记住 pending_file: {pending_file_state}]")
            if pending_plugin_state:
                print(f"\n[Debug: 记住 pending_plugin: {pending_plugin_state}]")
            if len(history) > 0:
                print(f"\n 当前对话历史: {len(history)} 轮")

        except requests.exceptions.Timeout:
            print("\n[Timer]  请求超时")
        except requests.exceptions.RequestException as e:
            print(f"\n[ERR] 请求异常: {e}")
        except KeyboardInterrupt:
            print("\n\n...用户中断了流式输出")
        except Exception as e:
            print(f"\n[ERR] 发生未知错误: {e}")
            traceback.print_exc()

    print("\n再见！")