"""
Knowledge Graph Builder for UNSW Course Data
Uses NetworkX for local graph storage and querying
"Knowledge Graph Query Interface（知识图谱查询工具）。"
"功能：对已构建的课程知识图进行多种查询（先修链、并修、解锁关系、专业归属、路径查找等），"
"返回结构化结果，便于上层 Agent/LLM 使用。"
"出参格式"
"{ \"status\": \"ok\" | \"error\", \"result\": <根据 action 返回的结构>, \"error\": <错误信息或None> }\n\n"
"示例1: action='direct_prereqs', course_code='COMP3900' -> result: ['COMP2521','MATH1081']\n"
"示例2: action='prereq_chain', course_code='COMP3900' -> result: { 'target_course':'COMP3900', 'chains': [['COMP2521','COMP2511'], ...], 'all_prerequisites': [...] }\n"
"示例3: action='statistics' -> result: { 'total_nodes': int, 'total_edges': int, 'node_types': {...}, 'relationship_types': {...} }\n"

"""

import json
import pickle
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
import networkx as nx
from dataclasses import dataclass, asdict
import matplotlib.pyplot as plt


@dataclass
class CourseNode:
    """Course node attributes"""
    code: str
    name: str
    level: int
    credit_points: str
    overview: str
    url: str
    offering_terms: List[str]
    node_type: str = "Course"


@dataclass
class MajorNode:
    """major_code/Specialisation node attributes"""
    code: str
    title: str
    faculty: str
    school: str
    total_uoc: str
    study_level: str
    node_type: str = "major_code"


@dataclass
class RequirementGroupNode:
    """Requirement group node attributes"""
    id: str  # Format: "{major_code}_{group_title}"
    major_code: str
    title: str
    required_uoc: str
    group_type: str  # Core Course, Elective, etc.
    description: str
    node_type: str = "RequirementGroup"


