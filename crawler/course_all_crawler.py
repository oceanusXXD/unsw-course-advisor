# -*- coding: utf-8 -*-
"""
UNSW Handbook 爬虫（多线程版）
- 调用 Courseloop 接口获取课程 URL
- 自动分页直到取完
- 多线程加速每个科目的抓取
"""

import requests
import json
import time
from pathlib import Path
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# 保存结果
os.makedirs("data", exist_ok=True)
filename = "data/AALL_subjects_courses.json"

API_URL = "https://api-ap-southeast-2.prod.courseloop.com/publisher/browsepage-academic-items"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; UNSW-API-Scraper/1.0)",
    "Content-Type": "application/json",
}

STUDY_LEVELS = {
    "undergraduate": "ugrd",
    "postgraduate": "pgrd",
    "research": "rsch"
}


def fetch_one_page(subject, year, level, value, offset=0, limit=50):
    """请求一页数据"""
    payload = {
        "siteId": "unsw-prod-pres",
        "contentType": "subject",
        "limit": limit,
        "offset": offset,
        "queryParams": [
            {"queryField": "educationalArea", "queryValue": subject},
            {"queryField": "implementationYear", "queryValue": year},
            {"queryField": "studyLevel", "queryValue": level},
            {"queryField": "studyLevelValue", "queryValue": value},
        ],
    }

    resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_all_pages(subject, year="2026"):
    """自动翻页抓取本科、研究生、研究型课程"""
    all_data = {}

    for level, value in STUDY_LEVELS.items():
        print(f"[INFO] 抓取 {subject} - {level} ...")
        offset = 0
        limit = 50
        urls = []

        while True:
            data = fetch_one_page(subject, year, level, value, offset, limit)
            items = data.get("data", {}).get("data", {})
            if not items:
                break

            if isinstance(items, list):
                for info in items:
                    url_map = info.get("urlMap")
                    if url_map:
                        urls.append("https://www.handbook.unsw.edu.au" + url_map)

            print(f"{level}: 已获取 {len(urls)} 条 (offset={offset})")
            offset += limit
            time.sleep(0.2)  # 延时

        all_data[level] = urls

    return all_data


def main():
    # ---------------- 1. 从 subject.txt 读取科目列表 ----------------
    subject_file = os.path.join(os.path.dirname(__file__), "subject.txt")

    if not os.path.exists(subject_file):
        print("[ERROR] 未找到 subject.txt，请确保该文件与脚本在同一目录下。")
        exit(1)

    with open(subject_file, "r", encoding="utf-8") as f:
        subjects = [line.strip() for line in f if line.strip()]

    print(f"[INFO] 从 subject.txt 读取到 {len(subjects)} 个科目: {subjects}")

    # ---------------- 2. 多线程抓取 ----------------
    results = {}
    max_workers = min(8, len(subjects))  # 根据科目数量设置线程数
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_subj = {executor.submit(fetch_all_pages, subj): subj for subj in subjects}

        for future in as_completed(future_to_subj):
            subj = future_to_subj[future]
            try:
                data = future.result()
                results[subj] = data
                print(f"{subj}: UG={len(data['undergraduate'])}, "
                      f"PG={len(data['postgraduate'])}, "
                      f"RS={len(data['research'])}")
            except Exception as e:
                print(f"[ERR] {subj} 抓取失败: {e}")

    # ---------------- 3. 保存结果 ----------------
    with open(filename, "w+", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"[DONE] 已保存 {filename}")


if __name__ == "__main__":
    main()
