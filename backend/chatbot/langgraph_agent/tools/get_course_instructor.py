# tools/get_course_instructor.py
import json
from typing import Dict, Any

def get_course_instructor(course_code: str) -> str:
    """
    示例工具：返回课程讲师信息（模拟 DB）。
    返回 JSON 字符串，兼容原先 tool 返回风格。
    """
    mock_db = {
        "CS101": "Dr. Alan Turing",
        "MATH203": "Prof. Ada Lovelace",
        "PHYS301": "Dr. Marie Curie",
        "ENG100": "Dr. Jane Austen"
    }
    instructor = mock_db.get(course_code.upper(), "未找到该课程的讲师信息")
    return json.dumps({"course_code": course_code, "instructor": instructor}, ensure_ascii=False)
