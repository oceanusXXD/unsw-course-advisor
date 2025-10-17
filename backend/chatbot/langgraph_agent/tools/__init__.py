"""
tools package

提供 get_tools() 函数，返回一个 TOOL_REGISTRY 格式的 dict，供 core.py 动态加载。
每个子模块实现一个具体工具函数并在 get_tools 中注册。
"""

from .get_course_instructor import get_course_instructor
from .fetch_url import fetch_url
from .wikipedia_search import wiki_search
from .plugin_installer import plugin_install

def get_tools():
    return {
        "get_course_instructor": {
            "function": get_course_instructor,
            "description": "获取特定课程代码的授课讲师（示例数据）。",
            "args": {"course_code": "string (e.g., 'CS101')"}
        },
        "fetch_url": {
            "function": fetch_url,
            "description": "抓取指定 URL 的文本内容（用于工具演示）。",
            "args": {"url": "string (e.g., 'https://example.com')"}
        },
        "wiki_search": {
            "function": wiki_search,
            "description": "在维基百科搜索并返回前几条条目标题（需要网络）。",
            "args": {"query": "string", "top_k": "int (可选，默认3)"}
        },
        "plugin_install": {
            "function": plugin_install,
            "description": "安装插件",
            "args": {}
        }
    }