# backend/chatbot/view_profile.py

from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json
from typing import Any, Dict, List, Optional
from asgiref.sync import sync_to_async  # 新增

from chatbot.langgraph_agent.tools.filter_compiled_courses import filter_compiled_courses
from chatbot.langgraph_agent.tools.knowledge_graph_query import knowledge_graph_search
# 导入异步版本
from chatbot.langgraph_agent.node.save_memory import (
    load_memory_structure_async,
    save_memory_structure_async
)
from chatbot.langgraph_agent.core import ENABLE_VERBOSE_LOGGING

# ============ 工具与规范化（保持不变）============

def _get_user_id(request) -> str:
    x_user = request.headers.get("X-User-Id")
    if x_user:
        return str(x_user)

    try:
        if getattr(request, "user", None) and request.user.is_authenticated:
            return str(request.user.id)
    except Exception:
        pass

    x_sess = request.headers.get("X-Session-ID")
    if x_sess:
        return str(x_sess)

    return "anonymous"


def _resolve_tab_id(request, payload: Optional[dict], user_id: str) -> str:
    if isinstance(payload, dict):
        t = payload.get("tab_id")
        if isinstance(t, str) and t.strip():
            return t.strip()
    xtab = request.headers.get("X-Tab-Id")
    if xtab and xtab.strip():
        return xtab.strip()
    return f"tab_profile_{user_id}"


