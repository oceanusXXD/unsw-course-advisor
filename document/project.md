# LangGraph Chatbot 实践报告

**项目名称:** UNSW Course Info Agent (基于 LangGraph 的 UNSW 课程信息问答机器人)

**提交者:**
**提交日期:**

## 目录

1. [Chatbot 设计思路与总体架构](#1-chatbot-设计思路与总体架构)
2. [使用的技术与实现方法](#2-使用的技术与实现方法)
3. [已实现的功能和流程介绍](#3-已实现的功能和流程介绍)
4. [项目 GitHub 代码链接](#4-项目-github-代码链接)

## 1. Chatbot 设计思路与总体架构

### 1.1 项目目标与主题

本项目设计并实现一个基于 LangGraph 的问答机器人。主要是帮助学生选课和理解课程信息，即一个专注于提供新南威尔士大学 (UNSW) 课程相关信息的智能助手。

核心目标是替代传统的手动查询 UNSW Handbook 的繁琐过程，利用 AI 技术为学生提供一个快速、准确、个性化的课程信息获取渠道。机器人应能理解学生关于课程内容、先决条件、学期安排、讲师信息以及各社交平台可获得的资料，(如寻找"容易"的课程或适合特定技能发展的课程) 等自然语言问题，并基于最新的官方数据给出回答。

### 1.2 设计

- **数据驱动:** 答案应尽可能基于从 UNSW Handbook 爬取的真实数据，通过 RAG 技术注入 LLM，减少信息幻觉。
- **智能化:** 利用 LangGraph 构建可扩展的 Agent 架构，使其具备意图理解、流程控制、工具调用和上下文保持的能力。
- **模块化:** 将数据爬取、知识库构建、AI Agent 逻辑、API 服务等解耦，方便维护和未来扩展。
- **用户体验:** 用户可以一站式通过网页以对话形式了解知识，并且 AI 会根据用户意图以及个人提供的资料进行推荐选课，并且提供了一键选课的插件，能够定时，自动化的一键 enroll 在网页上提到的课程

### 1.3 总体架构

本 Chatbot 基于 LangGraph Agent 架构，主要包括以下几个阶段和组件：

- **数据层 (离线):**

  - 网络爬虫 (crawler/): 定期爬取 UNSW Handbook 网站，获取课程代码、详情、毕业要求等原始 HTML/JSON 数据。
  - 知识库构建 (RAG_database/): 对爬取的原始数据进行清洗、分块 (Chunking)，使用 Embedding 模型 (本项目支持本地 Sentence Transformers 或 阿里云百炼 API) 生成向量，存储到 FAISS 向量索引库中，并关联元数据 (Metadata)。（暂时只有中文，待优化）

- **服务层 (在线):**

  - 后端 API (backend/): 基于 Django 构建，提供 /api/chatbot/chat_multiround/ 接口，接收用户查询和历史记录，返回流式响应。
  - LangGraph Agent (backend/chatbot/langgraph_agent/): 接收 API 传递的请求，作为核心控制器，自主调用可能需要的工具/函数，编排整个问答流程。
  - chat：实现流输出，基于 userid 的记忆存储等功能。

- **交互层:**

  - 基于 React 前端 (frontend/) 提供交互，包含登陆注册，自定义 prompt，主题切换（暂时只有暗亮两种），实现非对称加密。
  - Chrome 插件 (my-extension/) 作为选课交互页面，实现自动选课。

- **核心交互流程:**

```
A. 用户查询 -> 回答（RAG 路径）

用户在前端输入问题并提交。

前端将请求发送到 /api/chatbot/chat_multiround/（包含 JWT）。

后端 LangGraph Agent 的 Router 节点判断是否需要检索：若是则调用 Retriever（FAISS）并得到 top-k sources（含 metadata）。

Agent 将用户问题、top-k sources、历史对话一起传入 Generator 节点，使用 prompt 模板构造输入并调用 LLM（支持流式）。

LLM 输出被 Grounding Check 节点校验是否与 sources 冲突；若冲突执行 fallback（声明不确定或重新检索）。

后端通过 SSE 流式返回生成内容，前端实时渲染，同时将 sourcesData 渲染在右侧面板供用户核验来源。
```

```
B. 文件上传与插件解密使用（简化流程）

用户在前端或插件 Popup 上传加密的选课文件（前端可用 user_key 加密后上传）。

上传后后端生成 file_key，并用 SERVER_MASTER_KEY 加密存储 FileKey 记录。

插件需要解密文件执行选课时，background 向后端请求解密密钥（提供 license & 用户鉴权）。

后端查找文件对应的 FileKey，使用 SERVER_MASTER_KEY 解密 file_key，并用 user_key 对其重新加密或以短期凭证形式返回给插件。

插件使用接收到的凭证/密钥在本地解密文件并在页面上执行选课流程（content_script）。
```

## 2. 使用的技术与实现方法

### 2.1 核心框架：LangGraph

本项目使用 LangGraph (langgraph==0.6.10) 构建 AI Agent 的核心逻辑。

- **状态图 (State Graph):** 定义了一个 ChatState (TypedDict) 来维护对话过程中的所有信息，包括消息历史、当前查询、RAG 检索结果、路由决策、工具调用参数和 ID、生成的答案、校验结果等。
- **节点 (Nodes):** 将 Agent 的每个处理步骤封装为独立的 Python 函数 (节点)，例如 `load_memory`, `prepare_input`, `router`, `retrieve`, `tool_executor`, `generate`, `grounding_check`, `save_memory`。每个节点接收 ChatState 作为输入，执行特定任务，并返回更新后的状态字段。
- **边 (Edges):**
  - 条件边: `router` 节点根据 LLM 返回的路由决策 (`route` 字段) 决定下一个执行哪个节点 (如 `retrieve`, `tool_executor`, `generate`)。
  - 普通边: 定义了节点之间的固定执行顺序，例如从 `retrieve` 或 `tool_executor` 到 `generate`，再到 `grounding_check`，最后到 `save_memory` 并结束 (`__END__`)。
- **配置化:** 使用 YAML 文件 (nodes_config.yaml) 定义图的节点和边，通过 config_loader.py 动态加载并编译图，使得修改流程更加方便。
- **编译与执行:** main_graph.py 负责编译图 (`build_and_compile_graph`) 并提供 `run_chat` 函数作为入口点，接收查询和历史记录，调用编译后的图执行，并处理流式输出。

### 2.2 知识增强：RAG (检索增强生成)

为了让 Chatbot 能够回答关于 UNSW 课程的具体问题，采用了 RAG 及 正则化检索 技术（英文）。

- **数据来源:** UNSW Handbook 网站爬取的课程详情和毕业要求 JSON/HTML 文件。
- **知识库构建 (RAG_database/):**
  - 使用 Python 脚本解析数据，进行文本分块。
  - 调用 Embedding 模型 (支持本地 sentence-transformers 或 阿里云百炼 API) 生成向量。
  - 使用 faiss-cpu (faiss_cpu==1.12.0) 构建向量索引库 (faiss_index.bin)，并存储元数据 (metadata.jsonl)。
- **检索实现 (backend/chatbot/langgraph_agent/rag_chain_qwen.py):**
  - `retrieve` 函数接收用户查询，调用 Embedding 模型生成查询向量。
  - 使用 FAISS 索引执行 Top-K 相似性搜索。
  - 包含一个优化：如果查询中包含明确的课程代码，会优先将该课程的文档插入或置顶到检索结果中。
  - 返回包含分数、来源、文本片段和元数据的文档列表。
- **Agent 集成:** LangGraph 中的 `retrieve` 节点负责调用此 RAG 模块，并将结果存入 ChatState 的 `retrieved` 字段。`generate` 节点随后利用这些信息生成更准确的答案。

### 2.3 对话记忆 (Memory)

为了支持多轮对话，Agent 需要记住之前的交互内容。

- **实现方式:** 采用基于文件的简单记忆机制。
- **加载:** 对话开始时，`load_memory` 节点根据 `user_id` 读取对应的 JSON 文件 (`memory_data/{user_id}.json`)，将其内容加载到 ChatState 的 `memory` 字段。
- **保存:** 对话结束时 (或流式输出完成后)，`save_memory` 节点将包含最新交互的 ChatState (处理为可序列化格式) 追加或更新到对应的 JSON 文件中。
- **使用:** `prepare_input` 节点会结合加载的 `memory` 中的历史消息和当前用户查询，构建完整的消息列表传递给后续节点。

### 2.4 工具使用 (Tools)

Agent 被赋予了使用外部工具的能力，以执行 RAG 无法完成的任务或与外部系统交互。

- **工具定义 (tools/):** 每个工具是一个 Python 函数，并在 `tools/__init__.py` 中注册，包含函数引用、功能描述和参数说明。
- **已实现工具:**
  - `get_course_instructor`: (示例) 模拟查询课程讲师。
  - `fetch_url`: 抓取网页内容。
  - `wiki_search`: 查询维基百科。
  - `generate_selection`: 生成固定的选课结果 JSON。
  - `plugin_install`: (示例) 模拟调用插件安装接口。
  - `crypto`: (内部工具) 由 `generate_selection` 调用，使用 `accounts` 应用的 `CryptoService` 加密选课结果并保存文件密钥。
- **工具调用流程:**
  - `router` 节点根据用户查询和工具描述，判断是否需要调用工具，并决定调用哪个工具及传递什么参数。
  - 如果需要调用，状态图流转到 `tool_executor` 节点。
  - `tool_executor` 根据 ChatState 中的 `tool_name` 和 `tool_args` 执行相应的 Python 函数。
  - 工具执行结果以 `ToolMessage` 的形式添加到消息历史中，并传递给 `generate` 节点用于生成最终回复。

### 2.5 大型语言模型 (LLM)

本项目主要依赖大型语言模型来驱动 Agent 的决策和生成。

- **模型选择:** 主要使用阿里云百炼的 Qwen 系列模型 (如 `qwen-plus`, `qwen-max`)，通过设置环境变量 `QWEN_MODEL` 和 `DASHSCOPE_API_KEY` 来配置。支持使用提供的免费 Tokens。
- **API 调用:** 通过 `openai` Python 库 (`openai==2.3.0` - 注意：此版本较旧，但代码似乎适配了更新的 API 调用方式，建议更新依赖) 调用兼容 OpenAI 的 API 接口 (`call_qwen_sync` 函数)。
- **应用场景:**
  - 意图路由 (`router`): 使用 LLM 理解用户查询，并根据预设的 Prompt (包含工具描述) 输出 JSON 决策。
  - 答案生成 (`generate`): 使用 LLM 结合 RAG 上下文或工具结果，生成自然语言回复。
  - 答案校验 (`grounding_check`): (可选) 使用 LLM 判断生成的答案是否与 RAG 上下文一致。
- **Prompt 工程:** 在 `.prompts.json` 文件中定义和管理用于不同任务 (路由、生成、校验) 的 Prompt 模板。

### 2.6 后端服务与 API

- **框架:** 使用 Django (Django==5.2.7) 作为 Web 框架，提供 API 服务、数据库 ORM 和管理后台。
- **API 实现:** 使用 Django REST framework (djangorestframework) 创建 RESTful API 端点。
  - 核心聊天接口: `POST /api/chatbot/chat_multiround/`，接收 JSON 请求体 (`{"query": "...", "history": [...]}`), 返回 `text/event-stream` 类型的流式响应。
  - 其他接口: 包括用户注册/登录/登出、密码修改、许可证激活/验证、获取文件解密密钥等 (`accounts/urls.py`)。
- **数据库:** 默认使用 SQLite (`db.sqlite3`) 进行开发，方便快捷。主要用于存储用户信息 (`User` 模型) 和加密文件密钥 (`FileKey` 模型)。

## 3. 已实现的功能和流程介绍

### 3.1 核心问答功能

Chatbot 能够接收用户的自然语言提问，并通过 LangGraph Agent 进行处理，最终返回答案。支持连续的多轮对话。

### 3.2 RAG 驱动的课程信息查询

当用户的提问与 UNSW 课程信息相关时 (由 `router` 节点判断为 `retrieve_rag` 路径)，Agent 会执行以下步骤：

1. 调用 RAG 模块，使用用户查询在预先构建的 FAISS 向量库中进行相似性搜索。
2. 检索与查询最相关的课程信息文本片段 (来自 Handbook)。
3. 将检索到的文本片段作为上下文，连同原始查询和对话历史一起传递给 LLM (`generate` 节点)。
4. LLM 基于提供的上下文生成答案。 (可选) `grounding_check` 节点会验证答案是否基于上下文，如果不是，可能会返回通用回复或提示信息。

**示例:**
用户问："COMP1511 这门课讲了什么？"
Agent -> Router -> RAG -> Retrieve (找到 COMP1511 介绍片段) -> Generate (结合片段生成答案) -> Output。

### 3.3 多轮对话能力

通过 `load_memory` 和 `save_memory` 节点，Chatbot 能够记住之前的对话内容。

- 每次对话开始时，加载与用户 ID 关联的历史记录。
- 将历史记录与当前查询合并后输入 Agent。
- 对话结束后，将包含当前问答的新历史记录保存回文件。
  这使得用户可以进行追问或在后续问题中引用之前讨论过的内容。

### 3.4 工具调用示例 (如生成选课计划)

Agent 能够根据需要调用预定义的工具。

- **触发:** 当 `router` 节点判断用户意图是执行某个工具时 (如明确要求"生成选课计划"可能触发 `generate_selection`)。
- **执行:** `tool_executor` 节点调用相应的 Python 函数 (`tools/generate_selection.py`)。
- **结果处理:** `generate_selection` 工具会生成一个固定的选课 JSON，并内部调用 `crypto` 工具进行加密，最终将包含加密文件 URL 的 JSON 结果返回。
- **回复生成:** `generate` 节点接收到工具返回的 JSON 结果 (作为 `ToolMessage`)，并基于此生成告知用户操作完成并提供 URL 的回复。

### 3.5 交互方式 (API)

- **请求:** 发送 JSON 数据，包含：
  - `query`: (必需) 用户的当前问题 (字符串)。
  - `history`: (可选) 之前的对话历史，格式为 `[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]` 列表。
  - `user_id`: (可选) 用于区分不同用户的记忆文件 (字符串)。
- **响应:** `text/event-stream` 类型的流式响应。每一条消息都是 `data: {"type": "...", "data": ...}\n\n` 的格式。
  - `type="token"`: `data` 是 LLM 生成的文本片段。
  - `type="history"`: (通常在流末尾发送) `data` 是包含当前问答的完整更新后历史记录。
  - `type="error"`: `data` 包含错误信息。
  - `type="end"`: 表示流结束。
- **测试工具:** 可以使用 `backend/test/test_chat_multi.py` 脚本在命令行进行交互测试，它模拟了 API 调用和流式响应处理。

### 3.6 LangGraph Agent 工作流详解

以一个典型的 RAG 查询为例，Agent 内部的工作流程如下 (`nodes_config.yaml` 定义了流转关系)：

1. **`__START__`:** 图开始。
2. **`load_memory`:** 读取用户 `user_id` 对应的历史记录文件 `memory_data/{user_id}.json`，加载到 `state['memory']`。
3. **`prepare_input`:** 将当前 `state['query']` 和 `state['memory']['messages']` 合并成完整的消息列表 `state['messages']`。
4. **`router`:** 调用 LLM 判断意图。假设判断为 `retrieve_rag`。更新 `state['route'] = 'retrieve_rag'`。
5. **(条件边)** 根据 `state['route'] == 'retrieve_rag'`，图流转到 `retrieve` 节点。
6. **`retrieve`:** 调用 `rag_chain_qwen.retrieve()` 函数，执行向量搜索，将找到的文档列表存入 `state['retrieved']`。
7. **(普通边)** 图流转到 `generate` 节点。
8. **`generate`:** 调用 LLM，输入包含 `state['messages']` (含历史和当前问题) 和 `state['retrieved']` (作为上下文的文档)。LLM 生成答案，存入 `state['answer']` (可能是流式迭代器或完整字符串)。
9. **(普通边)** 图流转到 `grounding_check` 节点。
10. **`grounding_check`:** (如果启用) 调用 LLM 检查 `state['answer']` 是否与 `state['retrieved']` 一致，结果存入 `state['is_grounded']`。
11. **(普通边)** 图流转到 `save_memory` 节点。
12. **`save_memory`:** 将包含本次问答的 ChatState (处理后的可序列化版本) 更新/追加到 `memory_data/{user_id}.json` 文件中。
13. **(普通边)** 图流转到 `__END__`，流程结束。

**注意:** 如果 `router` 判断为 `call_tool`，流程会走向 `tool_executor` 再到 `generate`；如果判断为 `general_chat` 或 `needs_clarification`，则直接跳到 `generate`。`main_graph.py` 中的 `run_chat` 函数负责驱动这个流程并处理 `generate` 节点返回的流式输出。

## 4. 项目 GitHub 代码链接

https://github.com/oceanusxxd/unsw-course-advisor
