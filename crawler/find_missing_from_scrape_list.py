import json
from pathlib import Path
from typing import Set, Dict, Any, List

def load_required_courses(filepath: Path) -> Set[str]:
    """
    加载 all_graduation_requirements.json 文件。
    遍历所有专业、所有要求组，提取所有被列出的课程代码。
    """
    required_courses = set()
    print(f"  > 正在解析毕业要求文件: {filepath.name}")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # 假设 all_graduation_requirements.json 是一个包含所有专业JSON对象的列表
            all_majors_data: List[Dict[str, Any]] = json.load(f)
            
            for major_data in all_majors_data:
                curriculum = major_data.get("curriculum_structure", {})
                groups = curriculum.get("requirement_groups", [])
                for group in groups:
                    for course_ref in group.get("courses", []):
                        code = course_ref.get("code")
                        if code:
                            required_courses.add(code)
            
            return required_courses

    except Exception as e:
        print(f"[ERR] 错误: 解析 {filepath.name} 失败: {e}")
        return set()

def load_scraped_list_courses(filepath: Path) -> Set[str]:
    """
    加载 AALL_subjects_courses.json 文件。
    遍历所有URL，从中提取课程代码。
    """
    scraped_courses = set()
    print(f"  > 正在解析已爬取URL列表: {filepath.name}")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # 结构是 {"COMP": {"undergraduate": [...]}, ...}
            all_scraped_data: Dict[str, Dict[str, List[str]]] = json.load(f)
            
            for subject_data in all_scraped_data.values():
                for url_list in subject_data.values():
                    for url in url_list:
                        # 从 URL (https://.../COMP1010) 中提取代码
                        code = url.strip("/").split("/")[-1]
                        if code:
                            scraped_courses.add(code)
                            
            return scraped_courses
            
    except Exception as e:
        print(f"[ERR] 错误: 解析 {filepath.name} 失败: {e}")
        return set()

def main():
    """
    对比“毕业要求课程”和“已爬取URL列表课程”，找出缺失项。
    """
    try:
        # --- 路径修改 ---
        # script_dir 是 .../unsw-course-advisor/crawler
        script_dir = Path(__file__).parent 
        # project_root 是 .../unsw-course-advisor
        project_root = script_dir.parent 
        # --- 路径修改结束 ---
    except NameError:
        print("Warning: __file__ not defined. Using current directory as base.")
        script_dir = Path(".")
        # 假设在 crawler 目录运行，project_root 是上一级
        project_root = Path("..") 

    # --------------------------------------------------
    # 1. 定义文件路径 (基于新的 project_root)
    # --------------------------------------------------
    # 来源一: 毕业要求中的课程
    grad_req_file = project_root / "course_data" / "cleaned_graduation_requirements" / "all_graduation_requirements.json"
    
    # 来源二: 你的爬虫URL列表
    scraped_list_file = project_root / "course_data" / "course_detail_data" / "AALL_subjects_courses.json"
    
    print("="*80)
    print("开始对比“毕业要求”与“爬虫列表”...")
    print(f"  [项目根目录]: {project_root.resolve()}")
    print(f"  [来源 A] 毕业要求: {grad_req_file.resolve()}")
    print(f"  [来源 B] 爬虫列表: {scraped_list_file.resolve()}")
    print("="*80 + "\n")

    # --------------------------------------------------
    # 2. 检查文件是否存在
    # --------------------------------------------------
    if not grad_req_file.exists():
        print(f"[ERR] 错误: [来源 A] 文件未找到。请检查路径。")
        return
    if not scraped_list_file.exists():
        print(f"[ERR] 错误: [来源 B] 文件未找到。请检查路径。")
        return

    # --------------------------------------------------
    # 3. 加载和解析
    # --------------------------------------------------
    print("步骤 1: 加载 [来源 A] 毕业要求中的所有课程...")
    required_set = load_required_courses(grad_req_file)
    if not required_set:
        print("  > 未能从 [来源 A] 加载到任何课程。")
        return
    print(f"[OK] 完成，找到 {len(required_set)} 门课程。\n")


    print("步骤 2: 加载 [来源 B] 爬虫URL列表中的所有课程...")
    scraped_set = load_scraped_list_courses(scraped_list_file)
    if not scraped_set:
        print("  > 未能从 [来源 B] 加载到任何课程。")
        return
    print(f"[OK] 完成，找到 {len(scraped_set)} 门课程。\n")

    # --------------------------------------------------
    # 4. 对比和报告
    # --------------------------------------------------
    
    # 计算 (A - B)
    missing_from_scrape_list = required_set - scraped_set
    
    # 计算 (B - A) (那些你爬了，但似乎毕业又用不上的课)
    extra_in_scrape_list = scraped_set - required_set
    
    print("="*80)
    print("对比结果报告")
    print("="*80)

    if not missing_from_scrape_list:
        print(f"[OK] [A - B] 检查通过！")
        print("  所有在毕业要求中列出的课程，都在你的爬虫URL列表 (AALL_subjects_courses.json) 中找到了。")
    else:
        print(f"[ERR] [A - B] 发现 {len(missing_from_scrape_list)} 门缺失课程！")
        print("  以下课程在“毕业要求”中，但不在“爬虫URL列表”中：")
        print("---")
        for i, code in enumerate(sorted(list(missing_from_scrape_list))):
            print(f"  {i+1}. {code}")
        print("---")
        print("  > 建议: 检查你的爬虫列表生成逻辑，确保这些课程被包含在内。")

    print("\n" + "-"*80 + "\n")

    if extra_in_scrape_list:
        print(f"[WARN] [B - A] 额外信息：")
        print(f"  有 {len(extra_in_scrape_list)} 门课程在“爬虫URL列表”中，但未在“毕业要求”的课程组中明确列出。")
        print(f"  (这很正常，可能它们是作为先修课被间接引用，或是通识教育课程等)")
        # 打印前 20 个作为示例
        if len(extra_in_scrape_list) > 20:
            print(f"  示例: {sorted(list(extra_in_scrape_list))[:20]}...")
        else:
             print(f"  示例: {sorted(list(extra_in_scrape_list))}")
             
    print("\n" + "="*80)
    print("对比完成。")
    print("="*80)

if __name__ == "__main__":
    main()