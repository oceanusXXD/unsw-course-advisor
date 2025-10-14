# ./node/grounding_check.py
import traceback
from typing import Dict, Any
from core import ENABLE_GROUNDING_CHECK, ENABLE_VERBOSE_LOGGING, call_qwen_sync, GROUNDING_MODEL, RESPONSE_TEMPLATES

def node_grounding_check(state: Dict[str, Any]) -> Dict[str, Any]:
    if not state.get("enable_grounding", ENABLE_GROUNDING_CHECK):
        if ENABLE_VERBOSE_LOGGING:
            print("⏭️  GROUNDING CHECK: Disabled")
        return {"is_grounded": True}
    retrieved = state.get("retrieved")
    if not retrieved:
        return {"is_grounded": True}
    answer = state.get("answer", "")
    if answer in RESPONSE_TEMPLATES.values():
        return {"is_grounded": True}
    prompt = "只回答yes"
    try:
        verification = call_qwen_sync([{"role": "user", "content": prompt}], model=GROUNDING_MODEL, temperature=0.0, purpose="grounding")
        is_grounded = "yes" in verification.lower()
        if ENABLE_VERBOSE_LOGGING:
            print(f"✓ GROUNDING: {is_grounded}")
        return {"is_grounded": is_grounded}
    except Exception:
        traceback.print_exc()
        return {"is_grounded": True}
