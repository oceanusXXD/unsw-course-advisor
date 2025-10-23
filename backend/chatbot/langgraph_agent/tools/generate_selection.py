# tools/generate_selection.py
from typing import Dict, Any
import json

def generate_selection() -> str:
    """
    生成固定的选课结果并立即加密：
    - 固定返回: T1:GSOE9011, T2:COMP9101
    - 延迟导入 node_crypto 并调用（传入 state={"data": selection_result}）
    - 返回 JSON 字符串：{"data": selection_result, "encrypted": <node_crypto 返回值>}
    """
    # 1) 生成固定的选课数据
    selection_result = {
        "selected": [
            {"course_code": "GSOE9011", "term": "T1"},
            {"course_code": "COMP9101", "term": "T2"}
        ],
        "meta": {
            "generated_by": "generate_selection",
            "note": "Fixed selection results: T1:GSOE9011, T2:COMP9101"
        }
    }
    print("⚙️ [node_generate_selection] selection_result:", selection_result)

    # 2) 延迟导入并调用加密函数
    try:
        from .crypto import node_crypto
    except Exception as e:
        err = f"ImportError when importing node_crypto: {e}"
        print("⚠️", err)
        return json.dumps({
            "data": selection_result,
            "encrypted": {"error": err}
        }, ensure_ascii=False, indent=2)

    # 3) 调用 node_crypto
    try:
        state = {"data": selection_result}
        enc_result = node_crypto(state)
    except Exception as e:
        err = f"Error while running node_crypto: {e}"
        print("⚠️", err)
        enc_result = {"error": err}

    # 4) 返回最终 JSON（字符串）
    output = {
        "data": selection_result,
        "encrypted": enc_result
    }
    return json.dumps(output, ensure_ascii=False, indent=2)
