from bs4 import BeautifulSoup
import json
import glob
import re
import os

# 匹配 course_id 并解析 termcode/term/section
# pattern: <prefix><termcode(4digits)>T<termnum(1digit)><section(1digit)>
RE_COURSE = re.compile(r'^(?P<prefix>\d+?)(?P<termcode>\d{4})T(?P<termnum>\d)(?P<section>\d)$')

html_files = sorted(glob.glob("./search*.html"))

if not html_files:
    print("未找到任何 search*.html 文件")
    exit(1)

course_map = {}  # 结构: { "ACCT5910": [ {course_id:..., termcode:..., term: "T1", section:...}, ... ] }

for file_path in html_files:
    print(f"[Doc] 解析文件: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table tbody tr")

    for row in rows:
        code_cell = row.select_one("td:nth-child(1)")
        input_tag = row.select_one('input[name="courses[]"], input[name="selectCourses[]"], input[type="checkbox"]')
        # 兼容 courses[] 或 selectCourses[] 等
        if code_cell and input_tag:
            course_code = code_cell.get_text(strip=True)
            course_id = input_tag.get("value", "").strip()
            if not course_code or not course_id:
                continue

            # 解析 course_id
            m = RE_COURSE.match(course_id)
            entry = {"course_id": course_id}
            if m:
                termcode = m.group("termcode")
                termnum = m.group("termnum")
                section = m.group("section")
                entry.update({
                    "term_code": termcode,     # e.g. "5266"
                    "term": f"T{termnum}",     # e.g. "T2"
                    "section": section,        # e.g. "1"
                    "prefix": m.group("prefix")# optional prefix
                })
            else:
                # fallback: 若无法解析, 只存原始 course_id
                entry.update({
                    "term_code": None,
                    "term": None,
                    "section": None,
                    "prefix": None
                })

            # 添加到 course_map（允许同一课程多个 entry）
            course_map.setdefault(course_code, [])

            # 防止重复同一 course_id 被加入多次
            existing_ids = {e["course_id"] for e in course_map[course_code]}
            if course_id not in existing_ids:
                course_map[course_code].append(entry)

# 输出结果
print(f"共解析到 {len(course_map)} 门课程（含多学期条目）：")
print(json.dumps(course_map, indent=2, ensure_ascii=False))

# 保存到文件
out_path = "course_map.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(course_map, f, indent=2, ensure_ascii=False)

print(f"\n已保存到 {os.path.abspath(out_path)}")
