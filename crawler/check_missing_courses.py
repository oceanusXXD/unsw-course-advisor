#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UNSW Handbook 课程详情完整性检查脚本
------------------------------------
功能：
1. 对比 ./data/AALL_subjects_courses.json 与 ./data/{subject}_course_detail.json
2. 检查每个学科的课程代码是否齐全
3. 若有缺失，打印缺失课程代码并可自动调用 course_detail_crawler.py 重新爬取
"""

import os
import re
import json
import subprocess
from typing import Dict, List, Set

DATA_DIR = "./data"
ALL_SUBJECTS_FILE = os.path.join(DATA_DIR, "AALL_subjects_courses.json")
CRAWLER_SCRIPT = "./course_detail_crawler.py"
LEVEL_ORDER = ["undergraduate", "postgraduate", "research"]

def extract_course_code(url: str) -> str:
    """从课程URL提取课程代码，例如 /courses/2026/ACCT2101 -> ACCT2101"""
    m = re.search(r"/courses/\d{4}/([A-Z]{2,5}\d{3,4})", url)
    return m.group(1).upper() if m else None # type: ignore

def load_all_subjects_courses(path: str) -> Dict[str, Dict[str, List[str]]]:
    """加载 AALL_subjects_courses.json"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到文件: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def load_detail_codes(subject: str) -> Set[str]:
    """读取 ./data/{subject}_course_detail.json 内的课程代码集合"""
    path = os.path.join(DATA_DIR, f"{subject}_course_detail.json")
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            items = json.load(f)
        return {i.get("course_code", "").upper() for i in items if i.get("course_code")}
    except Exception as e:
        print(f"[WARN] 读取 {path} 失败：{e}")
        return set()

def get_expected_codes(subj_data: Dict[str, List[str]]) -> Set[str]:
    """从 AALL_subjects_courses.json 获取该学科的全部课程代码"""
    codes = set()
    for lvl in LEVEL_ORDER:
        urls = subj_data.get(lvl, [])
        for url in urls:
            code = extract_course_code(url)
            if code:
                codes.add(code)
    return codes

def check_subject_integrity(subject: str, subj_data: Dict[str, List[str]]):
    """对比一个学科的应有课程与已爬取课程"""
    expected_codes = get_expected_codes(subj_data)
    existing_codes = load_detail_codes(subject)
    missing = sorted(expected_codes - existing_codes)
    extra = sorted(existing_codes - expected_codes)
    return missing, extra

def main(auto_refetch: bool = True):
    all_data = load_all_subjects_courses(ALL_SUBJECTS_FILE)
    subjects = sorted(all_data.keys())
    total_missing = 0
    summary = {}

    print(f"[INFO] 检查 {len(subjects)} 个学科的课程详情完整性...\n")

    for subj in subjects:
        subj_data = all_data[subj]
        missing, extra = check_subject_integrity(subj, subj_data)

        if missing or extra:
            print(f"[WARN] {subj} 数据异常：")
            if missing:
                print(f"  [X] 缺失 {len(missing)} 门课程：{missing}")
                total_missing += len(missing)
            if extra:
                print(f"  [WARN] 多余 {len(extra)} 门课程（可能旧数据未清理）：{extra}")
            summary[subj] = {"missing": missing, "extra": extra}
        else:
            print(f"{subj} 完整")

    if total_missing == 0:
        print("\n[DONE] 所有学科课程详情均完整无缺！")
        return

    print(f"\n[SUMMARY] 共发现 {total_missing} 门课程缺失。")

    if auto_refetch:
        print("\n[INFO] 启动自动补抓任务（运行 course_detail_crawler.py）...")
        try:
            subprocess.run(["python", CRAWLER_SCRIPT], check=False)
        except Exception as e:
            print(f"[ERROR] 调用爬虫脚本失败：{e}")
    else:
        print("\n[NOTE] 未启用自动补抓，请手动运行：")
        print(f"python {CRAWLER_SCRIPT}")

if __name__ == "__main__":
    # auto_refetch=True 表示发现缺失时自动重新运行爬虫脚本
    main(auto_refetch=True)
