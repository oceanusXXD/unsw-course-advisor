# tools/__init__.py
"""
tools package

提供 get_tools() 函数，返回一个 TOOL_REGISTRY 格式的 dict，供 core.py 动态加载。
每个子模块实现一个具体工具函数并在 get_tools 中注册。
"""

from .get_course_instructor import get_course_instructor
from .calc import safe_calc
from .fetch_url import fetch_url
from .time_tools import current_time
from .wikipedia_search import wiki_search

def get_tools():
    return {
        "get_course_instructor": {
            "function": get_course_instructor,
            "description": "获取特定课程代码的授课讲师（示例数据）。",
            "args": {"course_code": "string (e.g., 'CS101')"}
        },
        "calc": {
            "function": safe_calc,
            "description": "安全计算器：计算简单的算术表达式（+ - * / // % ** 和括号）。",
            "args": {"expression": "string (e.g., '2+2*3')"}
        },
        "fetch_url": {
            "function": fetch_url,
            "description": "抓取指定 URL 的文本内容（用于工具演示）。",
            "args": {"url": "string (e.g., 'https://example.com')"}
        },
        "current_time": {
            "function": current_time,
            "description": "返回服务器当前时间（ISO 格式）及时区信息。",
            "args": {}
        },
        "wiki_search": {
            "function": wiki_search,
            "description": "在维基百科搜索并返回前几条条目标题（需要网络）。",
            "args": {"query": "string", "top_k": "int (可选，默认3)"}
        }
    }
