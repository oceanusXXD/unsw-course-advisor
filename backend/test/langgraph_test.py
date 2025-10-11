# langgraph_test.py
# -*- coding: utf-8 -*-
"""
调试 LangGraph + RAG 的脚本（更健壮的 run_chat 调用）
放在 backend/ 目录下运行（确保 backend 在 PYTHONPATH 中，或者直接在 backend 目录执行）
示例：
    python langgraph_test.py --query "CHEM3041课程内容是什么？" --topk 8 --show-prompt
    python langgraph_test.py --query "CHEM3041课程内容是什么？" --stream
"""

import os
import sys
import json
import time
import argparse
import traceback
from pathlib import Path
from dotenv import load_dotenv  # type: ignore

# ---------- 配置脚本路径（保证能导入 chatbot 包） ----------
HERE = Path(__file__).resolve().parent
print("当前目录:", HERE)
BACKEND_DIR = HERE.parent  # 假定 backend 位于上一级目录
print("backend 目录:", BACKEND_DIR)
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# 自动加载 .env（如果存在）
load_dotenv(dotenv_path=BACKEND_DIR / ".env")  # 会静默失败如果没有 .env

# ---------- 导入项目模块 ----------
try:
    import chatbot.rag_chain_qwen as rag
    import chatbot.langgraph_integration as langgraph
except Exception:
    # 打印导入错误并退出，提示用户检查路径
    print("无法导入 chatbot 模块。确保你在 backend/ 目录运行此脚本，或调整 sys.path。")
    traceback.print_exc()
    sys.exit(1)

# ---------- CLI 参数 ----------
parser = argparse.ArgumentParser(description="Test LangGraph + RAG integration (robust)")
parser.add_argument("--query", "-q", type=str, required=True, help="要测试的用户问题（中文）")
parser.add_argument("--topk", "-k", type=int, default=4, help="检索 top_k 文档")
parser.add_argument("--show-prompt", action="store_true", help="打印构造好的 prompt（供调试）")
parser.add_argument("--stream", action="store_true", help="是否使用流式调用模型（调试实时输出）")
parser.add_argument("--api-key", type=str, default=None, help="临时传入 API Key（优先于环境变量）")
args = parser.parse_args()

# ---------- 简单本地序列化 helpers（与 views 中格式一致） ----------
def serialize_docs_for_debug(docs):
    out = []
    for d in docs:
        # d 可能是 dict 或自定义对象，尽量安全取字段
        try:
            code = d.get("course_code") or d.get("CourseCode") or d.get("assoc_code") or ""
        except Exception:
            code = ""
        try:
            source_file = d.get("source_file") or d.get("source") or "unknown"
        except Exception:
            source_file = "unknown"
        try:
            score = d.get("_score", None)
            score = float(score) if score is not None else None
        except Exception:
            score = None
        try:
            preview = (d.get("_content") or d.get("_text") or d.get("content") or d.get("overview") or "")[:400]
        except Exception:
            preview = ""
        out.append({
            "course_code": code,
            "source_file": source_file,
            "score": score,
            "preview": preview
        })
    return out

# ---------- 检查 API Key ----------
api_key = args.api_key or os.getenv("DASHSCOPE_API_KEY")
if not api_key:
    print("警告：未检测到 DASHSCOPE_API_KEY（环境变量或 --api-key）。调用模型会失败（如果需要认证）。")
else:
    print("使用 API Key（已检测）。")

# ---------- 主测试流程 ----------
query = args.query.strip()
print(f"\n=== 测试开始 ({time.strftime('%Y-%m-%d %H:%M:%S')}) ===")
print("Query:", query)
print("Top-K:", args.topk)
print("使用流式:", args.stream)
print()

# helper: 尝试安全地 dump state snippet
def _state_snippet(state, length=2000):
    try:
        return json.dumps(state, ensure_ascii=False, default=str)[:length]
    except Exception:
        try:
            return str(state)[:length]
        except Exception:
            return "<无法序列化 state>"