class KnowledgeGraphBuilder:
    """Build knowledge graph from UNSW course data"""

    def __init__(self,
                 graduation_req_dir: str,
                 course_data_file: str):
        """Initialize builder"""
        self.graduation_req_dir = Path(graduation_req_dir)
        self.course_data_file = Path(course_data_file)

        # Initialize graph
        self.graph = nx.MultiDiGraph()

        # Load data
        print("Loading data...")
        self.graduation_requirements = self._load_graduation_requirements()
        self.course_details = self._load_course_details()
        print(f"[OK] Loaded {len(self.graduation_requirements)} majors")
        print(f"[OK] Loaded {len(self.course_details)} courses\n")

    def _load_graduation_requirements(self) -> Dict[str, Any]:
        """Load graduation requirements"""
        requirements = {}
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
        with open(self.course_data_file, 'r', encoding='utf-8') as f:
            courses = json.load(f)
        return {course["course_code"]: course for course in courses}

    def _extract_course_level(self, course_code: str) -> int:
        """Extract course level from code"""
        for char in course_code:
            if char.isdigit():
                return int(char)
        return 0

    def _parse_prerequisite_courses(self, prereq: Optional[Dict]) -> Set[str]:
        """
        Extract all course codes from prerequisite structure
        (注意: 这个函数递归地展平了 AND 和 OR 列表)
        """
        if prereq is None:
            return set()

        courses = set()

        if prereq.get("op") in ["AND", "OR"]:
            for arg in prereq.get("args", []):
                courses.update(self._parse_prerequisite_courses(arg))
        elif prereq.get("type") == "course":
            courses.add(prereq.get("code"))

        return courses

    def build_graph(self) -> nx.MultiDiGraph:
        """Build complete knowledge graph"""
        print("=" * 80)
        print("Building Knowledge Graph")
        print("=" * 80)

        # Step 1: Add all course nodes
        print("\n1. Adding course nodes...")
        self._add_course_nodes()

        # Step 2: Add major_code nodes
        print("2. Adding major_code nodes...")
        self._add_major_nodes()

        # Step 3: Add requirement group nodes
        print("3. Adding requirement group nodes...")
        self._add_requirement_group_nodes()

        # Step 4: Add prerequisite relationships
        print("4. Adding prerequisite relationships...")
        self._add_prerequisite_relationships()

        # Step 5: Add corequisite relationships
        print("5. Adding corequisite relationships...")
        self._add_corequisite_relationships()

        # Step 6: Add incompatibility relationships
        print("6. Adding incompatibility relationships...")
        self._add_incompatibility_relationships()

        # Step 7: Add UNLOCKS relationships (reverse of REQUIRES)
        print("7. Adding unlock relationships...")
        self._add_unlock_relationships()

        # Step 8: Add course-major_code relationships
        print("8. Adding course-major_code relationships...")
        self._add_course_major_relationships()

        # Step 9: Add course-requirement group relationships
        print("9. Adding course-requirement group relationships...")
        self._add_course_requirement_relationships()

        # Print statistics
        self._print_statistics()

        return self.graph

    def _add_course_nodes(self):
        """Add all course nodes to graph"""
        for course_code, course_detail in self.course_details.items():
            node = CourseNode(
                code=course_code,
                name=course_detail.get("overview", "")[:100] if course_detail.get("overview") else "",
                level=self._extract_course_level(course_code),
                credit_points=str(course_detail.get("raw_entry", {}).get("uoc", "6")),
                overview=course_detail.get("overview", ""),
                url=course_detail.get("url", ""),
                offering_terms=course_detail.get("parsed_terms", [])
            )

            self.graph.add_node(course_code, **asdict(node))

        print(f"   [OK] Added {len(self.course_details)} course nodes")

    def _add_major_nodes(self):
        """Add all major_code nodes to graph"""
        for major_code, major_data in self.graduation_requirements.items():
            node = MajorNode(
                code=major_code,
                title=major_data.get("title", ""),
                faculty=major_data.get("faculty", ""),
                school=major_data.get("school", ""),
                total_uoc=major_data.get("total_credit_points", ""),
                study_level=major_data.get("study_level", "")
            )

            self.graph.add_node(major_code, **asdict(node))

        print(f"   [OK] Added {len(self.graduation_requirements)} major_code nodes")

    def _add_requirement_group_nodes(self):
        """Add requirement group nodes"""
        count = 0
        for major_code, major_data in self.graduation_requirements.items():
            curriculum = major_data.get("curriculum_structure", {})
            requirement_groups = curriculum.get("requirement_groups", [])

            for group in requirement_groups:
                group_id = f"{major_code}_{group.get('title', 'unknown').replace(' ', '_')}"

                node = RequirementGroupNode(
                    id=group_id,
                    major_code=major_code,
                    title=group.get("title", ""),
                    required_uoc=group.get("credit_points", ""),
                    group_type=group.get("vertical_grouping_label", ""),
                    description=group.get("description", "")
                )

                self.graph.add_node(group_id, **asdict(node))

                # Link requirement group to major_code
                self.graph.add_edge(group_id, major_code, relationship="BELONGS_TO")

                count += 1

        print(f"   [OK] Added {count} requirement group nodes")

    def _add_prerequisite_relationships(self):
        """Add REQUIRES relationships from prerequisite data"""
        edges_to_add = []
        for course_code, course_detail in self.course_details.items():
            prereq = course_detail.get("parsed_prerequisite")
            if prereq:
                prereq_courses = self._parse_prerequisite_courses(prereq)
                for prereq_course in prereq_courses:
                    if prereq_course in self.graph:
                        # 修复: 边的方向必须是 (先修课, 目标课程)
                        # (prereq_course -> course_code)
                        edges_to_add.append((
                            prereq_course,  # <--- 修复: 来源 (先修课)
                            course_code,    # <--- 修复: 目标 (当前课程)
                            {"relationship": "REQUIRES", "prerequisite_structure": prereq}
                        ))
        # 一次性添加，避免动态修改
        if edges_to_add:
            self.graph.add_edges_from([(u, v, d) for u, v, d in edges_to_add])
        print(f"   [OK] Added {len(edges_to_add)} prerequisite relationships")


    def _add_corequisite_relationships(self):
        """Add COREQUISITE_OF relationships"""
        edges_to_add = []
        for course_code, course_detail in self.course_details.items():
            coreq = course_detail.get("parsed_corequisite")
            if coreq:
                coreq_courses = self._parse_prerequisite_courses(coreq)
                for coreq_course in coreq_courses:
                    if coreq_course in self.graph:
                        # 修复: 边的方向必须是 (并修课, 目标课程)
                        # (coreq_course -> course_code)
                        edges_to_add.append((
                            coreq_course,   # <--- 修复: 来源 (并修课)
                            course_code,    # <--- 修复: 目标 (当前课程)
                            {"relationship": "COREQUISITE_OF", "corequisite_structure": coreq}
                        ))
        if edges_to_add:
            self.graph.add_edges_from([(u, v, d) for u, v, d in edges_to_add])
        print(f"   [OK] Added {len(edges_to_add)} corequisite relationships")

    def _add_incompatibility_relationships(self):
        """Add INCOMPATIBLE_WITH relationships (bidirectional)"""
        edges_to_add = []
        for course_code, course_detail in self.course_details.items():
            incomp = course_detail.get("parsed_incompatible")
            if incomp:
                incomp_courses = self._parse_prerequisite_courses(incomp)
                for incomp_course in incomp_courses:
                    if incomp_course in self.graph:
                        edges_to_add.append((course_code, incomp_course, {"relationship": "INCOMPATIBLE_WITH"}))
                        edges_to_add.append((incomp_course, course_code, {"relationship": "INCOMPATIBLE_WITH"}))
        if edges_to_add:
            self.graph.add_edges_from([(u, v, d) for u, v, d in edges_to_add])
        print(f"   [OK] Added {len(edges_to_add)} incompatibility relationships")

    def _add_unlock_relationships(self):
        """Add UNLOCKS relationships (reverse of REQUIRES)"""
        edges_to_add = []
        # snapshot 当前边集合
        edges_snapshot = list(self.graph.edges(keys=True, data=True))
        for u, v, key, data in edges_snapshot:
            if data.get("relationship") == "REQUIRES":
                # 原始边是 (u, v) == (prereq, target)
                # 反向边是 (v, u) == (target, prereq)
                # 注意：这里的 v, u 顺序是正确的，因为 u 是来源，v 是目标
                edges_to_add.append((v, u, {"relationship": "UNLOCKS"}))
        if edges_to_add:
            self.graph.add_edges_from([(u, v, d) for u, v, d in edges_to_add])
        print(f"   [OK] Added {len(edges_to_add)} unlock relationships")

    def _add_course_major_relationships(self):
        """Add PART_OF relationships between courses and majors"""
        edges_to_add = []
        for major_code, major_data in self.graduation_requirements.items():
            curriculum = major_data.get("curriculum_structure", {})
            requirement_groups = curriculum.get("requirement_groups", [])
            for group in requirement_groups:
                for course_ref in group.get("courses", []):
                    course_code = course_ref.get("code")
                    if course_code and course_code in self.graph:
                        edges_to_add.append((
                            course_code,
                            major_code,
                            {"relationship": "PART_OF", "requirement_type": group.get("vertical_grouping_label", "")}
                        ))
        if edges_to_add:
            self.graph.add_edges_from([(u, v, d) for u, v, d in edges_to_add])
        print(f"   [OK] Added {len(edges_to_add)} course-major_code relationships")

    def _add_course_requirement_relationships(self):
        """Add SATISFIES relationships between courses and requirement groups"""
        edges_to_add = []
        for major_code, major_data in self.graduation_requirements.items():
            curriculum = major_data.get("curriculum_structure", {})
            requirement_groups = curriculum.get("requirement_groups", [])
            for group in requirement_groups:
                group_id = f"{major_code}_{group.get('title', 'unknown').replace(' ', '_')}"
                if group_id in self.graph:
                    for course_ref in group.get("courses", []):
                        course_code = course_ref.get("code")
                        if course_code and course_code in self.graph:
                            edges_to_add.append((
                                course_code,
                                group_id,
                                {"relationship": "SATISFIES", "credit_points": course_ref.get("credit_points", "")}
                            ))
        if edges_to_add:
            self.graph.add_edges_from([(u, v, d) for u, v, d in edges_to_add])
        print(f"   [OK] Added {len(edges_to_add)} course-requirement relationships")

    def _print_statistics(self):
        """Print graph statistics"""
        print("\n" + "=" * 80)
        print("Knowledge Graph Statistics")
        print("=" * 80)

        # Count nodes by type
        node_types = {}
        for node, data in self.graph.nodes(data=True):
            node_type = data.get("node_type", "Unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1

        print("\nNodes:")
        for node_type, count in sorted(node_types.items()):
            print(f"  {node_type}: {count}")
        print(f"  Total: {self.graph.number_of_nodes()}")

        # Count edges by relationship
        edge_types = {}
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            rel_type = data.get("relationship", "Unknown")
            edge_types[rel_type] = edge_types.get(rel_type, 0) + 1

        print("\nRelationships:")
        for rel_type, count in sorted(edge_types.items()):
            print(f"  {rel_type}: {count}")
        print(f"  Total: {self.graph.number_of_edges()}")

        # Graph properties
        print(f"\nGraph Properties:")
        print(f"  Directed: {self.graph.is_directed()}")
        if self.graph.number_of_nodes() > 0:
            print(f"  Number of connected components: {nx.number_weakly_connected_components(self.graph)}")

    def save_graph(self, output_path: str):
        """Save graph to disk"""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # 保存 pickle 版本（Python 可直接加载）
        with open(output_file, 'wb') as f:
            pickle.dump(self.graph, f)
        print(f"\n[OK] Graph saved to: {output_file}")

        # ===== 修复 GraphML 报错 =====
        # 创建一个副本，把复杂数据转为字符串
        safe_graph = self.graph.copy()
        for node, data in list(safe_graph.nodes(data=True)):
            for k, v in list(data.items()):
                if isinstance(v, (list, dict, set)):
                    safe_graph.nodes[node][k] = json.dumps(v, ensure_ascii=False)

        for u, v, key, data in list(safe_graph.edges(keys=True, data=True)):
            for k, v2 in list(data.items()):
                if isinstance(v2, (list, dict, set)):
                    # 注意 MultiDiGraph 的 edges 索引
                    safe_graph.edges[u, v, key][k] = json.dumps(v2, ensure_ascii=False)

        # 保存 GraphML 版本（兼容 Gephi / Cytoscape）
        graphml_file = output_file.with_suffix('.graphml')
        nx.write_graphml(safe_graph, graphml_file)
        print(f"[OK] GraphML saved to: {graphml_file}")

        # ===== 保存 metadata =====
        metadata = {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "node_types": {},
            "relationship_types": {}
        }

        for node, data in self.graph.nodes(data=True):
            node_type = data.get("node_type", "Unknown")
            metadata["node_types"][node_type] = metadata["node_types"].get(node_type, 0) + 1

        for _, _, _, data in self.graph.edges(keys=True, data=True):
            rel_type = data.get("relationship", "Unknown")
            metadata["relationship_types"][rel_type] = metadata["relationship_types"].get(rel_type, 0) + 1

        metadata_file = output_file.with_suffix('.json')
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"[OK] Metadata saved to: {metadata_file}")


    @staticmethod
    def load_graph(graph_path: str) -> nx.MultiDiGraph:
        """Load graph from disk"""
        with open(graph_path, 'rb') as f:
            graph = pickle.load(f)
        print(f"[OK] Loaded graph with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges")
        return graph


    def extract_major_subgraph(self, major_code: str, output_path: str, expand_one_hop: bool = True):
        """
        从知识图谱中提取指定专业（major_code）的子图，并保存为 GraphML 文件。
        - 包含直接 PART_OF 到该 major_code 的课程
        - 包含属于该 major_code 的 requirement groups
        - 可选：扩展与这些课程相连的一跳邻接（REQUIRES / UNLOCKS / COREQUISITE_OF / INCOMPATIBLE_WITH）
        """
        print(f"\nExtracting subgraph for major_code: {major_code}")
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        major_nodes: Set[Any] = set()
        # 一定包含 major_code 自己
        if major_code in self.graph:
            major_nodes.add(major_code)
        else:
            print(f"[WARN] major_code node {major_code} not found in graph.")
            # 仍然继续尝试查找课程（如果课程有 PART_OF 指向该 major_code）
        
        # 1) 找到所有直接 PART_OF -> major_code 的课程
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            if data.get("relationship") == "PART_OF" and v == major_code:
                major_nodes.add(u)
        
        # 2) 找到属于该 major_code 的 requirement groups（group 节点有 major_code 属性）
        for n, data in self.graph.nodes(data=True):
            if data.get("node_type") == "RequirementGroup" and data.get("major_code") == major_code:
                major_nodes.add(n)
                # group -> major_code 的 BELONGS_TO 边会在 subgraph 中出现（如果保留 major_code）
        
        if not major_nodes:
            print(f"[WARN] No nodes found for major_code: {major_code}")
            return None

        # 3) 可选：扩展一跳邻接（让子图包含相关的前置课程/解锁课程等）
        if expand_one_hop:
            extra = set()
            allowed_rels = {"REQUIRES", "UNLOCKS", "COREQUISITE_OF", "INCOMPATIBLE_WITH", "PART_OF", "SATISFIES", "BELONGS_TO"}
            for u, v, key, data in self.graph.edges(keys=True, data=True):
                rel = data.get("relationship")
                if rel in allowed_rels:
                    # 如果任一端在 major_nodes，加入另一端
                    if u in major_nodes and v not in major_nodes:
                        extra.add(v)
                    if v in major_nodes and u not in major_nodes:
                        extra.add(u)
            # 合并
            major_nodes.update(extra)

        # 最后从原图中提取子图
        subgraph = self.graph.subgraph(major_nodes).copy()
        print(f"[OK] Subgraph created with {subgraph.number_of_nodes()} nodes and {subgraph.number_of_edges()} edges")

        # 为了兼容 GraphML，需要把复杂属性序列化（list/dict/set -> JSON string）
        safe_sub = subgraph.copy()
        for node, data in list(safe_sub.nodes(data=True)):
            for k, v in list(data.items()):
                if isinstance(v, (list, dict, set)):
                    safe_sub.nodes[node][k] = json.dumps(v, ensure_ascii=False)
        for u, v, key, data in list(safe_sub.edges(keys=True, data=True)):
            for k, v2 in list(data.items()):
                if isinstance(v2, (list, dict, set)):
                    safe_sub.edges[u, v, key][k] = json.dumps(v2, ensure_ascii=False)

        # 保存子图
        subgraph_path = output_path / f"{major_code}_subgraph.graphml"
        nx.write_graphml(safe_sub, subgraph_path)
        print(f"[OK] Subgraph saved to: {subgraph_path}")

        return subgraph


