# config_loader.py (已修正)
import importlib
import os
import sys
import yaml
from types import ModuleType
from typing import Callable, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END
import importlib
import inspect
import sys
# --- START: 代码修改区域 ---

# node 包的名称
NODE_PKG = "node"
AGENT_DIR = os.path.dirname(__file__)
if AGENT_DIR not in sys.path:
    # 使用 insert(0, ...) 确保优先搜索我们的项目路径
    sys.path.insert(0, AGENT_DIR)

def normalize_node_id(node_id): # 标准化节点 ID，处理 __START__ 和 __END__
    if node_id == "__START__":
        return START
    if node_id == "__END__":
        return END
    return node_id

def _import_function(dotted_path: str) -> Callable:
    """
    导入点分路径指定的函数，支持相对导入
    """
    print(f"[DEBUG] Importing function from: {dotted_path}")
    
    # 处理相对导入
    if dotted_path.startswith('.'):
        # 获取调用者所在的包（config_loader.py 所在的包）
        caller_frame = inspect.currentframe().f_back
        caller_module = caller_frame.f_globals['__name__']
        base_package = caller_module.rsplit('.', 1)[0]
        
        # 构建完整导入路径
        full_path = base_package + dotted_path
        module_path, func_name = full_path.rsplit('.', 1)
    else:
        # 绝对导入
        module_path, func_name = dotted_path.rsplit('.', 1)
    mod = importlib.import_module(module_path)
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
    # *** 注意 ***:
    # 这里的导入逻辑是基于 YAML 中没有提供 function 字段的情况。
    # 根据你提供的 YAML 文件，所有节点都指定了完整的 function 路径，
    # 所以这个函数实际上不会被调用。但我们依然保持其正确性。
    mod_name = f"{NODE_PKG}.{node_id}" # 这会变成 "node.load_memory"
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
        if node_id in [START, END]:
            continue
        func_spec = node_cfg.get("function")
        fn = None
        # 1. 尝试按 function 指定的点分路径导入
        if func_spec:
            try:
                # 这里的导入现在会成功
                fn = _import_function(func_spec)
            except Exception as e: # 捕获所有异常，继续尝试按约定导入
                print(f"Warning: Failed to import function '{func_spec}' for node '{node_id}'. Error: {e}")
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
        graph.add_edge(normalize_node_id(e["from"]), normalize_node_id(e["to"]))

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
        graph.add_edge(normalize_node_id(e["from"]), normalize_node_id(e["to"]))

    return graph