"""
Data cleaning script for UNSW graduation requirements data
Focuses on extracting curriculum structure showing course requirements and options
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

def extract_course_from_relationship(relationship: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract a single course from a relationship entry
    
    Args:
        relationship: A relationship dictionary from curriculum structure
        
    Returns:
        Cleaned course information or None if inactive
    """
    # Skip inactive courses
    if relationship.get("academic_item_active") != "true":
        return None
    
    # Skip if state is not 'show'
    if relationship.get("academic_item_state") != "show":
        return None
    
    course = {
        "code": relationship.get("academic_item_code", ""),
        "name": relationship.get("academic_item_name", ""),
        "credit_points": relationship.get("academic_item_credit_points", ""),
        "type": relationship.get("academic_item_type", {}).get("label", ""),
        "url": relationship.get("academic_item_url", ""),
        "version": relationship.get("academic_item_version_name", ""),
        "parent_connector": relationship.get("parent_connector", {}).get("label", ""),
        "exclude": relationship.get("exclude", "false"),
        "order": relationship.get("order", "")
    }
    
    return course


def extract_requirement_group(container: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract a requirement group (container) with all its courses
    
    Args:
        container: A curriculum structure container
        
    Returns:
        Cleaned requirement group with courses
    """
    group = {
        # Group identification
        "title": container.get("title", ""),
        "description": container.get("description", ""),
        "preface": container.get("preface", ""),
        "footnote": container.get("footnote", ""),
        
        # Credit requirements
        "credit_points": container.get("credit_points", ""),
        "credit_points_max": container.get("credit_points_max", ""),
        
        # Group classification
        "vertical_grouping_label": container.get("vertical_grouping", {}).get("label", ""),
        "vertical_grouping_value": container.get("vertical_grouping", {}).get("value", ""),
        "horizontal_grouping_label": container.get("horizontal_grouping", {}).get("label", ""),
        "horizontal_grouping_value": container.get("horizontal_grouping", {}).get("value", ""),
        
        # Logic
        "parent_connector": container.get("parent_connector", {}).get("label", ""),
        "set_based": container.get("set_based", ""),
        "map_type": container.get("map_type", ""),
        
        # Order
        "order": container.get("order", ""),
        
        # Courses in this group
        "courses": [],
        
        # Dynamic queries (if any)
        "dynamic_queries": []
    }
    
    # Extract all courses from relationship array
    if "relationship" in container and container["relationship"]:
        for rel in container["relationship"]:
            course = extract_course_from_relationship(rel)
            if course:
                group["courses"].append(course)
    
    # Extract dynamic queries (for complex requirements)
    if "dynamic_relationship" in container and container["dynamic_relationship"]:
        for dyn_rel in container["dynamic_relationship"]:
            query = {
                "query": dyn_rel.get("dynamic_query", ""),
                "description": dyn_rel.get("description", ""),
                "parent_connector": dyn_rel.get("parent_connector", {}).get("label", ""),
                "credit_points": dyn_rel.get("credit_points", "")
            }
            group["dynamic_queries"].append(query)
    
    # Check for nested containers (sub-groups)
    if "container" in container and container["container"]:
        group["sub_groups"] = []
        for sub_container in container["container"]:
            sub_group = extract_requirement_group(sub_container)
            group["sub_groups"].append(sub_group)
    
    return group


def clean_graduation_requirements(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean graduation requirements data - extract key information
    
    Args:
        data: Raw specialisation/program data
        
    Returns:
        Cleaned data with focus on curriculum structure
    """
    
    cleaned = {
        # Basic identification
        "code": data.get("code", ""),
        "cl_code": data.get("cl_code", ""),
        "title": data.get("title", ""),
        
        # Type
        "academic_item_type": data.get("academic_item_type", ""),
        "content_type": data.get("contentTypeLabel", ""),
        "subclass": data.get("subclass", {}).get("label", ""),
        
        # Academic info
        "total_credit_points": data.get("credit_points", ""),
        "study_level": data.get("study_level_single", {}).get("label", ""),
        "implementation_year": data.get("implementation_year", ""),
        "version": data.get("version_name", ""),
        "status": data.get("status", {}).get("label", ""),
        
        # Organization
        "faculty": data.get("parent_academic_org", {}).get("value", ""),
        "school": data.get("academic_org", {}).get("value", ""),
        
        # Brief description
        "structure_summary": data.get("structure_summary", ""),
        
        # Available in programs
        "available_in_programs": [],
        
        # MAIN DATA: Curriculum structure with course requirements
        "curriculum_structure": None
    }
    
    # Extract available programs
    if "available_in_programs2021plus" in data:
        for prog in data["available_in_programs2021plus"]:
            if prog.get("assoc_state") == "show" and prog.get("assoc_active") == "true":
                cleaned["available_in_programs"].append({
                    "code": prog.get("assoc_code", ""),
                    "title": prog.get("assoc_title", ""),
                    "award": prog.get("assoc_award_single", ""),
                    "credit_points": prog.get("assoc_credit_points", ""),
                    "campus": prog.get("assoc_campus", ""),
                    "duration": prog.get("assoc_duration_hb_display", ""),
                    "url": prog.get("assoc_url", "")
                })
    
    # Extract curriculum structure - THE CORE DATA
    if "curriculumStructure" in data:
        curr_struct = data["curriculumStructure"]
        
        curriculum = {
            # Structure metadata
            "version": curr_struct.get("curriculum_structure", {}).get("value", ""),
            "name": curr_struct.get("name", ""),
            "total_credit_points": curr_struct.get("credit_points", ""),
            "implementation_year": curr_struct.get("implementation_year", ""),
            "relationship_type": curr_struct.get("relationship_type", {}).get("label", ""),
            
            # Requirement groups (containers)
            "requirement_groups": []
        }
        
        # Extract all requirement groups from container array
        if "container" in curr_struct:
            for container in curr_struct["container"]:
                group = extract_requirement_group(container)
                curriculum["requirement_groups"].append(group)
        
        cleaned["curriculum_structure"] = curriculum
    
    return cleaned


def generate_summary_statistics(cleaned_data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate summary statistics from cleaned data
    
    Args:
        cleaned_data_list: List of all cleaned specialisation data
        
    Returns:
        Summary statistics dictionary
    """
    stats = {
        "total_specialisations": len(cleaned_data_list),
        "by_type": {},
        "by_study_level": {},
        "by_faculty": {},
        "total_requirement_groups": 0,
        "total_courses": 0,
        "course_types": {},
        "group_types": {}
    }
    
    for spec in cleaned_data_list:
        # Count by type
        spec_type = spec.get("content_type", "Unknown")
        stats["by_type"][spec_type] = stats["by_type"].get(spec_type, 0) + 1
        
        # Count by study level
        level = spec.get("study_level", "Unknown")
        stats["by_study_level"][level] = stats["by_study_level"].get(level, 0) + 1
        
        # Count by faculty
        faculty = spec.get("faculty", "Unknown")
        stats["by_faculty"][faculty] = stats["by_faculty"].get(faculty, 0) + 1
        
        # Count requirement groups and courses
        if spec.get("curriculum_structure") and spec["curriculum_structure"].get("requirement_groups"):
            for group in spec["curriculum_structure"]["requirement_groups"]:
                stats["total_requirement_groups"] += 1
                
                # Count group types
                group_type = group.get("vertical_grouping_value", "Unknown")
                stats["group_types"][group_type] = stats["group_types"].get(group_type, 0) + 1
                
                # Count courses
                courses = group.get("courses", [])
                stats["total_courses"] += len(courses)
                
                for course in courses:
                    course_type = course.get("type", "Unknown")
                    stats["course_types"][course_type] = stats["course_types"].get(course_type, 0) + 1
    
    return stats


def clean_all_files(input_dir: str, output_dir: str):
    """
    Clean all graduation requirements JSON files
    
    Args:
        input_dir: Directory containing raw data files
        output_dir: Directory to save cleaned data
    """
    
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Processing statistics
    stats = {
        "total_files": 0,
        "success": 0,
        "errors": 0,
        "error_files": []
    }
    
    all_cleaned_data = []
    
    # Process each JSON file
    print("Processing files...")
    for json_file in sorted(input_path.glob("*.json")):
        stats["total_files"] += 1
        
        try:
            # Read raw data
            with open(json_file, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            
            # Clean data
            cleaned_data = clean_graduation_requirements(raw_data)
            
            # Save individual cleaned file
            output_file = output_path / f"cleaned_{json_file.name}"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
            
            all_cleaned_data.append(cleaned_data)
            
            stats["success"] += 1
            print(f"[OK] {json_file.name}")
            
        except Exception as e:
            stats["errors"] += 1
            stats["error_files"].append({
                "file": json_file.name,
                "error": str(e)
            })
            print(f"[X] {json_file.name}: {e}")
    
    # Save combined file
    print("\nSaving combined data...")
    combined_file = output_path / "all_graduation_requirements.json"
    with open(combined_file, 'w', encoding='utf-8') as f:
        json.dump(all_cleaned_data, f, indent=2, ensure_ascii=False)
    
    # Generate summary statistics
    print("Generating statistics...")
    summary_stats = generate_summary_statistics(all_cleaned_data)
    
    # Save statistics
    stats_file = output_path / "data_statistics.json"
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(summary_stats, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n" + "="*70)
    print("CLEANING SUMMARY")
    print("="*70)
    print(f"Files processed: {stats['total_files']}")
    print(f"Successfully cleaned: {stats['success']}")
    print(f"Errors: {stats['errors']}")
    
    print("\nDATA STATISTICS")
    print("="*70)
    print(f"Total specialisations/programs: {summary_stats['total_specialisations']}")
    print(f"Total requirement groups: {summary_stats['total_requirement_groups']}")
    print(f"Total courses listed: {summary_stats['total_courses']}")
    
    print(f"\nBy content type:")
    for type_name, count in sorted(summary_stats['by_type'].items()):
        print(f"  - {type_name}: {count}")
    
    print(f"\nBy study level:")
    for level, count in sorted(summary_stats['by_study_level'].items()):
        print(f"  - {level}: {count}")
    
    print(f"\nRequirement group types:")
    for group_type, count in sorted(summary_stats['group_types'].items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  - {group_type}: {count}")
    
    if stats["error_files"]:
        print(f"\nFiles with errors:")
        for error in stats["error_files"]:
            print(f"  - {error['file']}: {error['error']}")
    
    # Save processing report
    report_file = output_path / "_processing_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    print(f"\nOutput files:")
    print(f"  - Individual files: {output_path}/cleaned_*.json")
    print(f"  - Combined data: {combined_file}")
    print(f"  - Statistics: {stats_file}")
    print(f"  - Processing report: {report_file}")


def main():
    """Main execution function"""
    
    # Define paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    input_dir = project_root / "course_data" / "graduation_requests_data"
    output_dir = project_root / "course_data" / "cleaned_graduation_requirements"
    
    print("="*70)
    print("UNSW GRADUATION REQUIREMENTS DATA CLEANER")
    print("="*70)
    print(f"Input:  {input_dir}")
    print(f"Output: {output_dir}")
    print("="*70 + "\n")
    
    # Validate input directory
    if not input_dir.exists():
        print(f"[ERR] Error: Input directory not found!")
        print(f"   Looking for: {input_dir}")
        return
    
    # Count input files
    json_files = list(input_dir.glob("*.json"))
    if not json_files:
        print(f"[ERR] No JSON files found in {input_dir}")
        return
    
    print(f"Found {len(json_files)} JSON files\n")
    
    # Start cleaning
    clean_all_files(str(input_dir), str(output_dir))
    
    print("\n" + "="*70)
    print("[OK] CLEANING COMPLETE")
    print("="*70)


if __name__ == "__main__":
    main()