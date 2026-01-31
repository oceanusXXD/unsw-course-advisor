"""
Knowledge Graph Query Interface
Provides various query methods for course relationship navigation
"""

import pickle
from pathlib import Path
from typing import List, Set, Dict, Optional, Any, Tuple
import networkx as nx
from dataclasses import dataclass
import json
import re
from pathlib import Path
from pydantic import BaseModel, Field
from langchain_core.tools import tool
ENABLE_VERBOSE_LOGGING = True
@dataclass
class PrerequisiteChain:
    """Represents a chain of prerequisites"""
    target_course: str
    chains: List[List[str]]  # Multiple possible paths
    all_prerequisites: Set[str]


@dataclass
class CourseRelationship:
    """Course relationship information"""
    source: str
    target: str
    relationship_type: str
    metadata: Dict[str, Any]


class KnowledgeGraphQuery:
    """Query interface for UNSW course knowledge graph"""

    def __init__(self, graph_path: str):
        """
        Initialize with graph file path

        Args:
            graph_path: Path to pickled NetworkX graph
        """
        self.graph_path = Path(graph_path)
        self.graph = self._load_graph()

    def _load_graph(self) -> nx.MultiDiGraph:
        """Load graph from disk"""
        print(f"Loading knowledge graph from {self.graph_path}...")
        with open(self.graph_path, 'rb') as f:
            graph = pickle.load(f)
        print(f"[OK] Loaded graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges\n")
        return graph

    # ========================================================================
    # Basic Course Queries
    # ========================================================================

    def get_course_info(self, course_code: str) -> Optional[Dict[str, Any]]:
        """
        Get all information about a course

        Args:
            course_code: Course code (e.g., "COMP3900")

        Returns:
            Dictionary of course attributes or None if not found
        """
        if course_code not in self.graph:
            return None

        return dict(self.graph.nodes[course_code])

    def course_exists(self, course_code: str) -> bool:
        """Check if course exists in graph"""
        return course_code in self.graph

    def get_all_courses(self) -> List[str]:
        """Get all course codes"""
        return [
            node for node, data in self.graph.nodes(data=True)
            if data.get("node_type") == "Course"
        ]

    # ========================================================================
    # Prerequisite Queries
    # ========================================================================

    def get_direct_prerequisites(self, course_code: str) -> List[str]:
        """
        Get immediate prerequisites of a course

        Args:
            course_code: Target course code

        Returns:
            List of prerequisite course codes
        """
        if course_code not in self.graph:
            return []

        prereqs = []
        # 遍历前驱节点 (predecessor)，即 P -> course_code
        for predecessor in self.graph.predecessors(course_code):
            # 修复: 检查 P -> course_code 这条边
            # 原始错误代码: self.graph[course_code][predecessor]
            for key, edge_data in self.graph[predecessor][course_code].items():
                if edge_data.get("relationship") == "REQUIRES":
                    prereqs.append(predecessor)
                    break

        return prereqs

    def get_prerequisite_chain(self, course_code: str, max_depth: int = 10) -> PrerequisiteChain:
        """
        Get all prerequisite chains (multi-hop)

        Args:
            course_code: Target course code
            max_depth: Maximum depth to search

        Returns:
            PrerequisiteChain object with all paths
        """
        if course_code not in self.graph:
            return PrerequisiteChain(course_code, [], set())

        all_prereqs = set()
        chains = []

        def dfs_prereqs(current: str, path: List[str], depth: int):
            if depth > max_depth:
                return

            # (这个函数递归调用 get_direct_prerequisites, 所以也会被修正)
            direct_prereqs = self.get_direct_prerequisites(current)

            if not direct_prereqs:
                # Leaf node - save this chain
                if path:
                    chains.append(path[:])
                return

            for prereq in direct_prereqs:
                if prereq not in path:  # Avoid cycles
                    all_prereqs.add(prereq)
                    path.append(prereq)
                    dfs_prereqs(prereq, path, depth + 1)
                    path.pop()

        dfs_prereqs(course_code, [], 0)

        return PrerequisiteChain(
            target_course=course_code,
            chains=chains,
            all_prerequisites=all_prereqs
        )

    def get_courses_unlocked_by(self, course_code: str) -> List[str]:
        """
        Get courses that become available after completing this course
        (即: 查找 course_code 作为先修课的后续课程)

        Args:
            course_code: Completed course code

        Returns:
            List of unlocked course codes
        """
        if course_code not in self.graph:
            return []

        unlocked = []
        # 遍历后继节点 (successor)，即 course_code -> S
        for successor in self.graph.successors(course_code):
            # 检查 course_code -> S 这条边
            for key, edge_data in self.graph[course_code][successor].items():
                # 修复: 逻辑上 P -> S 的边是 "REQUIRES"
                # 原始错误代码: "UNLOCKS"
                if edge_data.get("relationship") == "REQUIRES":
                    unlocked.append(successor)
                    break

        return unlocked

    def get_all_unlocked_courses(self, completed_courses: Set[str]) -> List[str]:
        """
        Get all courses that can be taken given completed courses

        Args:
            completed_courses: Set of completed course codes

        Returns:
            List of course codes that prerequisites are satisfied
        """
        available = []

        for course in self.get_all_courses():
            if course in completed_courses:
                continue

            prereqs = self.get_direct_prerequisites(course)

            # Check if all prerequisites are completed
            if all(prereq in completed_courses for prereq in prereqs):
                available.append(course)

        return available

    # ========================================================================
    # Corequisite Queries
    # ========================================================================

    def get_corequisites(self, course_code: str) -> List[str]:
        """Get courses that must be taken together"""
        if course_code not in self.graph:
            return []

        coreqs = []
        # 遍历前驱节点 (predecessor)，即 C -> course_code
        for predecessor in self.graph.predecessors(course_code):
            # 修复: 检查 C -> course_code 这条边
            # 原始错误代码: self.graph[course_code][predecessor]
            for key, edge_data in self.graph[predecessor][course_code].items():
                if edge_data.get("relationship") == "COREQUISITE_OF":
                    coreqs.append(predecessor)
                    break

        return coreqs

    # ========================================================================
    # Incompatibility Queries
    # ========================================================================

    def get_incompatible_courses(self, course_code: str) -> List[str]:
        """Get courses that cannot be taken together with this course"""
        if course_code not in self.graph:
            return []
        
        # 修复: 必须进行对称检查 (入边和出边)
        incompatible_set = set()
        for neighbor in self.graph.neighbors(course_code):
            # 检查出边: course_code -> neighbor
            if self.graph.has_edge(course_code, neighbor):
                for key, edge_data in self.graph[course_code][neighbor].items():
                    if edge_data.get("relationship") == "INCOMPATIBLE_WITH":
                        incompatible_set.add(neighbor)
                        break

            # 检查入边: neighbor -> course_code
            if self.graph.has_edge(neighbor, course_code):
                for key, edge_data in self.graph[neighbor][course_code].items():
                    if edge_data.get("relationship") == "INCOMPATIBLE_WITH":
                        incompatible_set.add(neighbor)
                        break

        return list(incompatible_set)

    def check_incompatibility_conflict(self,
                                         course_code: str,
                                         completed_courses: Set[str]) -> Tuple[bool, List[str]]:
        """
        Check if course has incompatibility with completed courses

        Returns:
            (has_conflict, list_of_conflicting_courses)
        """
        incompatible = self.get_incompatible_courses(course_code)
        conflicts = [c for c in incompatible if c in completed_courses]
        return len(conflicts) > 0, conflicts

    # ========================================================================
    # major_code Queries
    # ========================================================================

    def get_courses_in_major(self, major_code: str) -> List[str]:
        """Get all courses that are part of a major_code"""
        if major_code not in self.graph:
            return []

        courses = []
        # 查找 Course -> major_code 的边
        for predecessor in self.graph.predecessors(major_code):
            # 访问 (predecessor, major_code) 边
            for key, edge_data in self.graph[predecessor][major_code].items():
                if edge_data.get("relationship") == "PART_OF":
                    if self.graph.nodes[predecessor].get("node_type") == "Course":
                        courses.append(predecessor)
                        break

        return courses

    def get_majors_for_course(self, course_code: str) -> List[Dict[str, str]]:
        """
        Get all majors that include this course

        Returns:
            List of dicts with major_code and requirement_type
        """
        if course_code not in self.graph:
            return []

        majors = []
        # 查找 Course -> major_code 的边
        for successor in self.graph.successors(course_code):
            # 访问 (course_code, successor) 边
            for key, edge_data in self.graph[course_code][successor].items():
                if edge_data.get("relationship") == "PART_OF":
                    if self.graph.nodes[successor].get("node_type") == "major_code":
                        majors.append({
                            "major_code": successor,
                            "requirement_type": edge_data.get("requirement_type", "")
                        })
                        break

        return majors

    def get_major_info(self, major_code: str) -> Optional[Dict[str, Any]]:
        """Get major_code information"""
        if major_code not in self.graph:
            return None

        return dict(self.graph.nodes[major_code])

    # ========================================================================
    # Requirement Group Queries
    # ========================================================================

    def get_requirement_groups_for_major(self, major_code: str) -> List[str]:
        """Get all requirement groups for a major_code"""
        if major_code not in self.graph:
            return []

        groups = []
        # 查找 Group -> major_code 的边
        for predecessor in self.graph.predecessors(major_code):
            for key, edge_data in self.graph[predecessor][major_code].items():
                if edge_data.get("relationship") == "BELONGS_TO":
                    if self.graph.nodes[predecessor].get("node_type") == "RequirementGroup":
                        groups.append(predecessor)
                        break

        return groups

    def get_courses_in_requirement_group(self, group_id: str) -> List[str]:
        """Get all courses that satisfy a requirement group"""
        if group_id not in self.graph:
            return []

        courses = []
        # 查找 Course -> Group 的边
        for predecessor in self.graph.predecessors(group_id):
            for key, edge_data in self.graph[predecessor][group_id].items():
                if edge_data.get("relationship") == "SATISFIES":
                    if self.graph.nodes[predecessor].get("node_type") == "Course":
                        courses.append(predecessor)
                        break

        return courses

    # ========================================================================
    # Path Finding
    # ========================================================================

    def find_prerequisite_path(self,
                                 from_course: str,
                                 to_course: str,
                                 max_length: int = 10) -> List[List[str]]:
        """
        Find all paths from one course to another via REQUIRES relationships

        Args:
            from_course: Starting course
            to_course: Target course
            max_length: Maximum path length

        Returns:
            List of paths (each path is a list of course codes)
        """
        if from_course not in self.graph or to_course not in self.graph:
            return []

        # Create a filtered graph with only REQUIRES edges
        requires_graph = nx.DiGraph()
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            if data.get("relationship") == "REQUIRES":
                requires_graph.add_edge(u, v)

        try:
            # Find all simple paths
            paths = list(nx.all_simple_paths(
                requires_graph,
                from_course,
                to_course,
                cutoff=max_length
            ))
            return paths
        except nx.NetworkXNoPath:
            return []

    def get_shortest_prerequisite_path(self,
                                         from_course: str,
                                         to_course: str) -> Optional[List[str]]:
        """Find shortest prerequisite path between two courses"""
        paths = self.find_prerequisite_path(from_course, to_course)
        if not paths:
            return None
        return min(paths, key=len)

    # ========================================================================
    # Advanced Queries
    # ========================================================================

    def get_missing_prerequisites(self,
                                    course_code: str,
                                    completed_courses: Set[str]) -> Dict[str, Any]:
        """
        Get detailed missing prerequisite information

        Returns:
            Dict with direct_missing, all_missing, and prerequisite_tree
        """
        chain = self.get_prerequisite_chain(course_code)
        direct_prereqs = self.get_direct_prerequisites(course_code)

        direct_missing = [p for p in direct_prereqs if p not in completed_courses]
        all_missing = [p for p in chain.all_prerequisites if p not in completed_courses]

        return {
            "course_code": course_code,
            "direct_missing": direct_missing,
            "all_missing": all_missing,
            "prerequisite_chains": chain.chains,
            "total_prerequisites": len(chain.all_prerequisites)
        }

    def get_course_relationships(self, course_code: str) -> Dict[str, List[str]]:
        """
        Get all relationships for a course

        Returns:
            Dict mapping relationship types to lists of related courses
        """
        if course_code not in self.graph:
            return {}

        relationships = {
            "requires": self.get_direct_prerequisites(course_code),
            "unlocks": self.get_courses_unlocked_by(course_code),
            "corequisites": self.get_corequisites(course_code),
            "incompatible": self.get_incompatible_courses(course_code),
            "majors": [m["major_code"] for m in self.get_majors_for_course(course_code)]
        }

        return relationships

    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics"""
        stats = {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_types": {},
            "relationship_types": {}
        }

        for node, data in self.graph.nodes(data=True):
            node_type = data.get("node_type", "Unknown")
            stats["node_types"][node_type] = stats["node_types"].get(node_type, 0) + 1

        for u, v, key, data in self.graph.edges(keys=True, data=True):
            rel_type = data.get("relationship", "Unknown")
            stats["relationship_types"][rel_type] = stats["relationship_types"].get(rel_type, 0) + 1

        return stats
def _to_jsonable(x):
    """辅助：把不可序列化类型转换成 JSON 可序列化类型"""
    if isinstance(x, set):
        return list(x)
    if isinstance(x, (list, tuple)):
        return [_to_jsonable(i) for i in x]
    if isinstance(x, dict):
        return {k: _to_jsonable(v) for k, v in x.items()}
    return x


def _infer_action_from_query(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    (新增辅助函数)
    如果 'action' 缺失，尝试从 'query' 推断。
    """
    if "action" in args and args["action"]:
        # Action 已存在，无需推断
        return args

    query = args.get("query", "")
    if not query:
        # 既没有 action 也没有 query，无法继续
        return args # (后续会触发 "missing action" 错误)

    # 推断逻辑：
    # 1. 检查查询中是否有课程代码
    course_match = re.search(r'\b([A-Z]{4}\d{4})\b', query, re.IGNORECASE)
    
    if course_match:
        course_code = course_match.group(1).upper()
        
        # 简单的推断规则
        query_lower = query.lower()
        
        if "prereq" in query_lower or "先修" in query_lower:
            args["action"] = "direct_prereqs"
            args["course_code"] = course_code
        elif "unlock" in query_lower or "解锁" in query_lower:
            args["action"] = "unlocks_by"
            args["course_code"] = course_code
        elif "incompatible" in query_lower or "不兼容" in query_lower:
            args["action"] = "incompatible"
            args["course_code"] = course_code
        else:
            # 默认操作：获取课程信息
            args["action"] = "get_course_info"
            args["course_code"] = course_code
            
        if ENABLE_VERBOSE_LOGGING:
            print(f"  [KGS Tool] 'action' 缺失, 从 query '{query}' 推断为: {args['action']}")

    # (如果未来需要，可以在此添加更多基于 query 的推断)
    
    return args