# 1) 用 LangGraph run_chat（尝试多种调用/传参方式，增加兼容性）
try:
    if hasattr(langgraph, "run_chat"):
        print("调用 langgraph.run_chat() ...")
        start = time.time()
        state = None
        attempts = []
        # 我们按优先顺序尝试：dict 包装 -> 原始字符串 -> keyword arg 'input'
        try:
            attempts.append("run_chat({'query': query})")
            state = langgraph.run_chat(query)
        except Exception as e1:
            print(f"尝试 run_chat({'{'}'query': query{'}'}) 失败: {e1}")
            traceback.print_exc()
            try:
                attempts.append("run_chat(query)")
                state = langgraph.run_chat(query)
            except Exception as e2:
                print(f"尝试 run_chat(query) 也失败: {e2}")
                traceback.print_exc()
                try:
                    attempts.append("run_chat(input=query)")
                    # 有些实现可能支持关键字参数
                    state = langgraph.run_chat(query=query)
                except Exception as e3:
                    print("所有对 run_chat 的尝试均失败，下面抛出最后的异常以便定位。")
                    traceback.print_exc()
                    raise

        elapsed = time.time() - start
        print(f"LangGraph 完成（耗时 {elapsed:.2f}s，尝试方式：{attempts}）")
        # 打印 state 关键字段（尽量兼容）
        print("\n--- 返回 state 简要 ---")
        try:
            ans = None
            # 常见字段
            if isinstance(state, dict):
                ans = state.get("answer") or state.get("answer_text") or state.get("output") or state.get("result") or None
            elif isinstance(state, str):
                ans = state
            else:
                # 如果为自定义对象，尝试取属性
                ans = getattr(state, "answer", None) or getattr(state, "answer_text", None) or None
            print("Answer:", ans)
        except Exception:
            print("读取 answer 时出错，state snippet:", _state_snippet(state))

        # 优先打印 sources_brief 或 retrieved
        try:
            if isinstance(state, dict) and state.get("sources_brief"):
                print("Sources (sources_brief):")
                print(json.dumps(state.get("sources_brief"), ensure_ascii=False, indent=2, default=str))
            else:
                retrieved = None
                if isinstance(state, dict):
                    retrieved = state.get("retrieved", None) or state.get("documents", None) or state.get("sources", None)
                # 如果 retrieved 是可迭代则展示计数和序列化预览
                if retrieved:
                    try:
                        docs_list = list(retrieved)
                        print("Retrieved count:", len(docs_list))
                        print(json.dumps(serialize_docs_for_debug(docs_list), ensure_ascii=False, indent=2))
                    except Exception:
                        print("无法序列化 retrieved，state snippet:", _state_snippet(state))
                else:
                    print("未在 state 中找到 sources_brief/retrieved 字段，state snippet:")
                    print(_state_snippet(state))
        except Exception:
            print("打印 state 来源时出错，state snippet:")
            print(_state_snippet(state))
    else:
        print("langgraph.run_chat 不存在，跳过 LangGraph 调用。")
except Exception:
    print("调用 langgraph.run_chat 时出现未捕获异常（见下方 traceback）：")
    traceback.print_exc()
    print("提示：如果错误与 'KeyError: \"query\"' 相关，说明 LangGraph 流程中某个 node 期望 state 包含 'query' 字段。")
    print("解决办法：1) 在 langgraph_integration.node_generate 中增强对 state 形态的兼容性；2) 或在构造 state 时确保包含 'query' 字段。")

# 2) 单独运行 RAG 检索（查看是否能命中目标课程）
try:
    print("\n=== 单独检索（rag.retrieve）调试 ===")
    docs = rag.retrieve(query, top_k=args.topk)
    # docs 可能为 list 或可迭代对象
    docs_list = list(docs) if docs is not None else []
    print("检索到文档数量:", len(docs_list))
    print(json.dumps(serialize_docs_for_debug(docs_list), ensure_ascii=False, indent=2))
except Exception:
    print("调用 rag.retrieve 出现错误：")
    traceback.print_exc()

# 3) 如果要求打印 prompt，构造并输出
if args.show_prompt:
    try:
        print("\n=== 构造 Prompt（供调试） ===")
        # 如果上面 docs 可用，优先使用；否则传空列表
        try:
            docs_used = docs_list
        except NameError:
            docs_used = []
        prompt = rag.build_prompt(query, docs_used)
        # 只打印前 4000 字以免太长
        print(prompt[:4000])
        if len(prompt) > 4000:
            print("\n...[prompt truncated]...")
    except Exception:
        print("构造 prompt 失败：")
        traceback.print_exc()

# 4) 调用模型生成（非流式或流式）
if args.stream:
    print("\n=== 流式调用模型（rag.answer_with_rag stream=True） ===")
    try:
        gen = rag.answer_with_rag(query, top_k=args.topk, stream=True, api_key=api_key, base_url=None, temperature=0.0)
        print("开始逐片输出模型流（可能会比较慢）:")
        for chunk in gen:
            # chunk 可能包含小段文本
            try:
                # 有的 generator 直接 yield 字符串，有的 yield dict
                if isinstance(chunk, dict):
                    sys.stdout.write(chunk.get("text", "") or chunk.get("output", "") or str(chunk))
                else:
                    sys.stdout.write(str(chunk))
                sys.stdout.flush()
            except Exception:
                # 若写 stdout 失败，直接 print
                print(chunk, end="", flush=True)
        print("\n\n=== 流式输出结束 ===")
    except Exception:
        print("流式调用失败：")
        traceback.print_exc()
else:
    print("\n=== 非流式调用模型（rag.answer_with_rag stream=False） ===")
    try:
        answer, docs2 = rag.answer_with_rag(query, top_k=args.topk, stream=False, api_key=api_key, base_url=None, temperature=0.0)
        print("\n模型完整回答：")
        print(answer)
        print("\n模型使用的来源（序列化）：")
        try:
            docs2_list = list(docs2)
        except Exception:
            docs2_list = docs2 or []
        print(json.dumps(serialize_docs_for_debug(docs2_list), ensure_ascii=False, indent=2))
    except Exception:
        print("非流式调用失败：")
        traceback.print_exc()

print("\n=== 测试结束 ===")
