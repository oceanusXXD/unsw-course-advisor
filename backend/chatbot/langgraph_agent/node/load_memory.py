# backend/chatbot/langgraph_agent/node/load_memory.py

import os
import json
import re
from typing import Dict, Any, List
from datetime import datetime, timedelta

# 导入强类型定义
from ..schemas import Memory, StudentInfo, ConversationTurn
from ..state import ChatState
from chatbot.db_manager import load_chat_messages_from_db
# 导入核心功能和 save_memory 中的函数
from ..core import ENABLE_VERBOSE_LOGGING, MAX_HISTORY_LENGTH, KEEP_FULL_RECENT
from .save_memory import load_memory_structure_async
HISTORY_K = 20

async def node_load_memory(state: ChatState) -> Dict[str, Any]:
    """
    [异步版本] 加载用户记忆（仅加载最近 k 条对话，防止上下文溢出）
    """
    user_id = state.get("user_id", "anonymous")
    tab_id = state.get("tab_id", "default_tab")

    if ENABLE_VERBOSE_LOGGING:
        print("\n" + "" * 40)
        print("【Load Memory 节点】(异步版本 + 历史截断)")
        print(f"   - user_id: {user_id}")
        print(f"   - tab_id: {tab_id}")
        print(f"   - limit k: {HISTORY_K}")
        print("" * 40 + "\n")

    # 1) 仅加载最近 k 条（时间正序）
    recent_convs: List[ConversationTurn] = await load_chat_messages_from_db(user_id, tab_id, k=HISTORY_K)

    # 2) 加载长期摘要/归档索引
    raw_memory: Memory = await load_memory_structure_async(user_id, tab_id)

    # 3) 用“截断后的对话”构建 memory（如果还想二次采样就调用 _extract_clean_conversations）
    #    如果你希望严格“最多 k 条”，可以直接 recent_convs 原样返回（如下）
    recent_for_llm = recent_convs  # 或 _extract_clean_conversations(recent_convs)

    cleaned_memory: Memory = {
        "long_term_summary": raw_memory.get("long_term_summary", ""),
        "recent_conversations": recent_for_llm,  # [OK] 用截断后的内容
        "archived_summaries": raw_memory.get("archived_summaries", []),
    }

    # 4) Student Info
    student_info: StudentInfo = _extract_student_info(cleaned_memory)

    if ENABLE_VERBOSE_LOGGING:
        print(f"\n[OK] [Load Memory] 已应用截断: recent={len(cleaned_memory['recent_conversations'])} 条")
        print(f"   - major_code: {student_info.get('major_code')}")
        print(f"   - completed_courses: {student_info.get('completed_courses')}")
        print(f"   - wam: {student_info.get('wam')}")
        print(f"   - all_major_courses 数量: {len(student_info.get('all_major_courses', []))}\n")

    return {
        "memory": cleaned_memory,
        "student_info": student_info
    }

# ========== 核心修复：新增函数 ==========

