# backend/chatbot/langgraph_agent/tools/query_rewriter.py

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool

# 导入核心功能和类型定义
from ..core import (
    call_qwen,  # [OK] 保留（向后兼容）
    call_qwen_httpx,  # [OK] 新增异步版本
    ENABLE_VERBOSE_LOGGING, 
    ROUTER_MODEL, 
    create_docs_summary
)
from ..schemas import RetrievedDocument

# --- Pydantic 模型定义 ---
class QueryRewriterArgs(BaseModel):
    """rewrite_query 工具的输入参数"""
    original_query: str = Field(description="用户的原始查询。")
    history: str = Field(default="", description="最近的对话历史摘要。")
    retrieved_docs_summary: str = Field(default="", description="当前已检索到的文档摘要。")
    missing_information: str = Field(description="明确指出当前缺少什么信息，以及期望通过重写查询获得什么。")

# --- 异步工具定义 [OK] ---
@tool(args_schema=QueryRewriterArgs)
async def rewrite_query(**kwargs) -> Dict[str, Any]:  # [OK] async def
    """
    当现有信息不足以回答用户问题时，根据对话历史和已检索的文档，重写一个更具体、更具针对性的新查询，以便进行更有效的检索。
    
    [WARN] 注意：这是异步工具，必须在异步上下文中使用 await 调用。
    """
    try:
        args = QueryRewriterArgs.model_validate(kwargs)
    except Exception as e:
        return {"status": "error", "error": f"参数验证失败: {e}"}

    # 构建 Prompt
    prompt = f"""你是一名检索查询重写器。请将用户的问题改写成"用于检索"的短查询串，而不是一段说明性文字。

要求：
- 只输出"检索关键字"，不要完整句子；不要出现"请/是否/希望/同时/说明/作为"等功能词。
- 必须保留：
  - 已出现的课程代码（如 COMPxxxx）
  - 主题方向关键词（如 人工智能/AI、机器学习、深度学习/神经网络、NLP/自然语言处理、强化学习、安全、数据挖掘/大数据/数据仓库）
  - 学期与限制（如 T1/T2/T3、先修、学分）
- 用空格或 AND/OR 连接关键词；不超过 120 个字符；尽量用中英混合常见词（如 NLP、AI、Deep Learning）。
- 不要输出任何解释、前缀或引号，只输出最终查询串。

【用户原始问题】
{args.original_query}

【对话历史摘要】
{args.history}

【已检索到的信息摘要】
{args.retrieved_docs_summary}

【当前缺少的信息】
{args.missing_information}

请输出最终的检索查询串（仅一行）："""

    messages = [{"role": "user", "content": prompt}]
    
    if ENABLE_VERBOSE_LOGGING:
        print("\n" + "="*30 + " Query Rewriter " + "="*30)
        print(f"   重写目标: {args.missing_information}")

    try:
        # [OK] 使用异步版本
        resp = await call_qwen_httpx(  # [OK] await call_qwen_httpx
            messages,
            model=ROUTER_MODEL,
            temperature=0.5,
            stream=False,
            purpose="query_rewriting"
        )
        
        rewritten_query = (resp.get("content", "") if isinstance(resp, dict) else str(resp)).strip()

        if ENABLE_VERBOSE_LOGGING:
            print(f"  [Result] 重写后的查询: {rewritten_query}")
        
        # 返回结构化的结果
        return {
            "status": "ok",
            "result": {
                "original_query": args.original_query,
                "rewritten_query": rewritten_query,
                "reason": args.missing_information,
            }
        }
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"  [ERR] 查询重写失败: {e}")
        return {"status": "error", "error": f"查询重写时发生错误: {e}"}