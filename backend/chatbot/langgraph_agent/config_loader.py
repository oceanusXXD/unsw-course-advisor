# backend/chatbot/langgraph_agent/config_loader.py

import importlib
import os
import sys
import yaml
from typing import Callable, Dict, Any, Optional, Type
from langgraph.graph import StateGraph, START, END

# 导入强类型 ChatState
from .state import ChatState

# node包路径设置 (保持不变)
NODE_PKG = "node"
AGENT_DIR = os.path.dirname(__file__)
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

def normalize_node_id(node_id: str) -> str:
    """标准化节点 ID，处理 __START__ 和 __END__"""
    if node_id == "__START__":
        return START
    if node_id == "__END__":
        return END
    return node_id

def _import_function(dotted_path: str) -> Callable:
    """按点分路径导入函数，并支持热重载 (保持不变)"""
    if dotted_path.startswith('.'):
        import inspect
        caller_frame = inspect.currentframe().f_back
        caller_module = caller_frame.f_globals['__name__']
        base_package = caller_module.rsplit('.', 1)[0]
        full_path = base_package + dotted_path
        module_path, func_name = full_path.rsplit('.', 1)
    else:
        module_path, func_name = dotted_path.rsplit('.', 1)

    if module_path in sys.modules:
        mod = importlib.reload(sys.modules[module_path])
    else:
        mod = importlib.import_module(module_path)
    return getattr(mod, func_name)

def _import_node_by_id(node_id: str) -> Callable:
    """按约定从 ./node/{node_id}.py 中导入函数 (保持不变)"""
    mod_name = f"{NODE_PKG}.{node_id}"
    try:
        if mod_name in sys.modules:
            mod = importlib.reload(sys.modules[mod_name])
        else:
            mod = importlib.import_module(mod_name)
    except ModuleNotFoundError as e:
        raise
    
    fn_name1 = f"node_{node_id}"
    if hasattr(mod, fn_name1):
        return getattr(mod, fn_name1)
    if hasattr(mod, "run"):
        return getattr(mod, "run")
    
    raise AttributeError(f"module {mod_name} does not expose 'node_{node_id}' or 'run'")

def load_graph_from_config(
    config_path: str,
    state_class: Type[ChatState],
    monitor_wrapper: Optional[Callable] = None
) -> StateGraph:
    """
    从 YAML 配置加载并构建 StateGraph (最终修复版)。
    """
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    graph = StateGraph(state_class)

    # 1. 添加所有节点
    for node_cfg in cfg.get("nodes", []):
        node_id = node_cfg["id"]
        if node_id in [START, END]:
            continue
        
        func_spec = node_cfg.get("function")
        fn: Optional[Callable] = None
        
        if func_spec:
            try:
                fn = _import_function(func_spec)
            except Exception as e:
                print(f"Warning: Failed to import function '{func_spec}' for node '{node_id}'. Error: {e}")
        
        if fn is None:
            try:
                fn = _import_node_by_id(node_id)
            except Exception as e:
                raise ImportError(f"无法加载节点 {node_id}: {e}") from e

        if node_cfg.get("monitor", False) and monitor_wrapper:
            fn = monitor_wrapper(node_id)(fn)

        graph.add_node(node_id, fn)

    # 2. 添加所有固定边 (普通 + 额外)
    all_edges = cfg.get("edges", []) + cfg.get("edges_extra", [])
    for e in all_edges:
        graph.add_edge(normalize_node_id(e["from"]), normalize_node_id(e["to"]))

    # 3.  关键修复：添加条件边，并支持 function 键
    for start_node, cond in (cfg.get("conditional_edges") or {}).items():
        mapping = cond.get("mapping", {})
        
        if "function" in cond:
            # 如果条件由一个外部函数定义
            cond_fn = _import_function(cond["function"])
            graph.add_conditional_edges(
                normalize_node_id(start_node),
                cond_fn,
                mapping
            )
        elif "key" in cond:
            # 如果条件由 state 中的一个 key 定义
            key = cond["key"]
            def make_key_fn(k: str) -> Callable[[ChatState], str]:
                return lambda state: state.get(k, "") # 兜底返回空字符串
            
            graph.add_conditional_edges(
                normalize_node_id(start_node),
                make_key_fn(key),
                mapping
            )

    # 4. 设置入口点
    entry_point = cfg.get("entry_point")
    if not entry_point:
        raise ValueError("YAML config must define an 'entry_point'.")
    graph.set_entry_point(normalize_node_id(entry_point))
    
    return graph