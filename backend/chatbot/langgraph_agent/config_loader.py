# config_loader.py
import importlib
import os
import sys
import yaml
from types import ModuleType
from typing import Callable, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END

# node package directory (相对于本文件)
NODE_PKG = "node"
NODE_DIR = os.path.join(os.path.dirname(__file__), NODE_PKG)
# 把 node 目录加入 sys.path（便于 import node.xxx）
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

def _import_function(dotted_path: str) -> Callable:
    """
    尝试直接 import 一个点分路径（module.func）。
    会抛异常给调用者。
    """
    module_name, func_name = dotted_path.rsplit(".", 1)
    mod = importlib.import_module(module_name)
    return getattr(mod, func_name)

def _import_node_by_id(node_id: str) -> Callable:
    """
    按约定从 ./node/{node_id}.py 中导入函数。
    解析顺序：
      1) module 'node.{node_id}' 中查找 `node_{node_id}`
      2) 查找 `run`
      3) 抛错
    支持 importlib.reload，方便开发时热更新。
    """
    mod_name = f"{NODE_PKG}.{node_id}"
    try:
        # 支持热加载（若已加载则 reload）
        if mod_name in sys.modules:
            mod = importlib.reload(sys.modules[mod_name])
        else:
            mod = importlib.import_module(mod_name)
    except ModuleNotFoundError as e:
        raise

    # 优先 node_<id>
    fn_name1 = f"node_{node_id}"
    if hasattr(mod, fn_name1):
        return getattr(mod, fn_name1)
    if hasattr(mod, "run"):
        return getattr(mod, "run")
    # 兜底：如果模块只定义了单个可调用对象，返回第一个可调用
    for v in vars(mod).values():
        if callable(v):
            return v
    raise AttributeError(f"module {mod_name} does not expose node_{node_id} or run()")

def load_graph_from_config(config_path: str, ChatState, monitor_wrapper: Optional[Callable]=None):
    """
    以更灵活的方式加载 nodes：
      - 先尝试 YAML 中的 function 字段（点分路径）
      - 否则按 node id 去 node 包中加载 ./node/{id}.py
    monitor_wrapper: 传入 monitor_performance 工厂以动态包裹节点（monitor_wrapper(node_id) -> decorator）
    """
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    graph = StateGraph(ChatState)

    for node_cfg in cfg.get("nodes", []):
        node_id = node_cfg["id"]
        func_spec = node_cfg.get("function")
        fn = None
        # 1. 尝试按 function 指定的点分路径导入
        if func_spec:
            try:
                fn = _import_function(func_spec)
            except Exception:
                # 忽略异常，后面尝试 node 包
                fn = None

        # 2. 如果没有成功，按约定从 node 包中加载
        if fn is None:
            try:
                fn = _import_node_by_id(node_id)
            except Exception as e:
                raise ImportError(f"无法加载节点 {node_id}: {e}") from e

        # 3. 如果需要监控且提供了监控 wrapper，则包裹
        if node_cfg.get("monitor", False) and monitor_wrapper:
            fn = monitor_wrapper(node_id)(fn)

        # 4. 把节点添加到图
        graph.add_node(node_id, fn)

    # 添加普通边
    for e in cfg.get("edges", []):
        graph.add_edge(e["from"], e["to"])

    # 条件边（支持 key->mapping）
    for node, cond in (cfg.get("conditional_edges") or {}).items():
        key = cond.get("key")
        mapping = cond.get("mapping", {})
        # 捕获 key 到闭包
        def make_key_fn(k):
            return lambda s: s.get(k)
        graph.add_conditional_edges(node, make_key_fn(key), mapping)

    # 额外边
    for e in cfg.get("edges_extra", []):
        graph.add_edge(e["from"], e["to"])

    return graph
