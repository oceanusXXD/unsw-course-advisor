from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Literal, Annotated
from langgraph.graph.message import add_messages

# 导入强类型定义和新的工厂函数
from .schemas import (
    RetrievedDocument, Citation, Source, ToolCall, SSEEvent, RouterDecision, 
    RouterTrail, StudentInfo, Memory, FinalOutput, PendingFileGeneration, 
    PendingPluginInstall, RouterTrailVisualEntry, # 新增导入
    get_default_memory, get_default_student_info   # 新增导入
)
# 自定义 reducer：只在新值非 None 时更新
def keep_if_not_none(old, new):
    """只在 new 不为 None 时更新，否则保留 old"""
    return new if new is not None else old
@dataclass
class ChatState(dict):
    messages: Annotated[List[Any], add_messages] = field(default_factory=list)
    query: str = ""
    user_id: Optional[str] = None

    # Router 相关
    route: Optional[Literal["retrieve_rag", "call_tool", "needs_clarification", "general_chat", "finish"]] = None
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_call_id: Optional[str] = None

    # 检索相关
    rewritten_query: Optional[str] = None
    retrieved_docs: Optional[List[RetrievedDocument]] = field(default_factory=list)
    retrieval_round: Optional[int] = 0
    sufficient: Optional[bool] = None
    quality_score: Optional[float] = None

    # 来源和引用
    sources: Optional[List[Source]] = field(default_factory=list)
    citations: Optional[List[Citation]] = field(default_factory=list)

    # 答案生成
    answer: Optional[str] = None
    is_grounded: Optional[bool] = False
    # 优化：默认值为 None，符合 Optional 类型
    final_output: Optional[FinalOutput] = None

    # 记忆和学生信息 - 优化：使用工厂函数
    memory: Memory = field(default_factory=get_default_memory)
    student_info: StudentInfo = field(default_factory=get_default_student_info)
    
    # Router 轨迹
    router_trail: List[RouterTrail] = field(default_factory=list)
    # 优化：使用强类型
    router_trail_visual: List[RouterTrailVisualEntry] = field(default_factory=list)
    
    # 配置开关
    enable_grounding: Optional[bool] = True
    enable_suggestions: Optional[bool] = True

    # 待处理任务
    pending_file_generation: Annotated[
        Optional[PendingFileGeneration], 
        keep_if_not_none  # 只在新值非 None 时更新
    ] = None
    
    pending_plugin_install: Annotated[
        Optional[PendingPluginInstall], 
        keep_if_not_none  # 只在新值非 None 时更新
    ] = None
    file_generation_declined: Optional[bool] = False
    last_proposal_ts: Optional[float] = 0.0
    # 流控制
    stream: Optional[bool] = False
    run_id: Optional[float] = None
    turn_id: str = ""

    # Router 中间产物
    context_snapshot: Dict[str, Any] = field(default_factory=dict)
    planner_raw: Dict[str, Any] = field(default_factory=dict)
    planner_decision: Optional[RouterDecision] = field(default=None) # 默认 None 更安全

    # SSE 事件
    sse_events: List[SSEEvent] = field(default_factory=list)
    error: Optional[str] = None
    def __post_init__(self):
        for k, v in self.__dict__.items():
            self[k] = v