def _extract_from_recent_conversations(convs: List[ConversationTurn], info: StudentInfo) -> StudentInfo:
    """从 recent_conversations 中提取结构化数据"""
    for conv in convs:
        q = conv.get("Q", "")
        a = conv.get("A", "")
        
        # 提取专业代码
        if "专业:" in q or "major_code:" in q.lower():
            major_match = re.search(r'专业[:：]\s*([A-Z0-9]{2,10})', q)
            if major_match:
                info["major_code"] = major_match.group(1).strip()
        
        # 提取已修课程
        if "已修:" in q:
            courses = re.findall(r'[A-Z]{4}\d{4}', q)
            if courses:
                info["completed_courses"] = sorted(list(set(courses)))
        
        # 提取 WAM
        if "WAM:" in q or "wam:" in q.lower():
            wam_match = re.search(r'(?:WAM|wam)[:：]\s*(\d+\.?\d*)', q)
            if wam_match:
                try:
                    info["wam"] = float(wam_match.group(1))
                except:
                    pass
        
        # 提取目标学期
        if "目标学期:" in q:
            term_match = re.search(r'目标学期[:：]\s*(\d{4}T\d)', q)
            if term_match:
                info["target_term"] = term_match.group(1).strip()
        
        # 提取当前 UOC
        if "当前UOC:" in q or "current_uoc:" in q.lower():
            uoc_match = re.search(r'(?:当前UOC|current_uoc)[:：]\s*(\d+)', q, re.IGNORECASE)
            if uoc_match:
                try:
                    info["current_uoc"] = int(uoc_match.group(1))
                except:
                    pass
        
        # [OK] 新增：提取 degree_level
        if "学位层次:" in q or "degree_level:" in q.lower():
            degree_match = re.search(r'(?:学位层次|degree_level)[:：]\s*(UG|PG)', q, re.IGNORECASE)
            if degree_match:
                level = degree_match.group(1).upper()
                if level in ("UG", "PG"):
                    info["degree_level"] = level
        
        # [OK] [OK] [OK] 修复：提取 all_major_courses（增加调试）
        if "系统：all_major_courses 已保存" in q:
            try:
                data = json.loads(a)
                if "all_major_courses" in data:
                    courses_list = data["all_major_courses"]
                    info["all_major_courses"] = courses_list
                    # [OK] 调试输出
                    if ENABLE_VERBOSE_LOGGING:
                        print(f"[DEBUG _extract_from_recent_conversations] 成功提取 all_major_courses: {len(courses_list)} 门")
                else:
                    if ENABLE_VERBOSE_LOGGING:
                        print(f"[DEBUG _extract_from_recent_conversations] JSON 中没有 all_major_courses 字段")
                        print(f"  实际字段: {list(data.keys())}")
            except Exception as e:
                # [OK] 不要吞掉异常，要打印出来！
                if ENABLE_VERBOSE_LOGGING:
                    print(f"[ERROR _extract_from_recent_conversations] 提取 all_major_courses 失败: {e}")
                    print(f"  Q: {q}")
                    print(f"  A: {a[:200]}...")
                import traceback
                traceback.print_exc()
        
        # [OK] 提取当前可选课程
        if "系统：enable_choose_courses 已保存" in q:
            try:
                data = json.loads(a)
                if "enable_choose_courses" in data:
                    info["current_enable_choose_courses"] = data["enable_choose_courses"]
                    if ENABLE_VERBOSE_LOGGING:
                        print(f"[DEBUG _extract_from_recent_conversations] 成功提取 enable_choose_courses: {len(data['enable_choose_courses'])} 门")
            except Exception as e:
                if ENABLE_VERBOSE_LOGGING:
                    print(f"[ERROR _extract_from_recent_conversations] 提取 enable_choose_courses 失败: {e}")
    
    return info


# ========== 核心修复：修改函数 ==========

def _extract_student_info(memory: Memory) -> StudentInfo:
    """从 memory 中提取结构化的学生信息，返回强类型 StudentInfo"""
    
    import re

    # [OK] 合并 long_term_summary 和 recent_conversations 的内容
    long_term = memory.get("long_term_summary", "")
    recent_convs = memory.get("recent_conversations", [])
    
    # 初始化符合 StudentInfo 契约的字典
    info: StudentInfo = {
        "major_code": "",
        "completed_courses": [],
        "all_major_courses": [],
        "raw_summary": long_term
    }
    
    # [OK] 优先从 recent_conversations 中提取结构化数据
    info = _extract_from_recent_conversations(recent_convs, info)
    
    # [OK] 拼接所有文本用于正则提取
    combined_text = long_term + "\n"
    for conv in recent_convs:
        combined_text += conv.get("Q", "") + "\n" + conv.get("A", "") + "\n"
    
    # === 提取专业 ===
    if not info["major_code"]:
        major_patterns = [
            r'专业[:：]\s*([A-Z0-9]{2,10})',
            r'major_code[:：]\s*([A-Z0-9]{2,10})'
        ]
        for pattern in major_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                info["major_code"] = match.group(1).strip()
                break
    
    # === 提取已修课程 ===
    if not info["completed_courses"]:
        course_patterns = [
            r'已修[:：]?\s*((?:[A-Z]{4}\d{4}(?:[,，、\s])?)+)',
            r'完成[:：]?\s*((?:[A-Z]{4}\d{4}(?:[,，、\s])?)+)'
        ]
        completed_courses = set()
        for pattern in course_patterns:
            matches = re.finditer(pattern, combined_text)
            for match in matches:
                completed_courses.update(re.findall(r'[A-Z]{4}\d{4}', match.group(1)))
        if completed_courses:
            info["completed_courses"] = sorted(list(completed_courses))
    
    # === 提取年级 ===
    if "year" not in info or info.get("year") is None:
        year_patterns = [r'(?:大|year)\s*([一二三四五1-5])']
        year_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}
        for pattern in year_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                year_str = match.group(1)
                info["year"] = year_map.get(year_str, int(year_str) if year_str.isdigit() else None)
                break

    # [OK] === 提取学历层次（本科 / 研究生） ===
    if "degree_level" not in info or not info.get("degree_level"):
        # 常见关键词：本科、本科生、undergraduate、UG；研究生、硕士、postgraduate、PG
        ug_keywords = ["本科", "本科生", "undergraduate", "UG"]
        pg_keywords = ["研究生", "硕士", "研究", "postgraduate", "PG", "master"]

        text_lower = combined_text.lower()

        if any(kw.lower() in text_lower for kw in pg_keywords):
            info["degree_level"] = "PG"
        elif any(kw.lower() in text_lower for kw in ug_keywords):
            info["degree_level"] = "UG"
        else:
            # 没明确提到则不设置（留空）
            info["degree_level"] = None

    # === 提取 WAM/GPA ===
    if "wam" not in info or info.get("wam") is None:
        wam_patterns = [r'(?:wam|WAM)[:：]\s*(\d+\.?\d*)']
        for pattern in wam_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                try:
                    info["wam"] = float(match.group(1))
                    break
                except:
                    pass

    # === 提取其他可选信息 ===
    if any(kw in combined_text for kw in ["新生", "第一年", "first year", "freshman"]):
        info["is_freshman"] = True

    goal_keywords = ["想学", "想选", "目标", "打算", "plan to", "want to"]
    for kw in goal_keywords:
        match = re.search(rf'{kw}[:：]?\s*([^。\n]+)', combined_text)
        if match:
            info["goals"] = match.group(1).strip()
            break

    return info