def _normalize_completed(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    out, seen = [], set()
    for item in raw:
        code = ""
        if isinstance(item, str):
            code = item
        elif isinstance(item, dict):
            code = (item.get("course_code") or item.get("code") or item.get("courseCode") or "").upper().strip()
        code = code.upper().strip()
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(code)
    return out


def _call_structured_tool(tool_obj, payload: dict):
    """兼容调用 @tool 包装过的工具"""
    if hasattr(tool_obj, "invoke"):
        return tool_obj.invoke(payload)
    if hasattr(tool_obj, "func"):
        return tool_obj.func(**payload)
    return tool_obj(**payload)


# 异步版本的工具调用包装器
async def _call_structured_tool_async(tool_obj, payload: dict):
    """
    异步调用工具（如果工具本身是同步的，使用 sync_to_async 包装）
    """
    # 检查是否是异步工具
    if hasattr(tool_obj, "ainvoke"):
        return await tool_obj.ainvoke(payload)
    
    # 如果是同步工具，包装为异步
    return await sync_to_async(_call_structured_tool)(tool_obj, payload)


async def _enrich_courses_async(course_codes: List[str]) -> List[Dict[str, Any]]:
    """
    异步版本：丰富课程信息
    """
    enriched = []
    for code in course_codes:
        if not code:
            continue
        enriched_course = {"course_code": code}
        try:
            # 使用异步工具调用
            info_result = await _call_structured_tool_async(
                knowledge_graph_search,
                {"action": "get_course_info", "course_code": code}
            )
            if info_result and info_result.get("status") == "ok" and info_result.get("result"):
                kg_data = info_result.get("result")
                enriched_course["title"] = kg_data.get("title", "N/A")
                enriched_course["overview"] = kg_data.get("overview", "")
                enriched_course["credit_points"] = kg_data.get("credit_points", "N/A")
                enriched_course["url"] = kg_data.get("url", "")
        except Exception as e:
            if ENABLE_VERBOSE_LOGGING:
                print(f"Error enriching course {code}: {e}")
        enriched.append(enriched_course)
    return enriched


def _build_filter_args(si: Dict[str, Any]) -> Dict[str, Any]:
    completed_course_codes = _normalize_completed(si.get("completed_courses", []))
    return {
        "completed_courses": completed_course_codes,
        "major_code": si.get("major_code"),
        "target_term": si.get("target_term"),
        "current_uoc": si.get("current_uoc", 0),
        "wam": si.get("wam"),
        "max_uoc_per_term": si.get("max_uoc_per_term", 20),
        "exclude_courses": si.get("exclude_courses"),
        "min_course_level": si.get("min_course_level"),
        "max_course_level": si.get("max_course_level"),
        "requirement_types": si.get("requirement_types"),
        "graduation_req_dir": si.get("graduation_req_dir"),
        "course_data_file": si.get("course_data_file"),
    }


def _validate(si: Dict[str, Any]) -> Optional[str]:
    if not si.get("major_code"):
        return "major_code is required"
    if not si.get("target_term"):
        return "target_term is required"
    return None


# ============ 长期记忆(JSON) 合并（保持不变）============

def _empty_profile():
    return {"identity": [], "goals": [], "preferences": [], "constraints": [], "skills": []}

def _ensure_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        return [v]
    return [str(v)]

def _parse_lts(raw: str) -> Dict[str, Any]:
    if not raw:
        return _empty_profile()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            out = _empty_profile()
            for k in out.keys():
                out[k] = _ensure_list(data.get(k))
            return out
    except Exception:
        pass
    pf = _empty_profile()
    pf["preferences"] = [str(raw)]
    return pf

def _merge_lists(a: List[str], b: List[str], limit: int = 10) -> List[str]:
    out, seen = [], set()
    for x in (a or []) + (b or []):
        s = str(x).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= limit:
            break
    return out

def _merge_long_term_summary(existing_raw: str, student_info: Dict[str, Any]) -> str:
    base = _parse_lts(existing_raw)

    identity_new = []
    if student_info.get("major_code"):
        identity_new.append(f"专业: {student_info['major_code']}")
    if student_info.get("degree_level"):
        identity_new.append(f"学位层次: {student_info['degree_level']}")
    if student_info.get("target_term"):
        identity_new.append(f"目标学期: {student_info['target_term']}")

    preferences_new = []
    req = student_info.get("requirement_types")
    if isinstance(req, list) and req:
        preferences_new.append("需求类型: " + ", ".join(req))

    constraints_new = []
    if student_info.get("max_uoc_per_term"):
        constraints_new.append(f"单学期最大UOC: {student_info['max_uoc_per_term']}")
    if student_info.get("current_uoc") is not None:
        constraints_new.append(f"当前UOC: {student_info['current_uoc']}")
    if student_info.get("wam") is not None:
        constraints_new.append(f"WAM: {student_info['wam']}")

    skills_new = _normalize_completed(student_info.get("completed_courses", []))

    merged = {
        "identity": _merge_lists(base.get("identity"), identity_new, limit=10),
        "goals": _merge_lists(base.get("goals"), _ensure_list(student_info.get("goals")), limit=10),
        "preferences": _merge_lists(base.get("preferences"), preferences_new, limit=20),
        "constraints": _merge_lists(base.get("constraints"), constraints_new, limit=20),
        "skills": _merge_lists(base.get("skills"), skills_new, limit=100),
    }
    return json.dumps(merged, ensure_ascii=False, separators=(",", ":"))


# ============ 异步写入内存 ============

async def _write_profile_to_memory_async(
    user_id: str,
    tab_id: str,
    student_info: Dict[str, Any],
    recommendation: Dict[str, Any],
    all_major_courses: Optional[List[str]] = None,
    enable_choose_courses: Optional[List[str]] = None
) -> None:
    """
    异步版本：将学生档案和硬规则结果写入 memory
    """
    # 使用异步加载
    mem = await load_memory_structure_async(user_id, tab_id)

    codes = _normalize_completed(student_info.get("completed_courses", []))
    degree_level = student_info.get("degree_level")

    text_query = (
        f"已修: {', '.join(codes)}；"
        f"专业: {student_info.get('major_code','')}；"
        f"目标学期: {student_info.get('target_term','')}；"
        f"WAM: {student_info.get('wam', '')}；"
        f"当前UOC: {student_info.get('current_uoc','')}"
    )
    if degree_level:
        text_query += f"；学位层次: {degree_level}"

    mem.setdefault("recent_conversations", []).append({
        "Q": text_query,
        "A": "学生档案信息已更新（用于后续对话推断）。",
        "T": timezone.now().isoformat()
    })

    if all_major_courses:
        mem["recent_conversations"].append({
            "Q": "系统：all_major_courses 已保存",
            "A": json.dumps({"all_major_courses": all_major_courses}, ensure_ascii=False),
            "T": timezone.now().isoformat()
        })

    if enable_choose_courses:
        top_show = 60
        shown = ", ".join(enable_choose_courses[:top_show])
        rest = len(enable_choose_courses) - top_show
        suffix = f"（其余 {rest} 门略）" if rest > 0 else ""
        mem["recent_conversations"].append({
            "Q": "系统：enable_choose_courses 已保存",
            "A": json.dumps({"enable_choose_courses": enable_choose_courses, "preview": f"{shown}{suffix}"}, ensure_ascii=False),
            "T": timezone.now().isoformat()
        })

    mem["recent_conversations"].append({
        "Q": "系统：已完成档案硬规则筛选与预推荐。",
        "A": f"推荐结果快照（只存摘要）：{json.dumps({'keys': list((recommendation or {}).keys())}, ensure_ascii=False)}",
        "T": timezone.now().isoformat()
    })

    existing = mem.get("long_term_summary", "") or ""
    mem["long_term_summary"] = _merge_long_term_summary(existing, student_info)

    if ENABLE_VERBOSE_LOGGING:
        print(f"\n[OK] [_write_profile_to_memory_async] 写入 memory for {user_id}/{tab_id}:")
        print(f"   - completed_courses: {len(codes)}")
        print(f"   - all_major_courses: {len(all_major_courses) if all_major_courses else 0}")
        print(f"   - enable_choose_courses: {len(enable_choose_courses) if enable_choose_courses else 0}")
        print(f"   - long_term_summary length: {len(mem['long_term_summary'])}")

    # 使用异步保存
    await save_memory_structure_async(user_id, tab_id, mem)


# ============ 异步视图 ============

@csrf_exempt
async def chatbot_profile(request):  # async def
    """
    异步版本：学生档案接口
    """
    if request.method == "GET":
        user_id = _get_user_id(request)
        payload = None
        try:
            # 异步读取请求体
            body = request.body
            if body:
                payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = None
        
        tab_id = _resolve_tab_id(request, payload, user_id)

        # 异步加载记忆
        mem = await load_memory_structure_async(user_id, tab_id)
        recent = mem.get("recent_conversations", []) or []
        last_profile_ev = None
        for e in reversed(recent):
            if e.get("Q", "").startswith("系统："):
                last_profile_ev = e
                break
        
        return JsonResponse({
            "status": "ok",
            "tab_id": tab_id,
            "memory_excerpt": (mem.get("long_term_summary", "") or "")[-800:],
            "last_profile_event": last_profile_ev
        }, status=200)

    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "POST"])

    # POST
    try:
        # 异步读取请求体
        body = request.body
        payload = json.loads(body.decode("utf-8")) if body else {}
    except Exception:
        return JsonResponse({"status": "error", "error": "Invalid JSON body"}, status=400)

    user_id = _get_user_id(request)
    tab_id = _resolve_tab_id(request, payload, user_id)

    student_info = payload.get("student_info") if isinstance(payload, dict) else None
    if not isinstance(student_info, dict):
        student_info = dict(payload)

    err = _validate(student_info)
    if err:
        return JsonResponse({"status": "error", "error": err}, status=400)

    normalized_codes = _normalize_completed(student_info.get("completed_courses", []))
    
    # 异步丰富课程信息
    enriched_courses_for_frontend = await _enrich_courses_async(normalized_codes)
    student_info["completed_courses"] = normalized_codes

    # 调用硬规则工具
    try:
        args = _build_filter_args(student_info)
        # 异步调用工具
        filt = await _call_structured_tool_async(filter_compiled_courses, args)
    except Exception as e:
        return JsonResponse({"status": "error", "error": f"filter_compiled_courses failed: {e}"}, status=500)
    
    if not isinstance(filt, dict) or filt.get("status") != "ok":
        return JsonResponse({"status": "error", "error": filt.get("error", "unknown error")}, status=400)
    
    recommendation = filt.get("result") or {}
    all_major_courses_list = recommendation.get("all_major_courses", []) or []
    enable_choose_courses_raw = recommendation.get("enable_choose_courses", []) or []

    enable_choose_courses_codes = []
    if enable_choose_courses_raw:
        for course in enable_choose_courses_raw:
            if isinstance(course, dict):
                code = course.get("code") or course.get("course_code")
                if code:
                    enable_choose_courses_codes.append(str(code))
            elif isinstance(course, str):
                enable_choose_courses_codes.append(course)

    result = {
        "student_info": {**student_info, "completed_courses": enriched_courses_for_frontend},
        "recommendation": recommendation,
        "updated_at": timezone.now().isoformat(),
        "tab_id": tab_id,
    }

    # 异步存入 memory
    try:
        await _write_profile_to_memory_async(
            user_id,
            tab_id,
            student_info,
            result["recommendation"],
            all_major_courses=all_major_courses_list,
            enable_choose_courses=enable_choose_courses_codes
        )
    except Exception as e:
        return JsonResponse({"status": "error", "error": f"save_memory failed: {e}"}, status=500)

    return JsonResponse({"status": "ok", "profile": result}, status=200)