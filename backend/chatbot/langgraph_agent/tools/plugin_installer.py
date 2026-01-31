"""
固定插件安装工具实现（GET请求版）
"""

import requests
from typing import Dict, Any
from langchain_core.tools import tool, BaseTool
@tool
def plugin_install() -> Dict[str, Any]:
    """
    通过GET请求安装预定义的固定插件
    
    返回:
        dict: 安装结果信息
    """
    try:
        
        # 调用后端API（GET请求）
        api_url = "http://localhost:8000/api/extension/start-extension/"
        response = requests.get(
            api_url,
            params={"action": "install_fixed"},  # 添加GET参数
            headers={"Accept": "application/json"}
        )

        # 处理响应
        if response.status_code == 200:
            return {
                "status": "success",
                "message": "固定插件安装成功",
                "details": response.json()
            }
        else:
            return {
                "status": "error",
                "message": f"后端返回错误 (HTTP {response.status_code}): {response.text}",
                "status_code": response.status_code
            }

    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": f"网络请求失败: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"安装过程中发生意外错误: {str(e)}"
        }