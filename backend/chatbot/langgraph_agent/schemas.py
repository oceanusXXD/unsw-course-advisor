"""
数据契约定义 - 使用 TypedDict 强化类型安全
避免 context_str vs context 等字段不一致导致的 KeyError

字段说明：
- 必选字段：直接定义
- 可选字段：使用 NotRequired (Python 3.11+) 或 Optional
"""

from typing import TypedDict, List, Dict, Any, Optional, Literal
from typing_extensions import NotRequired  # 兼容 Python < 3.11

# ============= 文档相关 =============

class RetrievedDocument(TypedDict):
    """检索到的文档结构"""
    source_id: str  # 文档唯一标识
    title: str  # 文档标题
    source_url: str  # 文档链接
    _text: str  # 文档全文内容（内部使用）
    snippet: NotRequired[str]  # 文档摘要片段（展示用）
    metadata: NotRequired[Dict[str, Any]]  # 额外元数据
    score: NotRequired[float]  # 相关性分数
    
class Citation(TypedDict):
    """引用结构"""
    id: str  # 引用ID
    index: int  # 引用序号 [1, 2, 3...]
    title: str  # 引用标题
    url: str  # 引用链接
    confidence: NotRequired[float]  # 引用置信度
    snippet: NotRequired[str]  # 引用片段

class Source(TypedDict):
    """前端展示的来源结构"""
    title: str  # 来源标题
    url: str  # 来源链接
    snippet: NotRequired[str]  # 来源摘要
    relevance_score: NotRequired[float]  # 相关性分数

# ============= 工具相关 =============

class ToolCall(TypedDict):
    """工具调用结构"""
    tool_name: str
    tool_args: Dict[str, Any]
    tool_call_id: NotRequired[str]

class ToolMessage(TypedDict):
    """工具消息结构"""
    role: Literal["tool"]
    tool_call_id: str
    name: str  # 工具名称
    content: str  # 工具返回内容
    error: NotRequired[str]  # 错误信息（如果有）

# ============= SSE 事件相关 =============

class SSEEvent(TypedDict):
    """服务端推送事件结构"""
    event: Literal["status", "data", "error", "tool", "citation", "source"]
    data: Dict[str, Any]
    timestamp: NotRequired[float]

class StatusEvent(TypedDict):
    """状态事件数据"""
    message: str
    node: NotRequired[str]
    progress: NotRequired[float]

# ============= Router 相关 =============

class RouterDecision(TypedDict):
    """路由决策结构"""
    route: Literal["retrieve_rag", "call_tool", "needs_clarification", "general_chat", "finish"]
    reason: str
    confidence: NotRequired[float]
    tool_info: NotRequired[ToolCall]

class RouterTrail(TypedDict):
    """路由轨迹结构"""
    node: str
    timestamp: float
    decision: NotRequired[RouterDecision]
    metadata: NotRequired[Dict[str, Any]]


# ============= 评估相关 =============

class RetrievalEvaluation(TypedDict):
    """检索评估结果"""
    sufficient: bool
    quality_score: float
    missing_aspects: NotRequired[List[str]]
    suggestions: NotRequired[List[str]]

# ============= 最终输出 =============

class FinalOutput(TypedDict):
    """最终输出结构"""
    answer: str
    sources: List[Source]
    citations: NotRequired[List[Citation]]
    is_grounded: bool
    suggestions: NotRequired[List[str]]
    metadata: NotRequired[Dict[str, Any]]

class PendingFileGeneration(TypedDict):
    """待处理的文件生成任务"""
    courses: List[str]  # 课程代码列表

class PendingPluginInstall(TypedDict):
    """待处理的插件安装任务"""
    requested: bool

# ============= 记忆与学生信息 =============
class ConversationTurn(TypedDict):
    """单轮对话结构 (用于记忆)"""
    Q: str
    A: str
    T: NotRequired[str]

class Memory(TypedDict):
    """对话记忆结构"""
    long_term_summary: str
    recent_conversations: List[ConversationTurn]
    archived_summaries: NotRequired[List[Dict[str, Any]]]

class StudentInfo(TypedDict):
    """学生信息结构"""
    major_code: str
    year: NotRequired[int]
    completed_courses: List[str]
    wam: NotRequired[float]
    raw_summary: NotRequired[str]
    all_major_courses: List[str]
    is_freshman: NotRequired[bool]
    goals: NotRequired[str]
    degree_level: NotRequired[Literal["UG", "PG"]] 


# 新增：Router 可视化轨迹类型
class RouterTrailVisualEntry(TypedDict):
    """Router 可视化轨迹的单个条目结构"""
    type: Literal["node", "edge"]
    id: str
    status: Literal["pending", "running", "success", "error"]
    label: NotRequired[str]
    data: NotRequired[Dict[str, Any]]

# ============= 新增：默认值工厂函数 =============

def get_default_memory() -> Memory:
    """返回一个空的、符合 Memory 契约的默认对象"""
    return {
        "long_term_summary": "",
        "recent_conversations": [],
        "archived_summaries": []
    }

def get_default_student_info() -> StudentInfo:
    """返回一个空的、符合 StudentInfo 契约的默认对象"""
    return {
        "major_code": "",
        "completed_courses": [],
        "all_major_courses": [],
    }


DEFAULT_MEMORY_STRUCTURE: Memory = {
    "long_term_summary": "",
    "recent_conversations": [],
    "archived_summaries": []
}