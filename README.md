# UNSW 课程顾问

[详细项目介绍](./document/project_summary.md)

[English](./document/README_EN.md) | [Deutsch](COMING SOON) | [日本語](COMING SOON) | [Español](COMING SOON)

---

### 项目简介

**UNSW 课程顾问** 是一个基于人工智能的个性化课程推荐系统，专为新南威尔士大学(UNSW)的学生设计。我们采用先进的 RAG (检索增强生成) 技术，将繁琐、耗时的手动查询手册过程，转变为智能、高效、数据驱动的课程选择体验。

我们的目标是让每位 UNSW 学生都能轻松找到最适合自己的课程，无论是为了冲击高分 (HD)、寻找高性价比的“水课”、掌握实用技能，还是规划高效的短学期学习路径。

---

### 核心理念

翻阅厚厚的 UNSW 手册来寻找理想课程，不仅效率低下，还可能错失良机。本项目致力于通过技术手段彻底改变这一现状。

**核心流程**:

1.  **智能爬取**: 自动化采集 UNSW 官方手册、课程评价等公开数据。
2.  **知识沉淀**: 将杂乱的数据清洗、处理后，存入专门构建的向量数据库。
3.  **智能生成**: 利用前沿的大语言模型 (如 Qwen) 和 RAG 技术，根据学生的个性化需求，生成基于真实数据的、人类可读的课程建议。

**一句话总结：让你不用再花冤枉钱就可以选好课！**

---

### 主要特性

- **实时更新**: 定期爬取 UNSW 官网，确保课程信息、开课时间等数据的准确性和时效性。
- **个性化推荐**: 深度理解你的选课意图——无论是想冲刺高分 (HD)，轻松拿学分 (找水课)，学习前沿实用课程，还是计划利用短学期加速毕业，我们都能提供量身定制的建议。
- **高效聊天机器人**: 基于 Qwen 和 LangGraph 构建的智能对话机器人，能够快速、准确地回答你的各类选课疑问。
- **[即将推出] Chrome 插件集成**: 一键唤醒智能助手，自动在 myUNSW 的 Course Plan 页面为你规划课程，甚至一键完成 enroll 操作，将便利性提升到极致。

---

### 技术栈

- **后端**: Django, Django REST framework, LangGraph, Qwen (LLM), FAISS (向量检索), Sentence Transformers / OpenAI API (Embeddings), PyCryptodome (加密)。
- **前端**: React, Vite, TypeScript, Tailwind CSS。
- **爬虫**: Python, Requests, BeautifulSoup。
- **浏览器插件**: Chrome Extension APIs (Manifest V3), JavaScript。
- **数据库**: SQLite (默认), PostgreSQL (推荐生产)。

---

### 系统架构

项目采用模块化设计，确保高内聚、低耦合，易于维护和扩展。

**核心模块**:

- `crawler/`: 负责爬取课程 URL、详细信息和毕业要求的脚本。
- `data/`: 存储原始爬取数据和处理后的结构化数据。
- `RAG_database/`: 用于解析数据、生成文本嵌入向量、填充向量数据库 (FAISS)，并提供检索功能。
- `backend/`: 基于 Django 构建的后端服务，提供 API 接口。
  - `chatbot/`: 包含 LangGraph Agent 核心逻辑，负责意图识别、RAG 调用、工具执行和答案生成。
  - `accounts/`: 处理用户认证、许可证管理和加密服务。
  - `extension/`: (实验性) 包含与 Chrome 插件自动化测试相关的接口。
- `frontend/`: 使用 React 构建的现代化用户交互界面。
- `my-extension/`: Chrome 浏览器插件代码，用于与 UNSW 选课页面交互和自动选课。
- `tests/`: 包含单元测试和集成测试脚本。
- `ops/`: (规划中) 包含 Docker 配置文件和自动化部署脚本。
- `configs/`: (规划中) 集中管理项目配置。
- `evaluation/`: (规划中) 包含 RAG 效果评估脚本。

#### 架构图

![系统架构](./document/structure.png)

**数据流:**

1.  **爬虫 (Crawler)**: 从 UNSW Handbook 和社交媒体获取课程代码、详情及评价，处理后生成 JSON 数据。
2.  **数据服务 (Data Service)**: 接收爬虫数据，进行文本分块 (Chunking)、向量化 (Embedding)，并将向量和元数据 (Metadata) 存储到向量数据库 (Vector Database)。
3.  **用户交互 (User)**: 用户通过 React Web Chat 与 Django 后端交互，请求通过 HTTP/Redis 传递。
4.  **LangGraph Agent**: Django 后端的核心，包含对话管理器 (Dialogue Manager)、工具路由器 (Tool Router) 和状态管理器 (State Manager)。
5.  **工具调用 (Tools)**: LangGraph 根据需要调用 RAG (从数据服务检索)、Chrome 插件工具或其他工具。
6.  **Chrome 插件**: 与 LangGraph 交互，接收指令并在 MyUNSW 网站上执行自动化操作 (如选课)，并可能提供反馈。

---

### 快速开始

#### 环境要求

- Python 3.9+
- Django
- Node.js (用于前端开发)
- Chrome 浏览器 (用于插件)
- (可选) FAISS, Sentence Transformers 或 OpenAI API Key (用于 RAG)

