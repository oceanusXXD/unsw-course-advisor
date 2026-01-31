# unsw-course-advisor\backend\chatbot\langgraph_agent\tools\__init__.py (修复版)
"""
tools package (V15 修复版)

修复内容:
1. 修复 'StructuredTool' object has no attribute 'jso_schema' 的 Bug。
2. 使用 t.name, t.description, 和 t.args_schema.schema() 来正确构建 Schema。
"""
from .generate_selection import generate_selection
from .plugin_installer import plugin_install
from .filter_compiled_courses import filter_compiled_courses
from .knowledge_graph_query import knowledge_graph_search
from pydantic import BaseModel, Field
from langchain_core.tools import tool, BaseTool
from typing import List, Dict, Any, Optional
from .query_rewriter import rewrite_query
# ================================================================
# 1. 路由专用 Schema (保持不变)
# ================================================================
ROUTING_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "vector_retrieve",
            "description": "使用向量检索获取相关文档。适用于：需要课程总览、手册内容、文本证据等广义信息检索的场景。",
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {"type": "string", "description": "为什么要调用向量检索？需要获取什么类型的信息？"}
                },
                "required": ["reasoning"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "continue_retrieve",
            "description": "当前信息不足以完整回答问题，需要继续检索更多信息。注意：只在真正需要更多信息时使用，避免无效检索。",
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {"type": "string", "description": "当前缺少什么关键信息？为什么现有信息不足以回答？"}
                },
                "required": ["reasoning"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "finish_retrieval",
            "description": "已获取足够信息可以回答问题，或已达检索上限，结束检索进入答案生成阶段。",
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {"type": "string", "description": "为什么当前信息已经足够？或者为什么应该结束检索？"}
                },
                "required": ["reasoning"]
            }
        }
    }
]
ROUTER_ONLY_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "retrieve_rag",
            "description": "当用户查询需要访问知识库时（例如课程信息、先修课程、专业要求、RAG检索），调用此路由。",
            "parameters": {
                "type": "object",
                "properties": {"reasoning": {"type": "string"}},
                "required": ["reasoning"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "general_chat",
            "description": "当用户查询是普通聊天、问候或不需要工具或 RAG 时，调用此路由。",
            "parameters": {
                "type": "object",
                "properties": {"reasoning": {"type": "string"}},
                "required": ["reasoning"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "call_tool",
            "description": "当用户查询需要调用特定工具（例如 `generate_selection` 或 `install_plugin`）时，调用此路由。",
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string"},
                    "tool_args": {"type": "object", "additionalProperties": True},
                    "reasoning": {"type": "string"}
                },
                "required": ["tool_name", "tool_args", "reasoning"]
            }
        }
    }
]

# ================================================================
# 2. 工具列表 (保持不变)
# ================================================================
def get_tools() -> List[BaseTool]:
    """
    通用工具注册表 (Pydantic/@tool 重构版)
    返回一个 @tool 对象列表
    """
    return [
        plugin_install,
        generate_selection
    ]

def get_rag_tools() -> List[BaseTool]:
    """
    RAG 专用工具注册表
    返回一个 *可执行* 的 @tool 对象列表
    (供 rag_tool_executor.py 使用)
    """
    return [
        knowledge_graph_search,
        filter_compiled_courses,
        rewrite_query,
    ]

# ================================================================
# 3.  关键修复：修正 Schema 组合函数
# ================================================================
def get_router_schema() -> List[Dict[str, Any]]:
    """
    获取 Router (router.py) 所需的 *完整* 工具 Schema
    """
    
    tools_schema = ROUTER_ONLY_SCHEMA
    
    general_tools_list = get_tools()
    
    for t in general_tools_list:
        tools_schema.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.args_schema.schema()
            }
        })
        
    return tools_schema

def get_agentic_router_schema() -> List[Dict[str, Any]]:
    """
    获取 Agentic Router (agentic_router.py) 所需的 *完整* 工具 Schema
    """
    
    # 1. 从硬编码的路由目标开始
    tools_schema = ROUTING_TOOLS_SCHEMA
    
    # 2. 获取所有可执行的 "RAG" @tool 工具
    rag_tools_list = get_rag_tools()
    
    # 3.  关键修复：使用 t.name, t.description, t.args_schema.schema()
    for t in rag_tools_list:
        tools_schema.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.args_schema.schema() # <- 修复
            }
        })
        
    return tools_schema
    
def get_all_tools() -> List[BaseTool]:
    """
    返回一个包含 *所有* 可执行工具的列表 (通用 + RAG)。
    供统一的 tool_executor 节点使用。
    """
    return get_tools() + get_rag_tools()