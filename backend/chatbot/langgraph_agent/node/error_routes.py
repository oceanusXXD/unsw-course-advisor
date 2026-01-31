# backend/chatbot/langgraph_agent/node/error_routes.py

from typing import Dict, Any
from ..state import ChatState

def after_generate(state: ChatState) -> str:
    # 有错误就结束，否则去 grounding_check
    return "__END__" if state.get("error") else "grounding_check"

def after_retrieve(state: ChatState) -> str:
    # 有错误就结束，否则去 evaluate_retrieval
    return "__END__" if state.get("error") else "evaluate_retrieval"