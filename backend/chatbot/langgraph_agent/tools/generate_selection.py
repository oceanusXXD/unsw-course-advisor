# tools/generate_selection.py
import json
import re
from typing import Any, Dict, List, Tuple, Optional

from pydantic import BaseModel, Field
from langchain_core.tools import tool, BaseTool
COURSE_RE = re.compile(r"^[A-Z]{4}\d{4}$")

def _debug(msg: str):
    print(f"[generate_selection] {msg}")

def _normalize_courses(raw: Any) -> List[str]:
    """
    接受多种形式的 courses，统一成 ['COMP1511', 'COMP1521', ...]
    支持:
      - list[str]
      - 逗号/空格分隔的字符串: "COMP1511, COMP1521"
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, str):
        # 用逗号/空白分割
        items = [x.strip() for x in re.split(r"[,\s]+", raw) if x.strip()]
    else:
        return []

    # 规范化、去重、校验
    seen = set()
    out: List[str] = []
    for x in items:
        code = str(x).strip().upper()
        if code and COURSE_RE.match(code) and code not in seen:
            seen.add(code)
            out.append(code)
    return out

def _extract_courses_from_params(params: Dict[str, Any]) -> List[str]:
    """
    从参数字典提取 courses:
      - params['courses']
      - params['args']['courses']
    """
    if not isinstance(params, dict):
        return []
    # 1) 顶层 courses
    if "courses" in params:
        return _normalize_courses(params["courses"])
    # 2) 嵌套 args.courses
    args = params.get("args")
    if isinstance(args, dict) and "courses" in args:
        return _normalize_courses(args["courses"])
    return []

class GenerateSelectionArgs(BaseModel):
    """generate_selection 工具的输入参数"""
    courses: Optional[List[str]] = Field(default=None, description="要生成选课文件的课程代码列表")

@tool(args_schema=GenerateSelectionArgs)    
def generate_selection(args: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """
    生成选课结果并加密（测试版）
    兼容两种调用方式：
      - generate_selection(courses=[...])
      - generate_selection(args={'courses': [...]})
    行为：
      - 若传入 courses（有效代码），则按传入构建选课结果（term=TBD）
      - 若未传入或无有效代码，则回退固定结果
    返回：
      {
        "data": { "selected": [...], "meta": {...} },
        "encrypted": { "url": "...", ... }
      }
    """
    _debug("函数被调用")
    # 兼容 args / kwargs 双入口
    params: Dict[str, Any] = {}
    if isinstance(args, dict):
        params.update(args)
    if kwargs:
        params.update(kwargs)

    _debug(f"接收到的参数: {params}")

    # 解析 courses
    courses = _extract_courses_from_params(params)
    _debug(f"解析后的 courses: {courses}")

    # 构建选课数据
    if courses:
        selected_list = [{"course_code": code, "term": "TBD"} for code in courses]
        selection_result = {
            "selected": selected_list,
            "meta": {
                "mode": "dynamic",
                "generated_by": "generate_selection",
                "count": len(selected_list),
                "note": "selection based on input courses"
            }
        }
    else:
        # 回退到固定数据（保留你的测试输出）
        selection_result = {
            "selected": [
                {"course_code": "GSOE9011", "term": "T1"},
                {"course_code": "COMP9101", "term": "T2"}
            ],
            "meta": {
                "mode": "fixed",
                "generated_by": "generate_selection",
                "note": "Fixed selection results: T1:GSOE9011, T2:COMP9101"
            }
        }
    _debug(f"构建的 selection_result: {selection_result}")

    # 调用加密函数
    try:
        from .crypto import node_crypto
        _debug("成功导入 node_crypto")
    except Exception as e:
        err = f"ImportError when importing node_crypto: {e}"
        _debug(err)
        return {
            "data": selection_result,
            "encrypted": {"error": err}
        }

    try:
        state = {"data": selection_result}
        enc_result = node_crypto(state)  # 期望返回 dict，如 {"url": "..."} 或 {"error": "..."}
        _debug("成功调用 node_crypto")
    except Exception as e:
        err = f"Error while running node_crypto: {e}"
        _debug(err)
        enc_result = {"error": err}

    output = {
        "data": selection_result,
        "encrypted": enc_result
    }
    _debug("执行完成，返回结果")
    return output