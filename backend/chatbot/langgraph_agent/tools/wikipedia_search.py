# tools/wikipedia_search.py
import requests
import json
from typing import List

def wiki_search(query: str, top_k: int = 3) -> str:
    """
    基于维基搜索返回标题列表（需要网络）。若在内网可使用模拟返回。
    """
    try:
        S = requests.Session()
        URL = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": top_k
        }
        r = S.get(URL, params=params, timeout=6)
        data = r.json()
        hits = data.get("query", {}).get("search", [])
        titles = [h["title"] for h in hits]
        return json.dumps({"query": query, "titles": titles}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"query": query, "error": str(e)}, ensure_ascii=False)
