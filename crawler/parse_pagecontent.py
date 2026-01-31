# parse_pagecontent.py
import os
import json
import csv
from bs4 import BeautifulSoup
import glob

# ========== 配置 ==========
INPUT_DIR = "../graduation_requests_data"   # 存放 *_pageContent.json 的目录
OUTPUT_DIR = "../parsed_graduation_requests_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 匹配哪些 JSON 文件；默认取目录下所有 .json
JSON_GLOB = os.path.join(INPUT_DIR, "*.json")
# ==========================


def html_to_text(html_str):
    if not html_str:
        return ""
    try:
        return BeautifulSoup(html_str, "html.parser").get_text(separator="\n").strip()
    except Exception:
        return str(html_str).strip()


def safe_get(dct, *keys, default=""):
    cur = dct
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur if cur is not None else default


def parse_program(data, source_fname=""):
    rec = {}
    rec["source_file"] = source_fname
    rec["title"] = data.get("title", "")
    rec["code"] = data.get("code", "") or data.get("cl_code", "")
    rec["short_title"] = data.get("short_title", "")
    rec["description"] = data.get("description", "")
    rec["html_description"] = html_to_text(data.get("html_description", ""))
    rec["structure_summary"] = html_to_text(data.get("structure_summary", ""))
    rec["credit_points"] = data.get("credit_points", "")
    rec["credit_points_header"] = data.get("credit_points_header", "")
    rec["implementation_year"] = data.get("implementation_year", "")
    rec["status"] = safe_get(data, "status", "label")
    # study_level 可能是 list 或单个结构
    if isinstance(data.get("study_level"), list):
        rec["study_level"] = ", ".join([s.get("label", "") for s in data.get("study_level", [])])
    else:
        rec["study_level"] = safe_get(data, "study_level_single", "label") or safe_get(data, "study_level", "label")
    rec["english_requirement"] = safe_get(data, "english_language_requirements", "value")
    rec["university"] = data.get("university", "")
    rec["keywords"] = data.get("keywords", "")
    rec["additional_notes"] = data.get("additional_notes", "")
    return rec


def parse_courses(data, program_code="", source_fname=""):
    courses = []
    cs = data.get("curriculumStructure", {}) or {}
    containers = cs.get("container", []) if isinstance(cs.get("container", []), list) else []
    # 兼容性：有时 container 可能在 curriculum_structure 下
    if not containers:
        maybe = cs.get("curriculum_structure", {}) or {}
        if isinstance(maybe.get("container", []), list):
            containers = maybe.get("container", [])

    for container in containers:
        container_title = container.get("title", "") or (container.get("vertical_grouping") or {}).get("label", "")
        container_desc = container.get("description", "") or ""
        rels = container.get("relationship", []) or []
        for rel in rels:
            code = rel.get("academic_item_code") or safe_get(rel, "child_record", "value") or ""
            # 解析 "Course: CODE" 形式
            if isinstance(code, str) and code.startswith("Course:"):
                parts = code.split(":", 1)
                if len(parts) >= 2:
                    code = parts[1].strip()
            name = rel.get("academic_item_name") or rel.get("academic_item_version_name") or ""
            item_url = rel.get("academic_item_url") or ""
            item_credit = rel.get("academic_item_credit_points") or rel.get("credit_points") or ""
            order = rel.get("order", "")
            # 再次尝试 child_record.key
            if not code:
                cr = rel.get("child_record", {}) or {}
                code = cr.get("key", "") or cr.get("value", "")
                if isinstance(code, str) and code.startswith("Course:"):
                    code = code.split(":", 1)[1].strip()
            courses.append({
                "program_code": program_code,
                "source_file": source_fname,
                "container_title": container_title,
                "container_description": html_to_text(container_desc),
                "course_code": code,
                "course_name": name,
                "course_url": item_url,
                "course_credit_points": item_credit,
                "order": order
            })
    return courses


def parse_learning_outcomes(data, program_code="", source_fname=""):
    los = []
    for lo in data.get("learning_outcomes", []) or []:
        los.append({
            "program_code": program_code,
            "source_file": source_fname,
            "lo_code": lo.get("code", ""),
            "number": lo.get("number", ""),
            "description": lo.get("description", ""),
            "order": lo.get("order", "")
        })
    return los