# === 1. 修改 Pydantic 模型以对齐数据契约 ===
class KnowledgeGraphArgs(BaseModel):
    """knowledge_graph_search 工具的输入参数"""
    action: str = Field(description="要执行的操作。例如: 'direct_prereqs', 'missing_prereqs' 等")
    
    # 与 StudentInfo 契约对齐：这是一个字符串列表
    completed_courses: Optional[List[str]] = Field(
        default=None, 
        description="已修课程代码列表，例如 ['COMP1511', 'MATH1131']"
    )
    
    # 其他参数保持不变
    course_code: Optional[str] = Field(default=None, description="课程代码，例如 'COMP3900'")
    from_course: Optional[str] = Field(default=None, description="起始课程代码（用于路径查找）")
    to_course: Optional[str] = Field(default=None, description="目标课程代码（用于路径查找）")
    major_code: Optional[str] = Field(default=None, description="专业代码，例如 'COMPIH'")
    group_id: Optional[str] = Field(default=None, description="RequirementGroup 的 ID")
    max_depth: int = Field(default=10, description="最大检索深度")
    max_length: int = Field(default=10, description="路径最大长度")
    graph_path: Optional[str] = Field(default=None, description="可选：覆盖默认的 KG pickle 路径")

@tool(args_schema=KnowledgeGraphArgs)
def knowledge_graph_search(**kwargs) -> Dict[str, Any]:
    """
    Tool entrypoint for KnowledgeGraphQuery operations.

    必填参数:
      - action: str, 要执行的操作（见下方 action 列表）

    可选参数视 action 而定，常用字段:
      - course_code: str
      - from_course: str
      - to_course: str
      - major_code: str
      - completed_courses: list[str] 或 set
      - max_depth / max_length: int
      - graph_path: str (可选，覆盖默认路径)

    支持的 action 列表 & 含义:
      - "get_course_info"
      - "course_exists"
      - "all_courses"
      - "direct_prereqs"
      - "prereq_chain"
      - "unlocks_by"
      - "all_unlocked"
      - "corequisites"
      - "incompatible"
      - "check_incompatibility_conflict"
      - "courses_in_major"
      - "majors_for_course"
      - "major_info"
      - "requirement_groups_for_major"
      - "courses_in_requirement_group"
      - "find_prereq_path"
      - "shortest_prereq_path"
      - "missing_prereqs"
      - "course_relationships"
      - "statistics"

    返回:
      {"status":"ok","result": <结构化结果>} 或 {"status":"error","error": "<message>"}

    示例:
      args = {"action":"direct_prereqs", "course_code":"COMP3900"}
    """
    try:
        # 首先尝试从查询中推断 action (业务逻辑)
        args_dict = _infer_action_from_query(kwargs)
        # 然后用 Pydantic 进行最终验证、类型转换和默认值填充
        args = KnowledgeGraphArgs.model_validate(args_dict)
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"[ERR] [KGS Tool] 参数解析失败: {e}")
        return {"status": "error", "error": f"参数解析或验证失败: {e}"}

    # Pydantic 保证了 action 存在，但我们还是做一个显式检查以防万一
    if not args.action:
        return {"status": "error", "error": "缺少必需的 'action' 参数"}

    try:
        # 加载知识图谱 (逻辑不变)
        graph_path = args.graph_path
        if not graph_path:
            script_dir = Path(__file__).parent
            project_root = script_dir.parent.parent.parent.parent # 根据你的项目结构调整
            graph_path = project_root / "course_data" / "knowledge_graph" / "course_kg.pkl"
        
        kg = KnowledgeGraphQuery(str(graph_path))
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"[ERR] [KGS Tool] 加载知识图谱失败: {e}")
        return {"status": "error", "error": f"加载知识图谱失败: {e}"}

    try:
        # === 核心分发逻辑 ===
        # 现在可以直接访问 args.action, args.course_code 等强类型属性
        
        # --- Course Info ---
        if args.action == "get_course_info":
            if not args.course_code: return {"status":"error","error":"get_course_info 需要 course_code"}
            res = kg.get_course_info(args.course_code)
            return {"status":"ok","result": _to_jsonable(res) if res is not None else None}
        if args.action == "course_exists":
            if not args.course_code: return {"status":"error","error":"course_exists 需要 course_code"}
            return {"status":"ok","result": kg.course_exists(args.course_code)}
        if args.action == "all_courses":
            return {"status":"ok","result": kg.get_all_courses()}

        # --- Prerequisite & Unlocks ---
        if args.action == "direct_prereqs":
            if not args.course_code: return {"status":"error","error":"direct_prereqs 需要 course_code"}
            return {"status":"ok","result": kg.get_direct_prerequisites(args.course_code)}
        if args.action == "prereq_chain":
            if not args.course_code: return {"status":"error","error":"prereq_chain 需要 course_code"}
            chain = kg.get_prerequisite_chain(args.course_code, max_depth=args.max_depth)
            return {"status":"ok","result": {"target_course": chain.target_course, "chains": chain.chains, "all_prerequisites": list(chain.all_prerequisites)}}
        if args.action == "unlocks_by":
            if not args.course_code: return {"status":"error","error":"unlocks_by 需要 course_code"}
            return {"status":"ok","result": kg.get_courses_unlocked_by(args.course_code)}
        if args.action == "all_unlocked":
            completed_set = set(args.completed_courses or [])
            return {"status":"ok","result": kg.get_all_unlocked_courses(completed_set)}
        if args.action == "missing_prereqs":
            if not args.course_code: return {"status":"error","error":"missing_prereqs 需要 course_code"}
            completed_set = set(args.completed_courses or [])
            res = kg.get_missing_prerequisites(args.course_code, completed_set)
            return {"status":"ok","result": _to_jsonable(res)}

        # --- Other Relationships ---
        if args.action == "corequisites":
            if not args.course_code: return {"status":"error","error":"corequisites 需要 course_code"}
            return {"status":"ok","result": kg.get_corequisites(args.course_code)}
        if args.action == "incompatible":
            if not args.course_code: return {"status":"error","error":"incompatible 需要 course_code"}
            return {"status":"ok","result": kg.get_incompatible_courses(args.course_code)}
        if args.action == "check_incompatibility_conflict":
            if not args.course_code: return {"status":"error","error":"check_incompatibility_conflict 需要 course_code"}
            completed_set = set(args.completed_courses or [])
            conflicts = kg.check_incompatibility_conflict(args.course_code, completed_set)
            return {"status":"ok","result": {"has_conflict": conflicts[0], "conflicting": conflicts[1]}}
        if args.action == "course_relationships":
            if not args.course_code: return {"status":"error","error":"course_relationships 需要 course_code"}
            res = kg.get_course_relationships(args.course_code)
            return {"status":"ok","result": _to_jsonable(res)}

        # --- major_code & Requirements ---
        if args.action == "courses_in_major":
            if not args.major_code: return {"status":"error","error":"courses_in_major 需要 major_code"}
            return {"status":"ok","result": kg.get_courses_in_major(args.major_code)}
        if args.action == "majors_for_course":
            if not args.course_code: return {"status":"error","error":"majors_for_course 需要 course_code"}
            return {"status":"ok","result": kg.get_majors_for_course(args.course_code)}
        if args.action == "major_info":
            if not args.major_code: return {"status":"error","error":"major_info 需要 major_code"}
            return {"status":"ok","result": kg.get_major_info(args.major_code)}
        if args.action == "requirement_groups_for_major":
            if not args.major_code: return {"status":"error","error":"requirement_groups_for_major 需要 major_code"}
            return {"status":"ok","result": kg.get_requirement_groups_for_major(args.major_code)}
        if args.action == "courses_in_requirement_group":
            if not args.group_id: return {"status":"error","error":"courses_in_requirement_group 需要 group_id"}
            return {"status":"ok","result": kg.get_courses_in_requirement_group(args.group_id)}

        # --- Path Finding ---
        if args.action == "find_prereq_path":
            if not args.from_course or not args.to_course: return {"status":"error","error":"find_prereq_path 需要 from_course 和 to_course"}
            paths = kg.find_prerequisite_path(args.from_course, args.to_course, max_length=args.max_length)
            return {"status":"ok","result": paths}
        if args.action == "shortest_prereq_path":
            if not args.from_course or not args.to_course: return {"status":"error","error":"shortest_prereq_path 需要 from_course 和 to_course"}
            sp = kg.get_shortest_prerequisite_path(args.from_course, args.to_course)
            return {"status":"ok","result": sp}

        # --- General ---
        if args.action == "statistics":
            return {"status":"ok","result": kg.get_statistics()}

        # Fallback for unknown action
        return {"status":"error", "error": f"未知的 action: {args.action}"}

    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"[ERR] [KGS Tool] 执行 action '{args.action}' 时失败: {e}")
            import traceback
            traceback.print_exc()
        return {"status": "error", "error": f"执行 action '{args.action}' 时发生错误: {str(e)}"}

