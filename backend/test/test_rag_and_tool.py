
import requests
import json
import time
import sys

URL = "http://127.0.0.1:8000/api/chat_multiround/"
HEADERS = {"Content-Type": "application/json"}

def try_fix_mojibake(s: str) -> str:
    """
    有时 UTF-8 bytes 被当成 latin1 解码，导致类似 'æªè³...'。
    常见恢复方法：先将当前 str 当作 latin1 bytes，再用 utf-8 解码。
    多做一次尝试，若失败则返回原串。
    """
    try:
        fixed = s.encode('latin1').decode('utf-8')
        # 简单校验：若 fixed 包含常见汉字就认为修复成功
        if any('\u4e00' <= ch <= '\u9fff' for ch in fixed):
            return fixed
    except Exception:
        pass
    return s

def safe_json_loads(s: str):
    """
    尝试把 s 解析为 JSON，做若干容错尝试（strip 前缀、修复 mojibake）。
    返回 (obj, used_string) 或 (None, last_string)。
    """
    if not s or not s.strip():
        return None, s

    # 1) 直接尝试
    try:
        return json.loads(s), s
    except Exception:
        pass

    # 2) 如果以 "data: " 前缀，移除后重试
    if s.startswith("data:"):
        payload = s[len("data:"):].strip()
        try:
            return json.loads(payload), payload
        except Exception:
            s = payload

    # 3) 修复 mojibake（latin1->utf8）
    fixed = try_fix_mojibake(s)
    if fixed != s:
        try:
            return json.loads(fixed), fixed
        except Exception:
            # 继续尝试去掉 data:
            if fixed.startswith("data:"):
                payload = fixed[len("data:"):].strip()
                try:
                    return json.loads(payload), payload
                except Exception:
                    pass

    # 4) 无法解析
    return None, s

def pretty_print_debug(title, data):
    print(f"\n[DEBUG] {title}:")
    if isinstance(data, (dict, list)):
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(str(data))

def debug_chat(query: str, user_id="tester"):
    print("\n" + "="*80)
    print("🧠 测试会话开始：", query)
    print("="*80)

    payload = {
        "query": query,
        "user_id": user_id,
        "enable_grounding": True,
        "enable_suggestions": False,
        "debug": True,  # 让后端在执行各节点时输出 debug event（可选）
    }

    # 用 stream=True 读取响应体（注意：服务端需返回 200 并使用 chunked transfer / text/event-stream）
    try:
        with requests.post(URL, json=payload, stream=True, headers=HEADERS, timeout=120) as resp:
            resp.raise_for_status()
            buffer = ""  # 保留上一次残缺数据（当 JSON 被拆分时使用）
            final_answer = ""
            print("🚀 连接成功，开始接收流式数据...\n")

            for raw in resp.iter_lines(decode_unicode=False):
                # raw 是 bytes 或 空行
                if not raw:
                    continue

                # 尝试把 bytes 解码为 str（优先 utf-8），并保留原 bytes 以便修复
                if isinstance(raw, bytes):
                    try:
                        chunk = raw.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            # 有时服务器把 utf-8 bytes 当 latin1 解码/转发，先尝试 latin1
                            chunk = raw.decode('latin1')
                        except Exception:
                            chunk = raw.decode('utf-8', errors='ignore')
                else:
                    chunk = str(raw)

                # SSE 会有 "data: {...}" 或纯 JSON 每行，可能也会是 token 文本
                # 把 chunk 附加到 buffer（用 \n 分割可能的多条消息）
                buffer += chunk
                # 遍历可能的完整行（以 "\n" 或 "\r\n" 结尾为一条），保留最后残缺
                parts = buffer.splitlines(keepends=True)
                new_buffer = ""
                for part in parts:
                    # 若最后一部分没有换行符，说明可能是残缺，留到下轮
                    if not (part.endswith("\n") or part.endswith("\r\n")):
                        new_buffer += part
                        continue

                    line = part.strip()
                    if not line:
                        continue

                    # 有时 SSE 批次里含 "data: {json}" 或直接 json 或 plain text token
                    obj, used_string = safe_json_loads(line)
                    if obj is not None:
                        # 期待后端发送 {"type":"debug"/"token"/...,"data":...}
                        typ = obj.get("type") if isinstance(obj, dict) else None
                        data = obj.get("data") if isinstance(obj, dict) else obj
                        if typ == "debug":
                            pretty_print_debug("node info", data)
                        elif typ == "token":
                            # token 可能是文本片段
                            sys.stdout.write(str(data))
                            sys.stdout.flush()
                            final_answer += str(data)
                        elif typ == "history":
                            pretty_print_debug("history", data)
                        elif typ == "error":
                            pretty_print_debug("error", data)
                        elif typ == "end":
                            print("\n✅ 服务端发来 end")
                            return
                        else:
                            # 如果没有 type 字段，打印整个 obj
                            pretty_print_debug("msg", obj)
                    else:
                        # 不是 JSON：可能是纯文本 token（部分或完整）
                        # 尝试修复 mojibake 并打印
                        fixed = try_fix_mojibake(line)
                        # 最后尝试解析为 '{"type":"token","data":"..."}' 形式（无双引号转义）
                        if fixed.startswith('{') and fixed.endswith('}'):
                            try:
                                j = json.loads(fixed)
                                pretty_print_debug("recovered_json", j)
                                continue
                            except Exception:
                                pass
                        # 否则把它当作 token 输出
                        sys.stdout.write(fixed)
                        sys.stdout.flush()
                        final_answer += fixed

                buffer = new_buffer

            print("\n\n⚠️ 流结束（server 关闭连接或客户端读取完毕）")
            print("\n\n💬 最终回答：\n", final_answer)
    except Exception as e:
        print("❌ 请求失败或读取流时发生异常：", e)

if __name__ == "__main__":
    # RAG 测试
    debug_chat("请总结一下CS101课程的教学大纲内容。")

    # Tool 测试
    debug_chat("谁是CS101课程的老师？")

    # 普通聊天测试
    debug_chat("你好，你能做什么？")
