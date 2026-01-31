import json
from pathlib import Path
from typing import Dict, Set, Optional, Any

def _parse_prerequisite_courses(prereq: Optional[Dict]) -> Set[str]:
    """
    (从 KnowledgeGraphBuilder 复制过来的辅助函数)
    Extract all course codes from prerequisite structure
    """
    if prereq is None:
        return set()
    
    courses = set()
    
    if prereq.get("op") in ["AND", "OR"]:
        for arg in prereq.get("args", []):
            courses.update(_parse_prerequisite_courses(arg))
    elif prereq.get("type") == "course":
        code = prereq.get("code")
        if code:
            courses.add(code)
    
    return courses

def main():
    """
    验证 compiled_data.json 中的课程定义是否覆盖了所有被引用的课程。
    
    - "已定义" = 在 compiled_data.json 中有完整条目的课程
    - "被引用" = 在 "先修课" 或 "专业要求" 中被提到的课程
    
    目标: 找出所有 "被引用" 但 "未定义" 的课程 (例如 COMP1927)
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
    # 这是你爬虫的 *最终输出*，也是 Builder 的 *输入*
    course_data_file = project_root / "course_data" / "compiled_course_data" / "compiled_data.json"
    
    # 这是毕业要求数据
    graduation_req_dir = project_root / "course_data" / "cleaned_graduation_requirements"
    
    print("="*80)
    print("开始验证课程数据完整性 (检查悬挂引用)...")
    print(f"  [项目根目录]: {project_root.resolve()}")
    print(f"  [课程定义文件]: {course_data_file.resolve()}")
    print(f"  [专业要求目录]: {graduation_req_dir.resolve()}")
    print("="*80 + "\n")

    # --------------------------------------------------
    # 步骤 1: 收集所有“已定义的”课程
    # --------------------------------------------------
    if not course_data_file.exists():
        print(f"[ERR] 错误: 课程定义文件未找到: {course_data_file}")
        print("  > 请先运行爬虫并编译生成 compiled_data.json 文件。")
        return

    defined_courses = set()
    all_course_data = []
    try:
        with open(course_data_file, 'r', encoding='utf-8') as f:
            all_course_data = json.load(f)
        for course in all_course_data:
            if course.get("course_code"):
                defined_courses.add(course["course_code"])
    except Exception as e:
        print(f"[ERR] 错误: 加载或解析 {course_data_file} 失败: {e}")
        return
        
    print(f"[OK] 步骤 1: 找到 {len(defined_courses)} 门已定义的课程 (来自 compiled_data.json)。")

    # --------------------------------------------------
    # 步骤 2: 收集所有“被引用的”课程
    # --------------------------------------------------
    mentioned_courses = set()

    # 2a: 从课程的先修/并修/不兼容中收集
    for course in all_course_data:
        mentioned_courses.update(
            _parse_prerequisite_courses(course.get("parsed_prerequisite"))
        )
        mentioned_courses.update(
            _parse_prerequisite_courses(course.get("parsed_corequisite"))
        )
        mentioned_courses.update(
            _parse_prerequisite_courses(course.get("parsed_incompatible"))
        )
    
    print(f"  > 找到 {len(mentioned_courses)} 门在课程依赖中被引用的课程。")

    # 2b: 从专业要求中收集
    if not graduation_req_dir.exists():
        print(f"[WARN] 警告: 专业要求目录未找到: {graduation_req_dir}")
    else:
        initial_count = len(mentioned_courses)
        for json_file in graduation_req_dir.glob("cleaned_*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    major_data = json.load(f)
                    curriculum = major_data.get("curriculum_structure", {})
                    groups = curriculum.get("requirement_groups", [])
                    for group in groups:
                        for course_ref in group.get("courses", []):
                            course_code = course_ref.get("code")
                            if course_code:
                                mentioned_courses.add(course_code)
            except Exception as e:
                print(f"[WARN] 警告: 解析 {json_file.name} 失败: {e}")
        
        print(f"  > 又找到 {len(mentioned_courses) - initial_count} 门在专业要求中被引用的课程。")

    print(f"[OK] 步骤 2: 共找到 {len(mentioned_courses)} 门独一无二的被引用课程。")

    # --------------------------------------------------
    # 步骤 3: 找出差异 (被引用 但 未定义)
    # --------------------------------------------------
    
    # 我们关心的是被引用了，但没有被定义的课程
    missing_courses = mentioned_courses - defined_courses

    print("\n" + "="*80)
    if not missing_courses:
        print("[OK] 验证成功: 数据完整！")
        print("  所有被引用的课程都在 compiled_data.json 中有定义。")
    else:
        print(f"[ERR] 验证失败: 发现 {len(missing_courses)} 门缺失的课程定义！")
        print("  以下课程被引用（作为先修课或专业要求），")
        print("  但在 compiled_data.json 中缺失：")
        print("---")
        for i, code in enumerate(sorted(list(missing_courses))):
            print(f"  {i+1}. {code}")
        print("---")
        print("  > 建议: 检查你的爬虫或数据采集流程，确保这些课程的数据被采集。")
        print("  > (你之前发现的 COMP1927 应该就在这个列表里)")
    print("="*80)


if __name__ == "__main__":
    main()