def visualize_graph(graph, title="Graph Visualization", max_nodes=200):
    """
    可视化一个 NetworkX 图（只显示前 max_nodes 个节点防止太大）
    """
    if graph is None:
        print("[WARN] No graph to visualize.")
        return

    if graph.number_of_nodes() > max_nodes:
        print(f"[WARN] Graph has {graph.number_of_nodes()} nodes, sampling first {max_nodes} for visualization.")
        sampled_nodes = list(graph.nodes())[:max_nodes]
        graph = graph.subgraph(sampled_nodes)

    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(graph, seed=42, k=0.15)
    # 注意：避免为节点上色使用自定义 color 列表（Matplotlib 风格限制）
    nx.draw(
        graph,
        pos,
        with_labels=False,
        node_size=50,
        node_color=None,
        edge_color='gray',
        alpha=0.8
    )
    plt.title(title)
    plt.show()


def main():
    """Build and save knowledge graph"""
    try:
        script_dir = Path(__file__).parent
        project_root = script_dir.parent.parent.parent.parent
    except NameError:
        print("Warning: __file__ not defined. Using current directory as base.")
        #  如果在 REPL 或 Notebook 中运行，请手动修改这些路径
        script_dir = Path(".")
        project_root = Path(".") # 假设在项目根目录运行

    graduation_req_dir = project_root / "course_data" / "cleaned_graduation_requirements"
    course_data_file = project_root / "course_data" / "compiled_course_data" / "compiled_data.json"
    output_dir = project_root / "course_data" / "knowledge_graph"

    output_dir.mkdir(parents=True, exist_ok=True)
    graph_pkl = output_dir / "course_kg.pkl"

    print("="*80)
    print("UNSW Course Knowledge Graph Builder")
    print("="*80)
    print(f"Project root: {project_root}")
    print(f"Output directory: {output_dir}\n")

    # 检查输入文件
    if not graduation_req_dir.exists():
        print(f"[ERR] Graduation requirements not found: {graduation_req_dir}")
        return
    if not course_data_file.exists():
        print(f"[ERR] Course data not found: {course_data_file}")
        return

    # 构建图
    builder = KnowledgeGraphBuilder(
        graduation_req_dir=str(graduation_req_dir),
        course_data_file=str(course_data_file)
    )

    graph = builder.build_graph()

    # 保存整体知识图谱（pickle + graphml + metadata）
    builder.save_graph(str(graph_pkl))

    # 提取 COMPIH 专业子图（并扩展一跳邻接，使先修/解锁等关系出现）
    #subgraph = builder.extract_major_subgraph("COMPIH", str(output_dir), expand_one_hop=True)

    ## 如果提取成功，则进行可视化（注意：节点过多会采样）
    #if subgraph is not None:
    #    visualize_graph(subgraph, title="COMPIH major_code Knowledge Subgraph")

    print("\n" + "="*80)
    print("[OK] Knowledge Graph Build Complete!")
    print("="*80)


if __name__ == "__main__":
    main()