import requests
from bs4 import BeautifulSoup
import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import re

# ================== 配置 ==================
MAX_WORKERS = 3
MIN_DELAY = 0.8
MAX_DELAY = 3.2
MAX_RETRY = 6
BACKOFF_BASE = 2.0
FORBIDDEN_WAIT_MIN = 6.0
FORBIDDEN_WAIT_MAX = 14.0

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/120.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

BASE_URL_TEMPLATE = "https://www.handbook.unsw.edu.au/undergraduate/specialisations/2026/{}"
SUBJECT_LIST_FILE = "./subject1.txt"

OUTPUT_DIR = "../graduation_requests_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)
SAVE_PAGECONTENT_TO_FILE = True  # 是否把 pageContent 单独保存
# ==========================================

def random_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

def safe_get(url: str, session: requests.Session) -> str | None:
    """带重试和指数退避的 GET 请求"""
    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = session.get(url, headers=random_headers(), timeout=20)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 403:
                wait = random.uniform(FORBIDDEN_WAIT_MIN, FORBIDDEN_WAIT_MAX)
                print(f"[403] {url} 被拒绝，等待 {wait:.1f}s (尝试 {attempt}/{MAX_RETRY})")
                time.sleep(wait)
            elif 500 <= resp.status_code < 600:
                backoff = (BACKOFF_BASE ** attempt) + random.uniform(0, 1)
                print(f"[{resp.status_code}] 服务器错误，等待 {backoff:.1f}s (尝试 {attempt}/{MAX_RETRY})")
                time.sleep(backoff)
            else:
                print(f"[{resp.status_code}] 非预期状态码，跳过 {url}")
                return None
        except requests.RequestException as e:
            backoff = (BACKOFF_BASE ** attempt) + random.uniform(0, 1)
            print(f"[Err] 请求异常 {e}，等待 {backoff:.1f}s (尝试 {attempt}/{MAX_RETRY})")
            time.sleep(backoff)
    print(f"[ERR] 最大重试次数到达，放弃 {url}")
    return None

def extract_next_data_from_html(html_text: str):
    """解析 __NEXT_DATA__ JSON"""
    # 方式1：<script id="__NEXT_DATA__">...</script>
    m = re.search(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html_text, flags=re.S|re.I)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # 方式2：window.__NEXT_DATA__ = {...};
    m2 = re.search(r'window\.__NEXT_DATA__\s*=\s*(\{.*?\})\s*;', html_text, flags=re.S)
    if m2:
        try:
            return json.loads(m2.group(1))
        except Exception:
            pass
    return None

def save_pagecontent(code: str, page_content):
    """保存 pageContent 到单独 JSON 文件"""
    safe_name = code.replace("/", "_")
    out_path = os.path.join(OUTPUT_DIR, f"{safe_name}_pageContent.json")
    with open(out_path, "w", encoding="utf-8") as wf:
        json.dump(page_content, wf, ensure_ascii=False, indent=2)
    return out_path

def fetch_div(code: str, session: requests.Session):
    url = BASE_URL_TEMPLATE.format(code)
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY) * 0.3)

    html_text = safe_get(url, session)
    if not html_text:
        return {"url": url, "success": False, "error": "无法获取页面 HTML"}

    next_data = extract_next_data_from_html(html_text)
    if not next_data:
        return {"url": url, "success": False, "error": "__NEXT_DATA__ 未找到"}

    try:
        page_content = next_data["props"]["pageProps"]["pageContent"]
    except KeyError:
        return {"url": url, "success": False, "error": "未找到 props.pageProps.pageContent"}

    if SAVE_PAGECONTENT_TO_FILE:
        save_pagecontent(code, page_content)

    return {"url": url, "success": True, "code": code, "pageContent": page_content}

def main():
    # 读取课程号
    with open(SUBJECT_LIST_FILE, "r", encoding="utf-8") as f:
        codes = [line.strip() for line in f if line.strip()]

    results = []
    session = requests.Session()

    print(f"开始抓取 {len(codes)} 个课程（并发 {MAX_WORKERS}）")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        future_to_code = {exe.submit(fetch_div, code, session): code for code in codes}
        for future in tqdm(as_completed(future_to_code), total=len(future_to_code)):
            code = future_to_code[future]
            try:
                res = future.result()
            except Exception as e:
                res = {"url": BASE_URL_TEMPLATE.format(code), "success": False, "error": str(e)}
            results.append(res)

    # 保存总结果
    summary_file = os.path.join(OUTPUT_DIR, "parsed_results_summary.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    succ = sum(1 for r in results if r.get("success"))
    print(f"抓取完成，共 {len(results)} 条，成功 {succ} 条。结果已保存到 {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
