# -*- coding: utf-8 -*-
"""
compile_and_filter_courses.py（仅编译模块）
位置：unsw-course-advisor/crawler/compile_and_filter_courses.py

功能：
  - 遍历 ../course_detail_data 下所有 *_course_detail.json 文件
  - 对课程条目进行编译（提取 parsed_terms / parsed_prerequisite / parsed_corequisite / parsed_incompatible）
  - 结果保存到 ../compiled_course_data/compiled_data.json（自动创建目录）

运行方式：
  python compile_and_filter_courses.py
"""

import os
import json
import re
from typing import List, Dict, Any, Optional

COURSE_CODE_RE = re.compile(r"\b[A-Z]{4}\d{4}\b")

# -------------------- 工具函数 --------------------
def find_course_files(src_dir: str) -> List[str]:
    """只加载 *_course_detail.json 的课程文件"""
    files = []
    for fname in sorted(os.listdir(src_dir)):
        if fname.endswith("_course_detail.json"):
            full = os.path.join(src_dir, fname)
            files.append(full)
    return files

def normalize_terms(terms_field: Optional[str]) -> List[str]:
    """解析 offering_terms 文字为 ['T1','T2'] 等"""
    if not terms_field:
        return []
    s = terms_field.lower()
    terms = []
    for m in re.finditer(r'term\s*(\d)', s):
        terms.append('T' + m.group(1))
    if 'summer' in s and 't3' not in terms:
        terms.append('T3')
    return sorted(set(terms))

def extract_course_codes(text: str) -> List[str]:
    if not text or not isinstance(text, str):
        return []
    return list(dict.fromkeys(COURSE_CODE_RE.findall(text)))

def simple_requirement_parse(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """启发式解析前置/并修/冲突条件"""
    if not text or not isinstance(text, str):
        return None
    s = text.strip()
    low = s.lower()

    # 不可兼修类
    if any(tok in low for tok in ['incompatible', 'cannot be taken with', 'not available to']):
        codes = extract_course_codes(text)
        if codes:
            return {'op': 'INCOMPATIBLE', 'args': [{'type': 'course', 'code': c} for c in codes]}

    # 并修
    if 'corequisite' in low or 'coreq' in low:
        codes = extract_course_codes(text)
        if codes:
            return {'op': 'COREQ', 'args': [{'type': 'course', 'code': c} for c in codes]}

    # 前置
    if any(tok in low for tok in ['prerequisite', 'must have completed', 'completion of']):
        body = re.sub(r'^[^:]{0,20}:\s*', '', s)
        parts = re.split(r'\band\b', body, flags=re.IGNORECASE)
        args = []
        for part in parts:
            if re.search(r'\bor\b|one of|/', part, flags=re.IGNORECASE):
                codes = extract_course_codes(part)
                if codes:
                    args.append({'op': 'OR', 'args': [{'type': 'course', 'code': c} for c in codes]})
            else:
                codes = extract_course_codes(part)
                if len(codes) == 1:
                    args.append({'type': 'course', 'code': codes[0]})
        if len(args) == 1:
            return args[0]
        elif len(args) > 1:
            return {'op': 'AND', 'args': args}

    codes = extract_course_codes(text)
    if codes:
        return {'op': 'OR', 'args': [{'type': 'course', 'code': c} for c in codes]}
    return None

# -------------------- 编译主流程 --------------------
def compile_course_files(src_dir: str, out_dir: str):
    """编译所有课程文件"""
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "compiled_data.json")

    files = find_course_files(src_dir)
    compiled = []

    for fpath in files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"[WARN] 跳过无法解析的文件 {fpath}: {e}")
            continue

        if not isinstance(data, list):
            continue

        for entry in data:
            if not isinstance(entry, dict):
                continue
            code = entry.get("course_code")
            if not code:
                continue

            parsed_terms = normalize_terms(entry.get("offering_terms") or "")
            prereq = coreq = incompatible = None

            for key in ["additional_enrolment_constraints", "notes", "overview"]:
                txt = entry.get(key)
                if txt:
                    parsed = simple_requirement_parse(txt)
                    if not parsed:
                        continue
                    if parsed.get("op") == "COREQ" and not coreq:
                        coreq = parsed
                    elif parsed.get("op") == "INCOMPATIBLE" and not incompatible:
                        incompatible = parsed
                    elif not prereq:
                        prereq = parsed

            compiled.append({
                "course_code": code,
                "url": entry.get("url", ""),
                "overview": entry.get("overview", ""),
                "offering_terms": entry.get("offering_terms", ""),
                "parsed_terms": parsed_terms,
                "parsed_prerequisite": prereq,
                "parsed_corequisite": coreq,
                "parsed_incompatible": incompatible,
                "raw_entry": entry
            })

    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(compiled, f, ensure_ascii=False, indent=2)

    print(f"[OK] 共编译 {len(compiled)} 门课程，输出文件：{out_file}")

# -------------------- 主函数 --------------------
def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(base_dir, "../course_detail_data")
    out_dir = os.path.join(base_dir, "../compiled_course_data")

    compile_course_files(src_dir, out_dir)

if __name__ == "__main__":
    main()
