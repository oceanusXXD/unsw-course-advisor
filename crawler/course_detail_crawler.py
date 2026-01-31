#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UNSW Handbook 课程详情爬虫
- [修改] 路径已适配 unsw-course-advisor/crawler 目录结构
- [修改] main() 函数已配置为 [仅运行缺失课程] 模式
- [新增] 支持 'missing_courses.txt'，自动查找缺失课程的 level 并追加
- 加入随机 UA / Referer、不规则延时、重试与中间结果恢复
- 若 ./data/{SUBJ}_course_detail.json 已存在，会跳过已抓取的 course_code
"""

from typing import Optional, List, Dict, Any, Set
import requests
from bs4 import BeautifulSoup, Tag  # type: ignore
import os
from pathlib import Path
import glob
import re
import json
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import threading


BASE_URL = "https://www.handbook.unsw.edu.au"
REQUEST_TIMEOUT = 12

# ========== 路径配置 (已修复) ==========

# 脚本位于 .../unsw-course-advisor/crawler
SCRIPT_DIR = Path(__file__).parent.resolve()
# 项目根目录是 .../unsw-course-advisor
PROJECT_ROOT = SCRIPT_DIR.parent

# 课程详情JSON的输出/读取目录
# e.g., unsw-course-advisor/course_data/course_detail_data/
DATA_DIR = str(PROJECT_ROOT / "course_data" / "course_detail_data")

# 缺失课程列表文件
# e.g., unsw-course-advisor/course_data/missing_courses.txt
MISSING_COURSES_FILE = str(PROJECT_ROOT / "course_data" / "missing_courses.txt")

# 确保数据输出目录存在
os.makedirs(DATA_DIR, exist_ok=True)

# ========== 爬虫配置 ==========
# 控制并发（对科目并发），建议 1-4
MAX_WORKERS = 3

# 延时与重试策略（可调整）
MIN_DELAY = 0.8      # 每次请求最低随机延时（秒）
MAX_DELAY = 3.2      # 每次请求最高随机延时（秒）
MAX_RETRY = 2       # 单次请求最大重试次数
BACKOFF_BASE = 2.0   # 指数退避基数

# 当遇到 403 时的额外等待范围
FORBIDDEN_WAIT_MIN = 6.0
FORBIDDEN_WAIT_MAX = 14.0

# 搜索缺失课程时按此顺序
LEVEL_ORDER = ["undergraduate", "postgraduate", "research"]

# 随机 User-Agent 列表（扩展）
USER_AGENTS = [
    # Chrome / Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/120.0.0.0",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0",
    # Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:119.0) Gecko/20100101 Firefox/119.0",
    # iPhone / Android
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
]


class UNSWHandbookScraper:
    def __init__(self, request_timeout: int = REQUEST_TIMEOUT):
        self.session = requests.Session()
        self.request_timeout = request_timeout

    # ----------------- JSON 抽取 / DOM 回退方法 -----------------
    def _extract_embedded_json(self, html: str) -> Optional[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        scripts = soup.find_all("script")
        for s in scripts[::-1]:
            text = s.string
            if not text:
                continue
            if text.strip().startswith("{") and ("pageConfig" in text or "pageProps" in text or '"props"' in text):
                try:
                    data = json.loads(text)
                    return data
                except Exception:
                    try:
                        m = re.search(r"(\{[\s\S]*\})\s*$", text)
                        if m:
                            candidate = m.group(1)
                            data = json.loads(candidate)
                            return data
                    except Exception:
                        continue
        return None

    def _find_course_obj_in_json(self, top_json: Dict[str, Any], course_code: str) -> Optional[Dict[str, Any]]:
        normalized = course_code.replace(" ", "").upper()
        found = None

        def recurse(obj):
            nonlocal found
            if found:
                return
            if isinstance(obj, dict):
                if 'cl_code' in obj:
                    if isinstance(obj['cl_code'], str) and obj['cl_code'].replace(" ", "").upper() == normalized:
                        found = obj
                        return
                if 'search_title' in obj and normalized in str(obj['search_title']).upper():
                    found = obj
                    return
                for v in obj.values():
                    recurse(v)
            elif isinstance(obj, list):
                for item in obj:
                    recurse(item)

        recurse(top_json)
        return found

    def _extract_from_course_obj(self, course_obj: Dict[str, Any]) -> Dict[str, Any]:
        out = {}
        out['overview'] = course_obj.get('overview') or course_obj.get('description') or course_obj.get('content') or ""
        enrol = course_obj.get('enrolment_rules') or course_obj.get('enrolmentConstraints') or course_obj.get('conditions_for_enrolment') or []
        if isinstance(enrol, list):
            parts = []
            for e in enrol:
                if isinstance(e, dict):
                    desc = e.get('description') or e.get('notes') or e.get('content') or ""
                    if desc:
                        parts.append(desc)
                elif isinstance(e, str):
                    parts.append(e)
            out['additional_enrolment_constraints'] = " ".join(parts).strip()
        else:
            out['additional_enrolment_constraints'] = str(enrol or "")

        eqs = course_obj.get('eqivalents') or course_obj.get('equivalents') or []
        eq_list = []
        if isinstance(eqs, list):
            for item in eqs:
                if isinstance(item, dict):
                    code = item.get('assoc_code') or item.get('cl_code') or (item.get('academic_item') or {}).get('key') or ""
                    title = item.get('assoc_short_title') or item.get('assoc_class_translated_subjects') or item.get('assoc_title') or item.get('assoc_short_title')
                    url = item.get('assoc_url') or item.get('url') or ""
                    if isinstance(title, dict):
                        title = title.get('value') if 'value' in title else str(title)
                    eq_list.append({"code": code, "title": title or "", "url": url})
        out['equivalent_courses'] = eq_list

        deliveries = course_obj.get('hb_delivery_variations') or course_obj.get('delivery_variations') or []
        delivery_out = []
        if isinstance(deliveries, list) and deliveries:
            for d in deliveries:
                if isinstance(d, dict):
                    display = d.get('display_name') or d.get('displayName') or d.get('delivery_name') or d.get('display_name')
                    notes = d.get('handbook_notes') or d.get('handbookNotes') or ""
                    dm = d.get('delivery_mode') or {}
                    dm_val = dm.get('value') if isinstance(dm, dict) else (dm or "")
                    contact = d.get('contact_hours') or d.get('contactHours') or ""
                    delivery_out.append({"display": display or "", "delivery_mode": dm_val or "", "notes": notes or "", "contact_hours": contact or ""})
        out['delivery'] = delivery_out

        offering_terms = ""
        unit_off = course_obj.get('Offering Terms') or course_obj.get('unitOffering') or course_obj.get('offering_detail') or course_obj.get('offeringDetails')
        if isinstance(unit_off, list):
            for u in unit_off:
                if isinstance(u, dict):
                    if 'offering_terms' in u:
                        offering_terms = u.get('offering_terms') or offering_terms
                    if 'offering_detail' in u and isinstance(u.get('offering_detail'), dict):
                        offering_terms = offering_terms or u['offering_detail'].get('offering_terms', "")
        elif isinstance(unit_off, dict):
            offering_terms = unit_off.get('offering_terms') or unit_off.get('offeringTerms') or ""
        offering_terms = offering_terms or course_obj.get('offering_terms') or course_obj.get('offeringTerms') or ""
        out['offering_terms'] = offering_terms

        out['notes'] = course_obj.get('notes') or ""
        return out

    @staticmethod
    def clean_text(s: Optional[str]) -> str:
        if not s:
            return ""
        return " ".join(s.strip().split())

    def _dom_extract_section(self, soup: BeautifulSoup, section_names: List[str]) -> str:
        for name in section_names:
            regex = re.compile(rf'^\s*{re.escape(name)}\s*$', re.IGNORECASE)
            for h in soup.find_all(re.compile('^h[1-6]$')):
                if regex.search(h.get_text(" ", strip=True)):
                    parts = []
                    nxt = h.find_next_sibling()
                    while nxt:
                        if isinstance(nxt, Tag) and re.match(r'^h[1-6]$', nxt.name, re.IGNORECASE):
                            break
                        txt = nxt.get_text(" ", strip=True)
                        if txt:
                            parts.append(txt)
                        nxt = nxt.find_next_sibling()
                    if parts:
                        return " ".join(parts).strip()
            for strong in soup.find_all("strong"):
                if regex.search(strong.get_text(" ", strip=True)):
                    p = strong.parent
                    if p:
                        txt = p.get_text(" ", strip=True)
                        return txt
        return ""

    # ----------------- 随机 UA / 重试 / backoff -----------------
    def _get_with_retries(self, url: str, course_code_hint: str = "", max_retry: int = MAX_RETRY) -> Optional[str]:
        """
        使用随机 UA、随机 Referer、重试与指数退避获取页面 HTML。
        返回 HTML 文本或 None（失败）。
        """
        for attempt in range(1, max_retry + 1):
            ua = random.choice(USER_AGENTS)
            referer = random.choice([
                "https://www.google.com/",
                "https://www.bing.com/",
                "https://www.handbook.unsw.edu.au/",
                url  # 用自身 URL
            ])
            headers = {
                "User-Agent": ua,
                "Referer": referer,
                "Accept-Language": "en-US,en;q=0.9"
            }
            try:
                # 每次都避免完全固定节奏
                delay_before = random.uniform(MIN_DELAY * 0.3, MIN_DELAY)
                time.sleep(delay_before)

                resp = self.session.get(url, timeout=self.request_timeout, headers=headers)
                status = resp.status_code
                if status == 200:
                    # 随机短暂停顿后返回
                    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
                    return resp.text
                elif status == 403:
                    # 遇到 Forbidden，等待更长时间再试（并带抖动）
                    wait = random.uniform(FORBIDDEN_WAIT_MIN, FORBIDDEN_WAIT_MAX) * (1 + random.random())
                    print(f"[WARN] 403 for {course_code_hint or url}. 等待 {wait:.1f}s 再重试（attempt {attempt}/{max_retry}）")
                    time.sleep(wait)
                elif status == 404:
                    return None
                else:
                    # 其它 4xx/5xx，进行指数退避
                    backoff = (BACKOFF_BASE ** attempt) + random.uniform(0, 1.5)
                    print(f"[WARN] {status} for {course_code_hint or url}. backoff {backoff:.1f}s (attempt {attempt}/{max_retry})")
                    time.sleep(backoff)
            except requests.RequestException as e:
                backoff = (BACKOFF_BASE ** attempt) + random.uniform(0, 2.0)
                print(f"[ERROR] 网络异常 {e} for {course_code_hint or url}. backoff {backoff:.1f}s (attempt {attempt}/{max_retry})")
                time.sleep(backoff)
        print(f"[ERROR] 达到最大重试次数，放弃 {course_code_hint or url}")
        return None

    # ----------------- 主抓取函数 -----------------
    def scrape_course(self, course_code: str, url_override: Optional[str] = None) -> Optional[Dict[str, Any]]:
        # 默认 URL 只是个占位符，必须依赖 url_override
        url = url_override or f"{BASE_URL}/undergraduate/courses/2026/{course_code}" # 默认用 ug
        
        html = self._get_with_retries(url, course_code_hint=course_code)
        if not html:
            return None # 如果 get_with_retries 失败 (e.g., 404)，直接返回 None

        # 解析逻辑
        parsed_json = self._extract_embedded_json(html)
        if parsed_json:
            course_obj = self._find_course_obj_in_json(parsed_json, course_code)
            if course_obj:
                data_from_json = self._extract_from_course_obj(course_obj)
                result = {
                    "course_code": course_code,
                    "url": url,
                    **data_from_json,
                    "source": "embedded_json"
                }
                # 健壮性检查：如果 JSON 找到了但概述为空，可能不是个好结果
                if result.get("overview"):
                    return result
                # 如果概述为空，继续尝试 DOM (以防万一)

        soup = BeautifulSoup(html, "html.parser")
        overview = self._dom_extract_section(soup, ["Overview", "Course overview", "Course description"])
        
        # 健壮性检查：如果 DOM 抓取也失败（概述为空），则认为此页面无效
        if not overview:
             # 这是一个关键检查，防止 200 OK 的 "Not Found" 页面被保存
            print(f"[INFO] {course_code} 在 {url} 页面抓取到，但未找到 Overview (JSON 或 DOM)，判定为无效页面")
            return None

        add_enrol = self._dom_extract_section(soup, ["Additional Enrolment Constraints", "Conditions for enrolment", "Enrolment Constraints"])
        eq_text = self._dom_extract_section(soup, ["Equivalent Courses", "Equivalent"])
        delivery_text = self._dom_extract_section(soup, ["Delivery", "Delivery Mode", "Delivery Format", "Delivery Notes"])
        offering_text = self._dom_extract_section(soup, ["Offering Terms", "Offering periods", "Offering term"])

        return {
            "course_code": course_code,
            "url": url,
            "overview": self.clean_text(overview),
            "additional_enrolment_constraints": self.clean_text(add_enrol),
            "equivalent_courses": self.clean_text(eq_text),
            "delivery": self.clean_text(delivery_text),
            "offering_terms": self.clean_text(offering_text),
            "source": "dom"
        }

# ----------------- 辅助函数 (重构自 main) -----------------

def get_subject_from_code(course_code: str) -> Optional[str]:
    """从 'COMP1927' 提取 'COMP'"""
    match = re.match(r'^([A-Z]{2,5})', course_code.upper())
    if match:
        return match.group(1)
    return None

def load_existing_codes(out_file: str) -> Set[str]:
    """安全地从 {SUBJ}_course_detail.json 加载已有的 course_code"""
    existing_codes = set()
    if os.path.exists(out_file):
        try:
            with open(out_file, "r", encoding="utf-8") as fr:
                existing = json.load(fr)
                if isinstance(existing, list):
                    for record in existing:
                        code = record.get("course_code")
                        if code:
                            existing_codes.add(code)
        except Exception:
            pass # 忽略错误, 返回空 set
    return existing_codes

def append_record_to_file(record: Dict, out_file: str) -> bool:
    """
    [线程安全] 安全地读取-追加-写回 JSON 列表文件
    """
    try:
        cur = []
        if os.path.exists(out_file):
            with open(out_file, "r", encoding="utf-8") as fr:
                try:
                    cur = json.load(fr)
                    if not isinstance(cur, list): # 处理已损坏的文件
                        cur = []
                except json.JSONDecodeError:
                    cur = []
        
        cur.append(record)
        
        with open(out_file, "w", encoding="utf-8") as fw:
            json.dump(cur, fw, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[ERROR] append_record_to_file 写入 {out_file} 失败: {e}")
        return False

# ----------------- 缺失课程处理函数 -----------------

def process_single_missing_code(code: str, scraper: UNSWHandbookScraper, file_locks: Dict[str, threading.Lock]):
    """
    [线程工作函数]
    处理单个缺失的课程代码。
    它会循环尝试 [ug, pg, research]，直到找到或全部失败。
    """
    subj = get_subject_from_code(code)
    if not subj:
        print(f"[WARN] 无法从 {code} 提取学科代码，跳过")
        return code, False

    out_file = os.path.join(DATA_DIR, f"{subj}_course_detail.json")
    
    # 检查是否已存在 (需要加锁，以防和原 main 冲突)
    with file_locks[subj]:
        existing_codes = load_existing_codes(out_file)
        
    if code in existing_codes:
        print(f"[SKIP] {code} 已存在于 {out_file}，跳过")
        return code, True # 标记为成功 (已处理)

    print(f"[FINDING] 正在查找缺失课程: {code} (将保存到 {out_file})")
    YEAR = "2026" # 固定年份 (根据你的例子)
    
    for level in LEVEL_ORDER:
        url_to_try = f"{BASE_URL}/{level}/courses/{YEAR}/{code}"
        print(f"  > [{code}] 尝试 level: {level} ({url_to_try})")
        
        # scrape_course 现在会返回 None 如果页面是 404 或无效
        rec = scraper.scrape_course(code, url_override=url_to_try)
        
        if rec:
            # 找到了!
            print(f"  [OK] [{code}] 在 {level} 找到！")
            
            # 获取该学科文件的锁，然后追加
            with file_locks[subj]:
                if append_record_to_file(rec, out_file):
                    print(f"  [OK] [SAVE] {code} 已追加到 {out_file}")
                else:
                    print(f"  [ERR] [SAVE_ERR] {code} 写入 {out_file} 失败！")
            
            # 成功抓取后，为该课程添加一个标准的长延时
            time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
            return code, True # 成功
        else:
            # 这个 level 失败了 (404 或无效页面), 稍作停顿
            print(f"  - [{code}] {level} 失败")
            time.sleep(random.uniform(MIN_DELAY * 0.5, MAX_DELAY * 0.5))

    print(f"[NOT_FOUND] 最终未能找到 {code} 在 [ug, pg, research] 中的任何一个... 跳过")
    return code, False # 失败

def process_missing_courses_parallel(scraper: UNSWHandbookScraper, codes_to_find: List[str], file_locks: Dict[str, threading.Lock]):
    """
    使用线程池并发处理 'missing_courses.txt' 中的课程。
    """
    print("\n" + "="*80)
    print(f"[INFO] 开始并行处理 {len(codes_to_find)} 门缺失的课程 (并发 workers={MAX_WORKERS})...")
    print(f"  > 文件: {MISSING_COURSES_FILE}")
    print("="*80 + "\n")
    
    success_count = 0
    fail_count = 0
    
    # 过滤掉已经存在于目标文件的课程
    codes_to_process = []
    print("[INFO] 正在预检查哪些课程已存在...")
    for code in codes_to_find:
        subj = get_subject_from_code(code)
        if not subj:
            print(f"[WARN] 预检查 {code} 失败: 无法提取学科")
            continue
        out_file = os.path.join(DATA_DIR, f"{subj}_course_detail.json")
        # 预检查不需要锁
        existing_codes = load_existing_codes(out_file)
        if code in existing_codes:
            print(f"[SKIP] {code} 已在 {out_file} 中，跳过")
            success_count += 1
        else:
            codes_to_process.append(code)
            
    print(f"[INFO] 预检查完成。需要抓取 {len(codes_to_process)} 门新课程。")
    if not codes_to_process:
        print("[INFO] 没有需要抓取的新课程。")
        return

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        # 提交任务
        futures = {ex.submit(process_single_missing_code, code, scraper, file_locks): code for code in codes_to_process}
        
        for f in as_completed(futures):
            code_done = futures[f]
            try:
                _code, success = f.result()
                if success:
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                print(f"[FATAL_ERR] {code_done} 线程处理异常: {e}")
                fail_count += 1

    print("\n" + "="*80)
    print("[INFO] 缺失课程处理完毕。")
    print(f"  > 总成功 (找到或已存在): {success_count}")
    print(f"  > 总失败 (未找到): {fail_count}")
    print("="*80 + "\n")

# ----------------- 主流程：[已修改为仅处理缺失课程] -----------------
def main():
    scraper = UNSWHandbookScraper()
    
    # 创建一个全局文件锁字典
    file_locks = defaultdict(threading.Lock)

    # ----------------- 步骤 1: 处理缺失课程 -----------------
    print(f"[INFO] 脚本已配置为 [仅处理缺失课程] 模式")
    print(f"[INFO] 正在查找缺失课程文件: {MISSING_COURSES_FILE}")

    if os.path.exists(MISSING_COURSES_FILE):
        missing_codes = []
        try:
            with open(MISSING_COURSES_FILE, "r", encoding="utf-8") as f:
                missing_codes = [line.strip().upper() for line in f if line.strip()]
            print(f"[INFO] 从文件加载了 {len(missing_codes)} 个课程代码。")
            
            # (开始处理缺失课程)
            process_missing_courses_parallel(scraper, missing_codes, file_locks)
            
        except Exception as e:
            print(f"[ERROR] 读取 {MISSING_COURSES_FILE} 失败: {e}")
    else:
        print(f"[ERR] [ERROR] 缺失课程文件未找到: {MISSING_COURSES_FILE}")
        print("  > 请确保文件存在于正确的位置。")
        return

    # ----------------- 步骤 2: 执行原有的主列表抓取 (已禁用) -----------------
    print("\n" + "="*80)
    print("[INFO] 任务已设置为 [只处理缺失课程]。")
    print("[INFO] 跳过原有的主列表抓取 (AALL_subjects_courses.json)。")
    print("\n[ALL DONE]")
    return # <-- 脚本在此处退出

    # 找到最新的 subjects_courses*.json（或 exact file）
    json_files = sorted(glob.glob(os.path.join(DATA_DIR, "AALL_subjects_courses.json")), reverse=True)
    exact_file = os.path.join(DATA_DIR, "subjects_courses.json")
    if exact_file not in json_files and os.path.exists(exact_file):
        json_files.insert(0, exact_file)
        
    if not json_files:
        print("[ERROR] 找不到 AALL_subjects_courses_*.json 或 AALL_subjects_courses.json，请先运行列表抓取。")
        # [修改] 即使找不到这个文件，如果处理了缺失课程，也算运行完毕
        if not os.path.exists(MISSING_COURSES_FILE):
            return
    
    input_path = json_files[0]
    print(f"[INFO] 使用课程列表文件: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        all_data = json.load(f)

    # 并发抓取每个学科，但每个学科内部保持顺序抓取
    subjects = list(all_data.keys())
    print(f"[INFO] 将抓取 {len(subjects)} 个学科（并发 workers={MAX_WORKERS}）")

    def process_subject(subj: str):
        levels = all_data.get(subj, {})
        # 输出文件和可续抓载入
        out_file = os.path.join(DATA_DIR, f"{subj}_course_detail.json")
        
        # [修改] 使用线程锁安全地加载
        with file_locks[subj]:
            existing_codes = load_existing_codes(out_file)
        
        if existing_codes:
            print(f"[INFO] {subj} 已存在 {len(existing_codes)} 条结果，继续未抓取项")

        results = []
        # 依次按 level_order 读取 URL 并抓取
        for lvl in LEVEL_ORDER:
            urls = levels.get(lvl, [])
            for url in urls:
                # 尝试从 url 提取课程代码
                m = re.search(r'/courses/(\d{4})/([A-Z]{2,5}\d{3,4})', url)
                code = m.group(2) if m else url  # 如果无法提取 code 用 URL 占位
                
                # [修改] 再次检查，因为缺失课程的运行可能刚刚添加了它
                if code in existing_codes:
                    # print(f"[SKIP] {subj} {code} 已存在，跳过") # (减少冗余打印)
                    continue

                # 抓取
                print(f"[INFO] {subj} 抓取 {code} -> {url}")
                
                # [修改] 确保 scrape_course 传递了 code
                code_to_scrape = code if re.match(r'^[A-Z]{2,5}\d{3,4}$', str(code)) else ""
                rec = scraper.scrape_course(code_to_scrape, url_override=url)
                
                if rec:
                    # [修改] 使用带锁的追加函数
                    with file_locks[subj]:
                        if append_record_to_file(rec, out_file):
                            print(f"[OK] 保存 {code} 到 {out_file}")
                            existing_codes.add(code) # 更新内存中的状态
                        else:
                             print(f"[ERROR] 写入文件失败: {code}")
                else:
                    print(f"[WARN] 未获取到 {code} 的详情（可能被封或页面不存在）")

                # 每次请求后随机短暂停顿（不规则）
                t = random.uniform(MIN_DELAY, MAX_DELAY)
                time.sleep(t)
                
        # [修改] 打印最终计数
        final_count = len(existing_codes)
        print(f"[DONE] 学科 {subj} 完成 (文件 {out_file} 现有 {final_count} 条)")
        return subj

    # 使用线程池并发处理学科（每科目内部顺序抓取）
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(process_subject, subj): subj for subj in subjects}
        for f in as_completed(futures):
            s = futures[f]
            try:
                f.result()
            except Exception as e:
                print(f"[ERROR] 学科 {s} 处理异常: {e}")

    print("\n[ALL DONE]")


if __name__ == "__main__":
    main()