# tools/filter_compiled_courses.py
"""
Course filtering tool for UNSW course advisor
Hard rule filter - Maximum data return with accurate constraints

对外暴露函数:
- filter_compiled_courses(args: Dict[str, Any]) -> Dict[str, Any]
  方便作为工具被动态调用（例如 tools registry 中）

 "选课硬规则集（Hard Rule Filter）。\n\n"
 "功能：\n"
 "根据学生的学业进度、目标学期、已修课程、学分要求和课程规则，"
 "筛选出当前可选课程（enrollable_courses）与被阻塞课程（blocked_courses）。"
 "输出包含总体完成进度与未满足的约束说明。\n\n"
 "出参格式（返回字典结构）：\n"
 "{\n"
 "  'status': 'ok' | 'error',\n"
 "  'result': {\n"
 "      'input_summary': {...},           # 用户输入汇总\n"
 "      'major_info': {...},              # 专业信息\n"
 "      'enable_choose_courses': [...],      # 可选课程（含原因分析）\n"
 "      'blocked_courses': [...],         # 不可选课程（含阻塞原因）\n"
 "      'requirement_status': [...],      # 每个课程组/要求完成情况\n"
 "      'overall_progress': {...},        # 整体进度统计\n"
 "      'summary': {...}                  # 简要统计结果\n"
 "  },\n"
 "  'error': { 'code': str, 'message': str } | None\n"
 "}\n"
"""

import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from collections import defaultdict
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from langchain_core.tools import tool

@dataclass
class CourseCompletionRecord:
    """Record of a completed course with term information"""
    course_code: str
    term: str  # Format: "2024T1", "2024T2", "2024T3"
    grade: Optional[str] = None  # Optional: for WAM calculation

    def get_year(self) -> int:
        """Extract year from term string"""
        return int(self.term[:4])

    def get_term_number(self) -> int:
        """Extract term number (1, 2, or 3)"""
        return int(self.term[-1])

    def is_before(self, other_term: str) -> bool:
        """Check if this course was completed before another term"""
        year1, term1 = int(self.term[:4]), int(self.term[-1])
        year2, term2 = int(other_term[:4]), int(other_term[-1])
        return (year1, term1) < (year2, term2)


@dataclass
class CourseFilterInput:
    """Input parameters for course filtering"""
    # Required fields
    completed_courses: List[CourseCompletionRecord]  # Courses with completion terms
    major_code: str  # Specialisation/major_code code
    target_term: str  # Target term to enroll (e.g., "2026T1")

    # Optional constraints
    current_uoc: Optional[int] = 0  # Total UOC completed
    wam: Optional[float] = None  # Weighted Average Mark
    max_uoc_per_term: int = 20  # Maximum UOC per term (default 20)

    # Optional filters (for future expansion)
    exclude_courses: Set[str] = field(default_factory=set)  # Courses to exclude
    min_course_level: Optional[int] = None  # e.g., 1 for level 1+
    max_course_level: Optional[int] = None  # e.g., 3 for level 1-3
    requirement_types: Optional[List[str]] = None  # e.g., ["Core Course", "Elective"]

    def __post_init__(self):
        """Validate and convert data"""
        if isinstance(self.completed_courses, list):
            # Convert dicts to CourseCompletionRecord if needed
            converted = []
            for course in self.completed_courses:
                if isinstance(course, dict):
                    # support both {"course_code":..., "term":...} or CourseCompletionRecord-like dict
                    converted.append(CourseCompletionRecord(**course))
                elif isinstance(course, CourseCompletionRecord):
                    converted.append(course)
                else:
                    raise ValueError(f"Invalid course record: {course}")
            self.completed_courses = converted

        if not isinstance(self.exclude_courses, set):
            self.exclude_courses = set(self.exclude_courses) if self.exclude_courses else set()

    def get_completed_course_codes(self) -> Set[str]:
        """Get set of completed course codes"""
        return {record.course_code for record in self.completed_courses}

    def get_completion_record(self, course_code: str) -> Optional[CourseCompletionRecord]:
        """Get completion record for a specific course"""
        for record in self.completed_courses:
            if record.course_code == course_code:
                return record
        return None


@dataclass
class PrerequisiteCheckResult:
    """Result of prerequisite checking"""
    satisfied: bool
    missing_courses: List[str]
    time_violations: List[str]  # Courses that need to be taken before others
    details: Dict[str, Any]