#def main():
#    """测试查询功能"""
#    try:
#        script_dir = Path(__file__).parent
#        project_root = script_dir.parent.parent.parent.parent
#    except NameError:
#        print("Warning: __file__ not defined. Using current directory as base.")
#        # 如果在 REPL 或 Notebook 中运行，请手动修改这些路径
#        script_dir = Path(".")
#        project_root = Path(".") # 假设在项目根目录运行
#    
#    graph_path = project_root / "course_data" / "knowledge_graph" / "course_kg.pkl"
#
#    print("=" * 80)
#    print("知识图谱查询接口测试")
#    print("=" * 80 + "\n")
#
#    if not graph_path.exists():
#        print(f"[ERR] 图文件未找到: {graph_path}")
#        print("   请先运行 build_knowledge_graph.py")
#        return
#
#    # 初始化查询接口
#    kg = KnowledgeGraphQuery(str(graph_path))
#
#    # 测试查询
#    print("=" * 80)
#    print("测试1: 课程信息 (COMP3900)")
#    print("=" * 80)
#    course_info = kg.get_course_info("COMP3900")
#    if course_info:
#        print(f"课程代码: {course_info.get('code')}")
#        print(f"课程等级: {course_info.get('level')}")
#        print(f"学分: {course_info.get('credit_points')}")
#        print(f"开课学期: {course_info.get('offering_terms')}")
#    else:
#        print("未找到 COMP3900 课程信息")
#
#    print("\n" + "=" * 80)
#    print("测试2: 先修课程 (COMP3900)")
#    print("=" * 80)
#    prereqs = kg.get_direct_prerequisites("COMP3900")
#    print(f"COMP3900 的直接先修课程: {prereqs}")
#
#    chain = kg.get_prerequisite_chain("COMP3900")
#    print(f"所有先修课程: {chain.all_prerequisites}")
#    print(f"先修课程链: 找到 {len(chain.chains)} 条路径")
#    if chain.chains:
#        shortest_chain = min(chain.chains, key=len)
#        print(f"最短路径: {shortest_chain}")
#    else:
#        print("未找到先修课程链")
#
#    print("\n" + "=" * 80)
#    print("测试3: 完成 COMP2521 后可解锁的课程")
#    print("=" * 80)
#    unlocked = kg.get_courses_unlocked_by("COMP2521")
#    print(f"可解锁课程数量: {len(unlocked)}")
#    print(f"前10门课程: {unlocked[:10]}...")
#
#    print("\n" + "=" * 80)
#    print("测试4: 专业查询 (COMPIH)")
#    print("=" * 80)
#    courses_in_major = kg.get_courses_in_major("COMPIH")
#    print(f"COMPIH 专业包含课程数量: {len(courses_in_major)}")
#    print(f"示例课程: {courses_in_major[:5]}")
#
#    print("\n" + "=" * 80)
#    print("测试5: 课程关系 (COMP3900)")
#    print("=" * 80)
#    rels = kg.get_course_relationships("COMP3900")
#    print(f"COMP3900 课程关系:")
#    for rel_type, courses in rels.items():
#        if rel_type == "requires":
#            print(f"   先修课程: {courses}")
#        elif rel_type == "unlocks":
#            print(f"   可解锁课程: {courses}")
#        elif rel_type == "corequisites":
#            print(f"   并修课程: {courses}")
#        elif rel_type == "incompatible":
#            print(f"   不兼容课程: {courses}")
#        elif rel_type == "majors":
#            print(f"   所属专业: {courses}")
#
#    print("\n" + "=" * 80)
#    print("测试6: 缺失的先修课程 (COMP3900)")
#    print("=" * 80)
#    completed = {"COMP1511", "COMP1521"}
#    missing = kg.get_missing_prerequisites("COMP3900", completed)
#    print(f"已修课程: {completed}")
#    print(f"对于 COMP3900 的缺失先修课程:")
#    print(f"   直接缺失: {missing['direct_missing']}")
#    print(f"   所有缺失: {missing['all_missing']}")
#    print(f"   总先修课程数: {missing['total_prerequisites']}")
#
#    print("\n" + "=" * 80)
#    print("图谱统计信息")
#    print("=" * 80)
#    stats = kg.get_statistics()
#    print(f"总节点数: {stats['total_nodes']}")
#    print(f"总边数: {stats['total_edges']}")
#    print(f"\n节点类型分布:")
#    for node_type, count in stats['node_types'].items():
#        print(f"   {node_type}: {count}")
#    print(f"\n关系类型分布:")
#    for rel_type, count in stats['relationship_types'].items():
#        print(f"   {rel_type}: {count}")
#
#
#if __name__ == "__main__":
#    main()