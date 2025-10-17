import uuid, traceback
from typing import Dict, Any
from core import TOOL_REGISTRY, RESPONSE_TEMPLATES, ENABLE_VERBOSE_LOGGING
from langchain_core.messages import ToolMessage

def node_tool_executor(state: Dict[str, Any]) -> Dict[str, Any]:
    tool_name = state.get("tool_name")
    tool_args = state.get("tool_args", {})  # 默认空字典
    tool_call_id = state.get("tool_call_id")
    
    # 防御性检查
    if not tool_name or tool_name not in TOOL_REGISTRY:
        error_msg = ToolMessage(content=f"Error: Tool '{tool_name}' not found.", 
                              tool_call_id=tool_call_id or "unknown")
        return {"messages": [error_msg], "answer": RESPONSE_TEMPLATES["error_tool"]}
    
    if "function" not in TOOL_REGISTRY[tool_name]:
        error_msg = ToolMessage(content=f"Error: Tool '{tool_name}' missing function implementation.", 
                              tool_call_id=tool_call_id or "unknown")
        return {"messages": [error_msg], "answer": RESPONSE_TEMPLATES["error_tool"]}

    try:
        tool_function = TOOL_REGISTRY[tool_name]["function"]
        if not isinstance(tool_args, dict):
            raise ValueError("tool_args must be a dictionary.")
            
        # 对于无参数工具确保传递空字典
        if not tool_args and TOOL_REGISTRY[tool_name].get("args") == {}:
            tool_args = {}
            
        result = tool_function(**tool_args)
        tool_msg = ToolMessage(content=result, tool_call_id=tool_call_id or f"call_{uuid.uuid4().hex[:16]}")
        
        if ENABLE_VERBOSE_LOGGING:
            print(f"✅ TOOL: {tool_name} executed successfully")
        return {"messages": [tool_msg]}
    except Exception:
        traceback.print_exc()
        error_msg = ToolMessage(content=f"Error executing tool {tool_name}: execution failed.", 
                              tool_call_id=tool_call_id or "unknown")
        return {"messages": [error_msg], "answer": RESPONSE_TEMPLATES["error_tool"]}