@dataclass
class FilteredCourse:
    """Represents a filtered course with all relevant information"""
    # Basic info
    code: str
    name: str
    credit_points: str
    url: str
    overview: str

    # Requirement info
    requirement_type: str
    requirement_group: str

    # Availability
    offering_terms: List[str]
    available_in_target_term: bool

    # Prerequisites
    prerequisite_satisfied: bool
    prerequisite_details: Optional[PrerequisiteCheckResult]

    # Corequisites
    corequisite_satisfied: bool
    corequisite_details: Optional[PrerequisiteCheckResult]

    # Incompatibility
    has_incompatible_conflict: bool
    incompatible_courses: List[str]

    # Additional constraints
    constraint_violations: List[str]  # Any constraint violations
    warnings: List[str]  # Warnings (not blocking)

    # Metadata for AI decision making
    course_level: int  # Extracted from course code
    can_enroll: bool  # Overall enrollment eligibility
    blocking_reason: Optional[str]  # Why can't enroll if can_enroll=False


@dataclass
class RequirementGroupStatus:
    """Status of a requirement group"""
    group_name: str
    required_uoc: str
    completed_uoc: int
    remaining_uoc: int
    completed_courses: List[str]
    percentage_complete: float
    is_satisfied: bool


@dataclass
class CourseFilterOutput:
    """Output structure for filtered courses"""
    # Input echo
    input_summary: Dict[str, Any]

    # major_code info
    major_info: Dict[str, str]

    # All courses from major_code (for reference)
    all_major_courses: List[str]

    # Filtered courses
    enable_choose_courses: List[FilteredCourse]  # Can enroll
    blocked_courses: List[FilteredCourse]  # Can't enroll (with reasons)

    # Requirement tracking
    requirement_status: List[RequirementGroupStatus]
    overall_progress: Dict[str, Any]

    # Summary statistics
    summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "input_summary": self.input_summary,
            "major_info": self.major_info,
            "all_major_courses": self.all_major_courses,
            "enable_choose_courses": [asdict(c) for c in self.enable_choose_courses],
            "blocked_courses": [asdict(c) for c in self.blocked_courses],
            "requirement_status": [asdict(r) for r in self.requirement_status],
            "overall_progress": self.overall_progress,
            "summary": self.summary
        }


