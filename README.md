## UNSW 课程顾问 🤖🎓  
[English](./README_EN.md) | [Deutsch](COMING SOON) | [日本語](COMING SOON) | [Español](COMING SOON)  

基于人工智能的个性化课程推荐系统，专为新南威尔士大学学生设计。采用现代RAG（检索增强生成）技术构建，旨在用智能、基于证据的课程建议替代手动查阅手册的繁琐过程。  

---

### 🎯 核心理念  
翻阅UNSW手册寻找合适课程可能令人望而生畏。本项目通过结合以下技术实现自动化发现流程：  
- 网络爬虫  
- 向量数据库  
- 大语言模型  

**为学生**：根据专业、已修课程和个人兴趣提供个性化课程建议  
**为顾问和教职工**：强大的课程数据查询和课程关系理解工具  

**核心流程**：  
1. 爬取官方课程数据  
2. 存入可搜索数据库  
3. 使用RAG服务生成基于真实数据的人类可读建议  

---

### ✨ 主要特性  
- **实时更新**：定期爬取获取最新课程信息  
- **个性化推荐**：基于学术背景（专业、已修课程）和兴趣定制  
- **可解释AI**：每项建议都附带课程概述、先修条件等来源片段  
- **交互式界面**：Streamlit界面即时获取建议  
- **可扩展模块化**：清晰解耦的架构设计  

---

### 🛠️ 技术栈  
#### 🏛️ 系统架构  
**核心模块**：  
- `crawler/`：爬取课程URL和详细信息的脚本  
- `data/`：存储原始爬取数据和结构化数据  
- `ingest/`：解析数据、填充数据库、生成嵌入向量  
- `retrieval/`：查询向量数据库服务  
- `rag_service/`：生成推荐的核心RAG API  
- `ui/`：Streamlit/Django前端界面  
- `tests/`：单元和集成测试  
- `ops/`：Docker配置和部署脚本  

---

### 🚀 快速开始  
#### 环境要求  
- Python 3.9+  
- Docker 和 Docker Compose  
- PostgreSQL + 向量数据库（如ChromaDB）  
- LLM API密钥（如OpenAI）  

#### 1. 安装依赖
```bash
pip install -r requirements.txt
```
#### 2. 端到端工作流程
**第一步：爬取课程数据**
获取课程URL，然后爬取详细信息（内置反爬虫措施）

**第二步：数据提取和向量化**
- 处理原始JSON → 存入PostgreSQL
- 生成嵌入向量 → 存入向量数据库

**数据库结构**：
- `subjects`：学科代码和名称（如COMP、MATH）
- `courses`：核心课程信息（代码、名称、学分）
- `course_details`：概述、备注、授课方式
- `embeddings`：文本块和对应向量

**第三步：启动RAG API服务**
主要接口：
- `POST /api/recommend`：主要推荐接口
- `GET /api/course/{code}`：获取课程详情
- `GET /api/search?query=...`：向量搜索相关片段

**第四步：启动Streamlit界面**
```bash
streamlit run ui/app.py
```
访问 `http://localhost:8501`

---

### 📈 发展路线图
- [ ] 增强学生画像：语义搜索+协同过滤混合方法
- [ ] 高级关系映射：课程依赖图可视化（LangGraph）
- [ ] 置信度评分：基于先修条件匹配和难度风险
- [ ] 时间表模拟：检查课程冲突和学分负荷
- [ ] 浏览器插件：在手册页面直接显示推荐
- [ ] A/B测试框架：优化提示策略和检索模型
- [ ] 语义聚类：自动识别重复或重叠课程

---

### 🤝 贡献指南
1.  Fork本项目
2.  创建功能分支（`git checkout -b feature/新功能`）
3.  提交更改（`git commit -m '添加新功能'`）
4.  推送到分支（`git push origin feature/新功能`）
5.  开启Pull Request

---

### 📄 许可证
基于**MIT许可证**分发，详见`LICENSE`文件。