# ./node/finalize.py
import json
from typing import Dict, Any
from core import ENABLE_SUGGESTIONS, GROUNDING_MODEL, call_qwen_sync, MAX_MEMORY_MESSAGES

def node_finalize(state: Dict[str, Any]) -> Dict[str, Any]:
    final_answer = state.get("answer", "抱歉，我无法回答。")
    is_grounded = state.get("is_grounded", True)
    route = state.get("route")
    suggested_questions = []
    if state.get("enable_suggestions", ENABLE_SUGGESTIONS):
        try:
            messages = state.get("messages", [])
            history_str = "\n".join([f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in messages[-5:]])
            prompt = (f"基于以下对话，请生成 2-3 个用户可能感兴趣的相关问题，用于引导对话。请只返回一个JSON列表。\\n\\n### 对话历史 ###\\n{history_str}\\n\\n最终回答: {final_answer[:200]}")
            suggestions_str = call_qwen_sync([{"role": "user", "content": prompt}], model=GROUNDING_MODEL, temperature=0.5, purpose="suggestions")
            suggested_questions = json.loads(suggestions_str)
        except Exception:
            pass
    retrieved = state.get("retrieved") or []
    sources = [{"title": d.get("title", d.get("course_code", "未知")), "source": d.get("source_file", d.get("url", "未知")), "score": d.get("_score")} for d in retrieved]
    final_output = {"answer": final_answer, "sources": sources, "suggested_questions": suggested_questions, "route_decision": route, "is_grounded": is_grounded}
    mem = state.get("memory", {}) or {}
    current_messages = state.get("messages", [])
    updated_messages = current_messages + [{"role": "assistant", "content": final_answer}]
    if len(updated_messages) > MAX_MEMORY_MESSAGES:
        updated_messages = updated_messages[-MAX_MEMORY_MESSAGES:]
    mem["history"] = updated_messages
    if final_answer and any(k in final_answer for k in ["记住", "保存偏好", "我叫", "我的名字"]):
        current_summary = mem.get("summary", "")
        mem["summary"] = (current_summary + "\n" + final_answer)[:2000]
    return {"final_output": final_output, "memory": mem}
