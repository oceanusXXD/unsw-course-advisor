# tools/fetch_url.py
import requests
import json
from typing import Dict, Any

def fetch_url(url: str, timeout: int = 8) -> str:
    """
    简单抓取 URL 文本内容（用于工具示例）。
    返回 JSON 字符串包含 status_code, text(前2000字符)。
    注意：生产使用需更严格的安全策略（超时、白名单等）。
    """
    try:
        r = requests.get(url, timeout=timeout)
        text = r.text[:2000]
        return json.dumps({"url": url, "status_code": r.status_code, "text": text}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"url": url, "error": str(e)}, ensure_ascii=False)