class CourseFilter:
    """Main course filtering class - Hard rule filter"""

    def __init__(self,
                 graduation_req_dir: str,
                 course_data_file: str):
        """Initialize the course filter"""
        self.graduation_req_dir = Path(graduation_req_dir)
        self.course_data_file = Path(course_data_file)

        # Load data
        self.graduation_requirements = self._load_graduation_requirements()
        self.course_details = self._load_course_details()

        # Debug info
        # print kept minimal to avoid noisy logs when used as a tool
        print(f"[OK] Loaded {len(self.graduation_requirements)} graduation requirements")
        print(f"[OK] Loaded {len(self.course_details)} course details\n")

    def _load_graduation_requirements(self) -> Dict[str, Any]:
        """Load all graduation requirements"""
        requirements = {}
        if not self.graduation_req_dir.exists():
            return requirements

        for json_file in self.graduation_req_dir.glob("cleaned_*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    code = data.get("code") or data.get("cl_code")
                    if code:
                        requirements[code] = data
            except Exception as e:
                print(f"Warning: Failed to load {json_file.name}: {e}")
        return requirements

    def _load_course_details(self) -> Dict[str, Any]:
        """Load course details"""
        if not self.course_data_file.exists():
            return {}
        with open(self.course_data_file, 'r', encoding='utf-8') as f:
            courses = json.load(f)
        return {course["course_code"]: course for course in courses}

    def _extract_course_level(self, course_code: str) -> int:
        """Extract course level from course code (e.g., COMP3411 -> 3)"""
        for char in course_code:
            if char.isdigit():
                return int(char)
        return 0

    def _check_prerequisite_recursive(self,
                                     prerequisite: Optional[Dict],
                                     completed_codes: Set[str],
                                     target_term: str,
                                     completed_records: List[CourseCompletionRecord]) -> PrerequisiteCheckResult:
        """
        Recursively check prerequisites with time validation

        Returns detailed check result including time violations
        """
        if prerequisite is None:
            return PrerequisiteCheckResult(
                satisfied=True,
                missing_courses=[],
                time_violations=[],
                details={}
            )

        op = prerequisite.get("op")
        missing = []
        time_violations = []

        if op == "AND":
            # All conditions must be met
            all_satisfied = True
            for arg in prerequisite.get("args", []):
                result = self._check_prerequisite_recursive(arg, completed_codes, target_term, completed_records)
                if not result.satisfied:
                    all_satisfied = False
                missing.extend(result.missing_courses)
                time_violations.extend(result.time_violations)

            return PrerequisiteCheckResult(
                satisfied=all_satisfied,
                missing_courses=missing,
                time_violations=time_violations,
                details={"op": "AND", "args": prerequisite.get("args", [])}
            )

        elif op == "OR":
            # At least one condition must be met
            any_satisfied = False
            all_results = []
            for arg in prerequisite.get("args", []):
                result = self._check_prerequisite_recursive(arg, completed_codes, target_term, completed_records)
                all_results.append(result)
                if result.satisfied:
                    any_satisfied = True
                    break

            if not any_satisfied:
                # Collect all missing from OR branches
                for result in all_results:
                    missing.extend(result.missing_courses)

            return PrerequisiteCheckResult(
                satisfied=any_satisfied,
                missing_courses=missing,
                time_violations=time_violations,
                details={"op": "OR", "args": prerequisite.get("args", [])}
            )

        elif prerequisite.get("type") == "course":
            # Single course requirement
            course_code = prerequisite.get("code")
            if course_code not in completed_codes:
                return PrerequisiteCheckResult(
                    satisfied=False,
                    missing_courses=[course_code],
                    time_violations=[],
                    details={"type": "course", "code": course_code}
                )

            # Check if completed before target term
            completion_record = None
            for record in completed_records:
                if record.course_code == course_code:
                    completion_record = record
                    break

            if completion_record and not completion_record.is_before(target_term):
                time_violations.append(f"{course_code} must be completed before {target_term}")
                return PrerequisiteCheckResult(
                    satisfied=False,
                    missing_courses=[],
                    time_violations=time_violations,
                    details={"type": "course", "code": course_code, "time_issue": True}
                )

            return PrerequisiteCheckResult(
                satisfied=True,
                missing_courses=[],
                time_violations=[],
                details={"type": "course", "code": course_code}
            )

        elif prerequisite.get("type") == "uoc":
            # UOC requirement - would need current_uoc from input
            # For now, return True (can be enhanced)
            return PrerequisiteCheckResult(
                satisfied=True,
                missing_courses=[],
                time_violations=[],
                details={"type": "uoc", "amount": prerequisite.get("amount")}
            )

        elif prerequisite.get("type") == "wam":
            # WAM requirement
            return PrerequisiteCheckResult(
                satisfied=True,
                missing_courses=[],
                time_violations=[],
                details={"type": "wam", "threshold": prerequisite.get("threshold")}
            )

        return PrerequisiteCheckResult(satisfied=True, missing_courses=[], time_violations=[], details={})

    def _check_incompatible(self,
                           incompatible: Optional[Dict],
                           completed_codes: Set[str]) -> Tuple[bool, List[str]]:
        """
        Check for incompatible course conflicts

        Returns (has_conflict, list_of_conflicting_courses)
        """
        if incompatible is None:
            return False, []

        conflicts = []
        op = incompatible.get("op")

        if op == "OR":
            for arg in incompatible.get("args", []):
                if arg.get("type") == "course":
                    code = arg.get("code")
                    if code in completed_codes:
                        conflicts.append(code)
        elif incompatible.get("type") == "course":
            code = incompatible.get("code")
            if code in completed_codes:
                conflicts.append(code)

        return len(conflicts) > 0, conflicts

    def _extract_all_courses_from_major(self, major_req: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Extract all courses from major_code's graduation requirements"""
        courses_map = {}
        curriculum = major_req.get("curriculum_structure", {})
        requirement_groups = curriculum.get("requirement_groups", [])

        def extract_from_group(group: Dict[str, Any]):
            group_title = group.get("title", "Unknown")
            group_type = group.get("vertical_grouping_label", "")

            for course_ref in group.get("courses", []):
                course_code = course_ref.get("code", "")
                if course_code:
                    courses_map[course_code] = {
                        "name": course_ref.get("name", ""),
                        "credit_points": course_ref.get("credit_points", ""),
                        "requirement_group": group_title,
                        "requirement_type": group_type,
                        "parent_connector": course_ref.get("parent_connector", ""),
                        "order": course_ref.get("order", "")
                    }

            for sub_group in group.get("sub_groups", []):
                extract_from_group(sub_group)

        for group in requirement_groups:
            extract_from_group(group)

        return courses_map

    def filter_courses(self, filter_input: CourseFilterInput) -> CourseFilterOutput:
        """
        Main filtering function - Hard rule filter
        Returns maximum data with accurate constraints
        """
        # Get major_code requirements
        major_req = self.graduation_requirements.get(filter_input.major_code)

        if not major_req:
            return CourseFilterOutput(
                input_summary={"error": f"major_code {filter_input.major_code} not found"},
                major_info={},
                all_major_courses=[],
                enable_choose_courses=[],
                blocked_courses=[],
                requirement_status=[],
                overall_progress={},
                summary={"error": "major_code not found"}
            )

        # Extract major_code info
        major_info = {
            "code": major_req.get("code", ""),
            "title": major_req.get("title", ""),
            "total_credit_points": major_req.get("total_credit_points", ""),
            "faculty": major_req.get("faculty", ""),
            "school": major_req.get("school", ""),
            "study_level": major_req.get("study_level", "")
        }

        # Extract all courses from major_code
        major_courses = self._extract_all_courses_from_major(major_req)
        completed_codes = filter_input.get_completed_course_codes()

        print(f"Processing {filter_input.major_code}: {len(major_courses)} total courses")

        # Prepare lists
        enable_choose_courses = []
        blocked_courses = []

        # Process each course
        for course_code, req_info in major_courses.items():
            # Skip if already completed
            if course_code in completed_codes:
                continue

            # Skip if explicitly excluded
            if course_code in filter_input.exclude_courses:
                continue

            # Get course details
            course_detail = self.course_details.get(course_code)
            if not course_detail:
                continue

            # Extract course level
            course_level = self._extract_course_level(course_code)

            # Apply level filters
            if filter_input.min_course_level and course_level < filter_input.min_course_level:
                continue
            if filter_input.max_course_level and course_level > filter_input.max_course_level:
                continue

            # Apply requirement type filter
            if filter_input.requirement_types:
                if req_info["requirement_type"] not in filter_input.requirement_types:
                    continue

            # Check term availability
            parsed_terms = course_detail.get("parsed_terms", [])
            target_term_code = filter_input.target_term[-2:]  # Extract "T1", "T2", "T3"
            available_in_target = target_term_code in parsed_terms

            # Check prerequisites
            prerequisite = course_detail.get("parsed_prerequisite")
            prereq_result = self._check_prerequisite_recursive(
                prerequisite,
                completed_codes,
                filter_input.target_term,
                filter_input.completed_courses
            )

            # Check corequisites
            corequisite = course_detail.get("parsed_corequisite")
            coreq_result = self._check_prerequisite_recursive(
                corequisite,
                completed_codes,
                filter_input.target_term,
                filter_input.completed_courses
            )

            # Check incompatibility
            incompatible = course_detail.get("parsed_incompatible")
            has_conflict, conflict_courses = self._check_incompatible(incompatible, completed_codes)

            # Collect warnings and violations
            warnings = []
            violations = []

            if not available_in_target:
                violations.append(f"Not offered in {target_term_code}")

            if not prereq_result.satisfied:
                if prereq_result.missing_courses:
                    violations.append(f"Missing prerequisites: {', '.join(prereq_result.missing_courses)}")
                if prereq_result.time_violations:
                    violations.append(f"Time constraint: {'; '.join(prereq_result.time_violations)}")

            if not coreq_result.satisfied:
                if coreq_result.missing_courses:
                    violations.append(f"Missing corequisites: {', '.join(coreq_result.missing_courses)}")

            if has_conflict:
                violations.append(f"Incompatible with completed: {', '.join(conflict_courses)}")

            # Determine if can enroll
            can_enroll = (
                available_in_target and
                prereq_result.satisfied and
                coreq_result.satisfied and
                not has_conflict
            )

            blocking_reason = None if can_enroll else "; ".join(violations)

            # Create filtered course
            filtered_course = FilteredCourse(
                code=course_code,
                name=req_info["name"],
                credit_points=req_info["credit_points"],
                url=course_detail.get("url", ""),
                overview=course_detail.get("overview", ""),
                requirement_type=req_info["requirement_type"],
                requirement_group=req_info["requirement_group"],
                offering_terms=parsed_terms,
                available_in_target_term=available_in_target,
                prerequisite_satisfied=prereq_result.satisfied,
                prerequisite_details=prereq_result,
                corequisite_satisfied=coreq_result.satisfied,
                corequisite_details=coreq_result,
                has_incompatible_conflict=has_conflict,
                incompatible_courses=conflict_courses,
                constraint_violations=violations,
                warnings=warnings,
                course_level=course_level,
                can_enroll=can_enroll,
                blocking_reason=blocking_reason
            )

            if can_enroll:
                enable_choose_courses.append(filtered_course)
            else:
                blocked_courses.append(filtered_course)

        # Calculate requirement status
        requirement_status = self._calculate_requirement_status(
            major_req.get("curriculum_structure", {}).get("requirement_groups", []),
            filter_input.completed_courses
        )

        # Calculate overall progress
        try:
            total_required = int(major_info.get("total_credit_points", "0") or "0")
        except:
            total_required = 0

        total_completed = sum(int(r.completed_uoc) for r in requirement_status) if requirement_status else 0
        overall_progress = {
            "total_required_uoc": total_required,
            "total_completed_uoc": total_completed,
            "remaining_uoc": max(0, total_required - total_completed),
            "percentage_complete": (total_completed / total_required * 100) if total_required > 0 else 0
        }

        # Summary
        summary = {
            "total_courses_in_major": len(major_courses),
            "enable_choose_courses": len(enable_choose_courses),
            "blocked_courses": len(blocked_courses),
            "by_requirement_type": {},
            "by_blocking_reason": {}
        }

        for course in enable_choose_courses:
            req_type = course.requirement_type or "Other"
            summary["by_requirement_type"][req_type] = summary["by_requirement_type"].get(req_type, 0) + 1

        for course in blocked_courses:
            if course.blocking_reason:
                summary["by_blocking_reason"][course.blocking_reason] = \
                    summary["by_blocking_reason"].get(course.blocking_reason, 0) + 1

        # Input summary
        input_summary = {
            "major_code": filter_input.major_code,
            "target_term": filter_input.target_term,
            "completed_courses_count": len(filter_input.completed_courses),
            "current_uoc": filter_input.current_uoc,
            "wam": filter_input.wam,
            "max_uoc_per_term": filter_input.max_uoc_per_term
        }

        return CourseFilterOutput(
            input_summary=input_summary,
            major_info=major_info,
            all_major_courses=list(major_courses.keys()),
            enable_choose_courses=enable_choose_courses,
            blocked_courses=blocked_courses,
            requirement_status=requirement_status,
            overall_progress=overall_progress,
            summary=summary
        )

    def _calculate_requirement_status(self,
                                     requirement_groups: List[Dict],
                                     completed_records: List[CourseCompletionRecord]) -> List[RequirementGroupStatus]:
        """Calculate status for each requirement group"""
        statuses = []
        completed_codes = {r.course_code for r in completed_records}

        def process_group(group: Dict[str, Any]):
            group_title = group.get("title", "Unknown")
            required_uoc = group.get("credit_points", "0")

            completed_in_group = []
            completed_uoc = 0

            for course_ref in group.get("courses", []):
                course_code = course_ref.get("code", "")
                if course_code in completed_codes:
                    completed_in_group.append(course_code)
                    uoc = course_ref.get("credit_points", "0") or "0"
                    try:
                        completed_uoc += int(uoc)
                    except:
                        pass

            try:
                required_uoc_int = int(required_uoc) if required_uoc else 0
            except:
                required_uoc_int = 0

            remaining_uoc = max(0, required_uoc_int - completed_uoc)
            percentage = (completed_uoc / required_uoc_int * 100) if required_uoc_int > 0 else 0
            is_satisfied = completed_uoc >= required_uoc_int if required_uoc_int > 0 else False

            status = RequirementGroupStatus(
                group_name=group_title,
                required_uoc=required_uoc,
                completed_uoc=completed_uoc,
                remaining_uoc=remaining_uoc,
                completed_courses=completed_in_group,
                percentage_complete=percentage,
                is_satisfied=is_satisfied
            )
            statuses.append(status)

            for sub_group in group.get("sub_groups", []):
                process_group(sub_group)

        for group in requirement_groups:
            process_group(group)

        return statuses


# --------------------------
# Exported helper functions
# --------------------------

def create_course_filter_and_run(
    completed_courses: List[Dict[str, Any]] | List[str],
    major_code: str,
    target_term: str,
    current_uoc: Optional[int] = 0,
    wam: Optional[float] = None,
    max_uoc_per_term: int = 20,
    exclude_courses: Optional[List[str]] = None,
    min_course_level: Optional[int] = None,
    max_course_level: Optional[int] = None,
    requirement_types: Optional[List[str]] = None,
    graduation_req_dir: Optional[str] = None,
    course_data_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience wrapper:
    - 初始化 CourseFilter（使用默认路径或传入路径）
    - 将输入字典转换为 CourseFilterInput 并执行 filter_courses
    - 返回 CourseFilterOutput.to_dict()
    """
    # determine default project root relative to this file
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent.parent.parent

    if graduation_req_dir is None:
        graduation_req_dir = project_root / "course_data" / "cleaned_graduation_requirements"
    if course_data_file is None:
        course_data_file = project_root / "course_data" / "compiled_course_data" / "compiled_data.json"

    cf = CourseFilter(str(graduation_req_dir), str(course_data_file))
    processed_completed_courses = []
    if completed_courses:
        if isinstance(completed_courses, list) and len(completed_courses) > 0:
            if isinstance(completed_courses[0], str):
                # 输入是 List[str]，转换为 List[Dict]
                processed_completed_courses = [
                    {"course_code": code, "term": "2000T1"} for code in completed_courses
                ]
            elif isinstance(completed_courses[0], dict):
                # 输入已经是 List[Dict]
                processed_completed_courses = completed_courses
        elif isinstance(completed_courses, list) and len(completed_courses) == 0:
             processed_completed_courses = [] # 空列表
    # Build CourseFilterInput
    try:
        input_obj = CourseFilterInput(
            completed_courses=processed_completed_courses or [],
            major_code=major_code,
            target_term=target_term,
            current_uoc=current_uoc or 0,
            wam=wam,
            max_uoc_per_term=max_uoc_per_term,
            exclude_courses=set(exclude_courses or []),
            min_course_level=min_course_level,
            max_course_level=max_course_level,
            requirement_types=requirement_types
        )
    except Exception as e:
        return {"status": "error", "error": f"Invalid input for CourseFilterInput: {e}"}

    try:
        output = cf.filter_courses(input_obj)
        return {"status": "ok", "result": output.to_dict()}
    except Exception as e:
        return {"status": "error", "error": str(e)}


class CourseFilterArgs(BaseModel):
    """
    filter_compiled_courses 工具的输入参数
    [OK] 字段名与 StudentInfo 契约完全对齐：使用 major_code 而不是 major_code
    """
    
    # [OK] 配置：允许同时使用字段名和别名（兼容性）
    model_config = ConfigDict(populate_by_name=True)
    
    # [OK] 使用 major_code 作为主字段名，与 StudentInfo 一致
    # 通过 alias 兼容旧的 LLM 可能生成的 major_code
    major_code: str = Field(
        description="专业代码，例如 '3778' 或 'COMPIH'",
        alias="major_code"  # 兼容旧字段名
    )
    
    # [OK] 结构改为 List[str]，与 StudentInfo 一致
    completed_courses: List[str] = Field(
        default_factory=list, 
        description="已修课程代码列表，例如 ['COMP1511', 'MATH1131']"
    )
    
    target_term: str = Field(
        description="目标学期，例如 '2026T1'"
    )
    
    current_uoc: int = Field(
        default=0, 
        description="当前已完成的 UOC（学分）"
    )
    
    wam: Optional[float] = Field(
        default=None, 
        description="学生当前的 WAM（加权平均分）"
    )
    
    max_uoc_per_term: int = Field(
        default=20, 
        description="该学期最大可选 UOC"
    )
    
    # 其他可选参数
    exclude_courses: Optional[List[str]] = Field(
        default=None,
        description="需要排除的课程列表"
    )
    
    min_course_level: Optional[int] = Field(
        default=None,
        description="最低课程级别（例如 1000, 2000）"
    )
    
    max_course_level: Optional[int] = Field(
        default=None,
        description="最高课程级别（例如 3000, 4000）"
    )
    
    requirement_types: Optional[List[str]] = Field(
        default=None,
        description="需求类型列表"
    )
    
    graduation_req_dir: Optional[str] = Field(
        default=None,
        description="毕业要求目录路径"
    )
    
    course_data_file: Optional[str] = Field(
        default=None,
        description="课程数据文件路径"
    )


@tool(args_schema=CourseFilterArgs)
def filter_compiled_courses(**kwargs) -> Dict[str, Any]:
    """
    根据学生的学术背景和目标学期，使用硬规则筛选并推荐可选课程。
    
    此工具直接使用 Pydantic 模型进行参数验证和解析。
    
    支持的字段名（兼容性）：
    - major_code 或 major_code (推荐使用 major，与 StudentInfo 契约一致)
    
    返回：
    {
        "status": "success" | "error",
        "recommended_courses": [...],  # 推荐课程列表
        "warnings": [...],              # 警告信息
        "error": "..."                  # 错误信息（如果有）
    }
    """
    try:
        # [OK] Pydantic 会自动处理验证、别名和默认值
        # populate_by_name=True 允许同时接受 'major_code' 和 'major_code'
        args = CourseFilterArgs.model_validate(kwargs)

        # 验证必需字段
        if not args.major_code or not args.target_term:
            return {
                "status": "error", 
                "error": "major_code 和 target_term 是必需的字段"
            }

        # [OK] 调用核心业务逻辑
        # 注意：如果下游函数仍然使用 major_code 参数名，需要传递 major_code=args.major_code
        return create_course_filter_and_run(
            completed_courses=args.completed_courses,
            major_code=args.major_code,  # [WARN] 如果下游函数用 major_code 参数名
            target_term=args.target_term,
            current_uoc=args.current_uoc,
            wam=args.wam,
            max_uoc_per_term=args.max_uoc_per_term,
            exclude_courses=args.exclude_courses,
            min_course_level=args.min_course_level,
            max_course_level=args.max_course_level,
            requirement_types=args.requirement_types,
            graduation_req_dir=args.graduation_req_dir,
            course_data_file=args.course_data_file
        )
        
    except Exception as e:
        # Pydantic 验证失败或业务逻辑异常都会被捕获
        import traceback
        return {
            "status": "error", 
            "error": f"工具执行失败: {str(e)}",
            "trace": traceback.format_exc()
        }

# Keep main for local testing
def main():
    """Test function"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent.parent.parent

    graduation_req_dir = project_root / "course_data" / "cleaned_graduation_requirements"
    course_data_file = project_root / "course_data" / "compiled_course_data" / "compiled_data.json"

    print("=" * 80)
    print("UNSW Hard Rule Course Filter")
    print("=" * 80)
    print(f"Project root: {project_root}\n")

    if not graduation_req_dir.exists() or not course_data_file.exists():
        print("[ERR] Data files not found")
        return

    # 测试用例
    test_input = {
        "completed_courses": [
            {"course_code": "COMP1511", "term": "2024T1"},
            {"course_code": "COMP1521", "term": "2024T2"},
            {"course_code": "COMP2521", "term": "2024T3"},
            {"course_code": "MATH1081", "term": "2024T1"},
            {"course_code": "COMP3411", "term": "2025T1"},
            {"course_code": "COMP9417", "term": "2025T2"},
            {"course_code": "COMP9517", "term": "2025T2"},
        ],
        "major_code": "COMPIH",
        "target_term": "2026T1",
        "current_uoc": 42,
        "wam": 75.5,
        "max_uoc_per_term": 20
    }

    res = filter_compiled_courses(test_input)
    if res.get("status") == "ok":
        output_file = project_root / "course_data" / "filter_output_example.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(res["result"], f, indent=2, ensure_ascii=False)
        print(f"\n[OK] Full output saved to: {output_file}")
    else:
        print("Error:", res.get("error"))


if __name__ == "__main__":
    main()