#### 安装与运行

1.  **克隆仓库**

    ```bash
    git clone [https://github.com/oceanusxxd/unsw-course-advisor.git](https://github.com/oceanusxxd/unsw-course-advisor.git)
    cd unsw-course-advisor
    ```

2.  **安装 Python 依赖**

    ```bash
    pip install -r requirements.txt
    # !! 重要: requirements.txt 缺失 pycryptodome，需要手动添加 !!
    pip install pycryptodome
    ```

3.  **配置环境变量**

    - 在 `backend/` 目录下创建 `.env` 文件。
    - 至少需要配置 `DASHSCOPE_API_KEY` (如果使用 API Embedding), `SERVER_MASTER_KEY` (用于加密), `QWEN_MODEL` (或相应的 LLM API Key/Endpoint)。参考 `backend/chatbot/langgraph_agent/core.py` 和 `backend/accounts/services.py` 获取所需变量列表。
    - `SERVER_MASTER_KEY` **必须**设置为一个强随机的 32 字节密钥（Base64 编码是一个好选择）。

4.  **数据处理流水线**

    - **步骤 4.1: 爬取课程数据** (确保 `crawler/subject.txt` 存在并包含目标专业代码)
      ```bash
      cd crawler/
      python course_all_crawler.py      # 爬取课程代码列表
      python course_detail_crawler.py   # 爬取课程详细信息
      python check_missing_courses.py # 检查并可能重新爬取缺失课程
      # (可选) python subject_graduation_request.py # 爬取毕业要求 (需要 subject1.txt)
      # (可选) python parse_pagecontent.py        # 解析毕业要求 HTML
      # (可选) python get_coursemap.py            # 从本地 HTML 生成 course_map.json (用于插件)
      cd ..
      ```
    - **步骤 4.2: 构建向量数据库** (为 RAG 检索服务准备数据)
      ```bash
      cd RAG_database/
      # 根据需要修改 build_*.py 中的 USE_API_EMBEDDING 和模型配置
      python build_course_datail_vector_db.py   # 构建课程详情向量库
      # (可选) python build_graduation_detail_vector_db.py # 构建毕业要求向量库
      cd ..
      ```

5.  **运行 Django 数据库迁移**

    ```bash
    cd backend/
    python manage.py migrate
    ```

6.  **启动后端 Django 服务**

    ```bash
    # 仍在 backend/ 目录下
    python manage.py runserver
    ```

    _服务将默认运行在 `http://127.0.0.1:8000/`_。API 访问地址为 `http://127.0.0.1:8000/api/`。

7.  **启动前端 React 界面**

    ```bash
    cd ../frontend/
    npm install
    npm run dev
    ```

    _现在你可以在浏览器中访问 `http://localhost:5173` (或 Vite 输出的其他端口) 来与应用交互_。

8.  **(可选) 加载 Chrome 插件**
    - 打开 Chrome 浏览器，进入 `chrome://extensions/`。
    - 开启右上角的“开发者模式”。
    - 点击“加载已解压的扩展程序”，选择项目中的 `my-extension/` 目录。

---

### 发展路线图

- [x] **基础数据爬取**: 定向爬取官网 Handbook 资料，用作课程描述。
- [x] **基础数据库构建**: 结构化存储爬取到的课程详细资料。
- [x] **向量数据库构建**: 为 RAG 提供高效的语义检索能力。
- [x] **聊天机器人**: 基于 Langgraph 实现交互式问答流程。
- [x] **RAG 集成**: 基于 Langgraph 构建自评判 Agent，智能唤起 RAG 进行检索。
- [ ] **进阶数据爬取**: 采集课程评价数据（如各中介、小红书等），构建更全面的课程画像。
- [x] **用户认证系统**: 支持学生登录，保存个人专业、已修课程和偏好设置。
- [x] **流式输出**: 优化聊天机器人交互，实现打字机般的实时响应体验。
- [x] **Chrome 插件**: 实现课程规划和一键选课/Enroll 功能。
- [ ] **向量化与分块优化**: 持续优化 RAG 检索的效果及速度。
- [x] **React 前端重构**: 将前端改成 React。
- [ ] **语义聚类**: 自动识别内容重复或高度相似的课程。
- [ ] **架构升级**: 引入 RPC 优化系统性能和用户体验，探索 SaaS/PaaS 部署模式。

---

### 贡献指南

我们热烈欢迎社区的贡献！无论是代码、文档还是建议，都对我们至关重要。

1.  **Fork** 本项目。
2.  创建你的功能分支 (`git checkout -b feature/YourAmazingFeature`)。
3.  提交你的更改 (`git commit -m 'Add some AmazingFeature'`)。
4.  将你的分支推送到远程仓库 (`git push origin feature/YourAmazingFeature`)。
5.  提交一个 **Pull Request**，等待审核。

---

### 联系我们

如果你有任何问题、建议或合作意向，请随时通过以下方式联系我：

- **邮箱**: <tao666918@gmail.com> | <z453676955@qq.com>
- 或者在 GitHub 上提交一个 **Issue**。

---

### 许可证

本项目基于 **GNU General Public License v3.0 许可证** 进行分发。详情请查阅 `LICENSE` 文件。