# ========== 以下函数保持不变 ==========

def _extract_clean_conversations(raw_history: List[ConversationTurn]) -> List[ConversationTurn]:
    """智能采样对话，输入输出都符合 ConversationTurn 列表"""
    if not raw_history:
        return []
    
    sorted_history = sorted(raw_history, key=lambda x: x.get('T', ''), reverse=True)
    
    if len(sorted_history) <= KEEP_FULL_RECENT:
        return _clean_entries(sorted_history)
    
    recent_n = _clean_entries(sorted_history[:KEEP_FULL_RECENT])
    older_entries = sorted_history[KEEP_FULL_RECENT:MAX_HISTORY_LENGTH + KEEP_FULL_RECENT]
    important = _filter_important_conversations(older_entries, recent_n)
    
    return list(reversed(important + recent_n))


def _filter_important_conversations(entries: List[ConversationTurn], recent_entries: List[ConversationTurn]) -> List[ConversationTurn]:
    """筛选重要对话"""
    important = []
    
    recent_topics = set()
    for entry in recent_entries:
        q = entry.get("Q", "").lower()
        a = entry.get("A", "").lower()
        combined = q + " " + a
        if "wam" in combined or "gpa" in combined:
            recent_topics.add("academic_performance")
        if "新生" in combined or "第一年" in combined:
            recent_topics.add("freshman")
        if "专业" in combined or "major_code" in combined:
            recent_topics.add("major_code")
    
    for entry in entries:
        query = entry.get("Q", "")
        answer = entry.get("A", "")
        combined = (query + " " + answer).lower()
        
        skip = False
        if "freshman" in recent_topics and ("wam" in combined or "gpa" in combined):
            skip = True
        if "major_code" in recent_topics and "专业" in combined and _is_old_entry(entry, days=7):
            skip = True
        
        if skip:
            continue
        
        if any(keyword in combined for keyword in ["我叫", "我是", "名字"]):
            if not _is_old_entry(entry, days=1):
                important.append(_clean_entry(entry))
        elif entry.get("route") == "retrieve_rag":
            important.append(_clean_entry(entry, max_answer_length=100))
        elif any(keyword in combined for keyword in ["选", "决定", "报名", "推荐", "建议"]):
            important.append(_clean_entry(entry))
    
    return important[:10]


def _clean_entries(entries: List[ConversationTurn]) -> List[ConversationTurn]:
    """批量清理条目"""
    return [_clean_entry(e) for e in entries if e.get("Q") and e.get("A")]


def _clean_entry(entry: ConversationTurn, max_answer_length: int = 200) -> ConversationTurn:
    """清理单个条目"""
    return {
        "Q": entry.get("Q", ""),
        "A": _truncate_answer(entry.get("A", ""), max_answer_length),
        "T": entry.get("T", "")[:10] if entry.get("T") else ""
    }


def _is_old_entry(entry: dict, days: int = 7) -> bool:
    """检查条目是否过时"""
    timestamp_str = entry.get("T", "")
    if not timestamp_str:
        return False
    try:
        entry_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        age = datetime.now(entry_time.tzinfo) - entry_time
        return age.days > days
    except:
        return False


def _truncate_answer(answer: str, max_length: int = 200) -> str:
    """截断过长答案"""
    if not answer or answer == "<STREAMING_ANSWER_NOT_SAVED>":
        return ""
    if len(answer) <= max_length:
        return answer
    truncated = answer[:max_length]
    last_period = truncated.rfind("。")
    if last_period > max_length * 0.7:
        return truncated[:last_period + 1]
    return truncated + "..."