def main():
    files = glob.glob(JSON_GLOB)
    if not files:
        print(f"没有找到任何 JSON 文件（路径模式：{JSON_GLOB}），请确认输入目录和文件名。")
        return

    programs_rows = []
    courses_rows = []
    lo_rows = []
    cleaned_all = []

    for fpath in files:
        fname = os.path.basename(fpath)
        try:
            with open(fpath, "r", encoding="utf-8") as fr:
                data = json.load(fr)
        except Exception as e:
            print(f"[跳过] 无法解析 {fname}: {e}")
            continue

        # 处理多种顶层情况：dict（可能含 pageContent）或 list（多个条目）
        items = []
        if isinstance(data, dict):
            # 如果顶层包含 pageContent 字段（可能是 dict 或 list）
            if "pageContent" in data:
                pc = data["pageContent"]
                if isinstance(pc, list):
                    items = pc
                elif isinstance(pc, dict):
                    items = [pc]
                else:
                    # 非常规类型，跳过
                    print(f"[警告] {fname} 的 pageContent 不是 dict/list，跳过该文件")
                    items = []
            else:
                # 把顶层 dict 当作单个 program
                items = [data]
        elif isinstance(data, list):
            # 顶层就是 list，直接把每个元素当作一个 program/条目
            items = data
        else:
            print(f"[跳过] {fname} 顶层既不是 dict 也不是 list，类型：{type(data)}")
            continue

        # items 现在是一个程序条目列表（可能只有一个）
        for idx, content in enumerate(items):
            if not isinstance(content, dict):
                print(f"[跳过] {fname} 中第 {idx} 项不是 dict，类型：{type(content)}")
                continue

            # 用带索引的 source 名，避免同一文件多条目冲突
            source_name = f"{fname}#{idx}" if len(items) > 1 else fname
            program_code = content.get("code", "") or content.get("cl_code", "") or content.get("search_title", "")

            prog = parse_program(content, source_fname=source_name)
            programs_rows.append(prog)

            courses = parse_courses(content, program_code=program_code, source_fname=source_name)
            courses_rows.extend(courses)

            los = parse_learning_outcomes(content, program_code=program_code, source_fname=source_name)
            lo_rows.extend(los)

            cleaned_all.append({
                "source_file": source_name,
                "program_summary": prog,
                "courses": courses,
                "learning_outcomes": los
            })

    # 写 CSV：programs_summary.csv
    programs_csv = os.path.join(OUTPUT_DIR, "programs_summary.csv")
    with open(programs_csv, "w", newline="", encoding="utf-8-sig") as wf:
        fieldnames = ["source_file", "code", "title", "short_title", "description", "html_description", "structure_summary", "credit_points", "credit_points_header", "implementation_year", "status", "study_level", "english_requirement", "university", "keywords", "additional_notes"]
        writer = csv.DictWriter(wf, fieldnames=fieldnames)
        writer.writeheader()
        for r in programs_rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    # 写 CSV：courses.csv
    courses_csv = os.path.join(OUTPUT_DIR, "courses.csv")
    with open(courses_csv, "w", newline="", encoding="utf-8-sig") as wf:
        fieldnames = ["source_file", "program_code", "container_title", "container_description", "course_code", "course_name", "course_credit_points", "course_url", "order"]
        writer = csv.DictWriter(wf, fieldnames=fieldnames)
        writer.writeheader()
        for r in courses_rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    # 写 CSV：learning_outcomes.csv
    los_csv = os.path.join(OUTPUT_DIR, "learning_outcomes.csv")
    with open(los_csv, "w", newline="", encoding="utf-8-sig") as wf:
        fieldnames = ["source_file", "program_code", "lo_code", "number", "description", "order"]
        writer = csv.DictWriter(wf, fieldnames=fieldnames)
        writer.writeheader()
        for r in lo_rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})

    # 写合并 JSON 备份
    cleaned_json = os.path.join(OUTPUT_DIR, "cleaned_all.json")
    with open(cleaned_json, "w", encoding="utf-8") as wf:
        json.dump(cleaned_all, wf, ensure_ascii=False, indent=2)

    print("解析完成：")
    print(f"  programs_summary -> {programs_csv}")
    print(f"  courses -> {courses_csv}")
    print(f"  learning_outcomes -> {los_csv}")
    print(f"  cleaned_all.json -> {cleaned_json}")
    print(f"共处理 {len(cleaned_all)} 个条目，提取课程条目 {len(courses_rows)}，学习成果 {len(lo_rows)}。")


if __name__ == "__main__":
    main()
