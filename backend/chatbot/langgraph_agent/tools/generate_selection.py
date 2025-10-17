from typing import Dict, Any
import random
import json

def generate_selection() -> str:
    """
    生成选课结果并立即加密：
    - 生成选课数据（dict）
    - 延迟导入 node_crypto 并调用（传入 state={"data": selection_result}）
    - 返回 JSON 字符串：{"data": selection_result, "encrypted": <node_crypto 返回值>}
    注意：返回值为字符串（方便作为 Tool 的输出），上游可 json.loads() 解析。
    """
    # 1) 生成选课数据
    selected = [{"course_code": f"COMP{random.randint(5000, 9000)}"} for _ in range(6)]
    selection_result = {
        "selected": selected,
        "meta": {
            "generated_by": "generate_selection",
        }
    }
    print("⚙️ [node_generate_selection] selection_result:", selection_result)

    # 2) 延迟导入并调用加密函数（避免导入阶段的循环/包问题）
    try:
        # 如果 crypto 在同一包中，使用相对导入（函数内延迟导入更安全）
        from .crypto import node_crypto
    except Exception as e:
        # 导入失败：返回未加密的数据并说明错误
        err = f"ImportError when importing node_crypto: {e}"
        print("⚠️", err)
        return json.dumps({
            "data": selection_result,
            "encrypted": {"error": err}
        }, ensure_ascii=False, indent=2)

    # 3) 调用 node_crypto（node_crypto 期望 state 包含 "data"）
    try:
        state = {"data": selection_result}
        enc_result = node_crypto(state)  # 通常返回 {"url": "..."} 或 {"error": "..."}
    except Exception as e:
        # node_crypto 执行过程中出错：记录并返回
        err = f"Error while running node_crypto: {e}"
        print("⚠️", err)
        enc_result = {"error": err}

    # 4) 返回最终 JSON（字符串）
    output = {
        "data": selection_result,
        "encrypted": enc_result
    }
    return json.dumps(output, ensure_ascii=False, indent=2)
