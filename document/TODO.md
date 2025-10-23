# 项目 TODO 列表 (UNSW Course Advisor)

## 优先级说明

- **[高]**：关键 Bug 修复、安全问题、核心功能缺失
- **[中]**：重要功能完善、性能/体验优化、生产环境准备
- **[低]**：次要功能、代码优化、文档完善

---

## I. 前端 (React / Vite / TypeScript)

### [高] 功能完善与占位符替换

- **InputPanel.tsx**：实现文件上传功能 (`handleUploadClick`)，允许用户上传加密文件或选课列表。
- **SettingsProfileSection.tsx**：实现头像上传 (`handleFileChange`)，更新用户信息并提供 UI 反馈。
- **SettingsAccountSection.tsx**：实现删除账户功能，需后端 API 支持并添加确认提示。

### [高] 依赖版本校准

- **package.json**：调整 `@types/react` 和 `@types/react-dom` 版本，使其与 `react` 和 `react-dom (v18)` 一致。

### [中] 配置与环境

- **src/services/api.ts**：将硬编码的 `API_BASE` 修改为从 `Vite` 环境变量 `import.meta.env.VITE_API_BASE_URL` 读取。

### [中] RAG 结果展示

- **RightPanel.tsx**：替换 mock 数据，修改 `Chat.tsx` 的 `handleSources` 回调，将流式响应结果传递给 `App.tsx` 的 `results` 状态并展示。
- **ResultCard.tsx**：根据真实数据结构调整 `CourseData` 接口和卡片显示内容。

### [中] 错误处理与用户反馈

- 全局检查 `api.ts` 与各组件中的 `catch` 块，通过 `Toaster` 或组件消息提示错误，而非仅 `console.error`。

### [低] 性能优化

- **ChatContext.tsx**：优化聊天记录的 `localStorage` 持久化策略（使用节流或改用 IndexedDB）。
- 移除组件中的 `MutationObserver`，改用 `CSS 变量` 或 `Context API` 实现主题切换。

### [低] 代码复用

- 将 `api.ts` 中的加密/解密函数提取到 `src/utils/crypto.ts` 以便未来与 Chrome 插件共享。

### [低] UI/UX 细节

- 优化响应式布局与可访问性（添加 `aria-label` 等）。

---

## II. 后端 (Django)

### [高] 依赖修复与管理

- 更新 `openai==2.3.0` → `openai>=1.0.0`。
- 添加缺失依赖 `pycryptodome`。
- 考虑使用 `pip-tools` 或 `Poetry/PDM` 管理依赖版本。

### [高] 安全加固

- **settings.py**：更换默认 `SECRET_KEY`，生产环境设置 `DEBUG=False`，配置 `ALLOWED_HOSTS`。
- **accounts/views.py**：审查 `AllowAny` 的使用，考虑要求认证。
- **accounts/services.py**：强制从环境变量读取 Base64 编码的主密钥，移除多余逻辑。

### [高] 移除/重构不稳定功能

- **extension/views.py**：`launch_and_check_extension` 使用 Selenium/PyAutoGUI，需标注为测试或寻找替代方案。

### [中] 生产环境配置

- 设置生产数据库（PostgreSQL）、邮件后端、静态与媒体文件服务（Nginx, Whitenoise, S3）。

### [中] LangGraph Agent 增强

- 增加错误处理与 fallback 机制。
- **save_memory.py**：限制历史记录长度、支持定期清理或摘要化。
- 扩展 `tools` 工具集。

### [低] API 完善

- 添加 docstring 或使用 `drf-spectacular` 生成 API 文档。
- 标准化错误响应格式。

### [低] 测试

- 增加针对加密逻辑、许可证、LangGraph 流程及 RAG 效果的测试。

---

## III. 模型 / RAG 优化

### [高] Embedding 模型与维度确认

- 确认 `RAG_database` 与 `rag_chain_qwen.py` 中模型与维度设置一致，避免向量不匹配。

### [中] 数据质量与覆盖

- 实现课程评价数据爬取与整合。
- 建立数据清洗与验证流程。

### [中] Chunking 策略优化

- 调整 `CHUNK_MAX_CHARS`、`CHUNK_OVERLAP` 或基于语义的切分策略。

### [中] 检索与重排策略

- 评估交叉编码器效果 (`USE_CROSS_ENCODER=True`)。
- 优化课程代码优先逻辑与排序。
- 探索混合检索策略（关键词+向量搜索）。

### [中] Prompt Engineering

- 优化 `.prompts.json` 中的 Router、Generator、Grounding Check prompt。

### [中] LangGraph Agent 调优

- 评估并优化 Router 与 Grounding Check 的准确率与阈值。

### [低] 评估体系

- 实现 `evaluation/` 下的评估脚本（Hit Rate、MRR、RAGAS 等）。

---

## IV. Chrome 插件 (my-extension)

### [高] 核心功能实现

- 实现课程规划、添加、移除功能。
- 实现 `content_script.js` 与 `background.js` 的交互，支持自动选课。

### [中] 状态管理与鲁棒性

- 增强选课流程的状态管理与错误恢复机制。
- 优化 DOM 选择器与加载等待逻辑。
- 确保 `__apiRunner` 与 token 获取逻辑稳定。

### [中] 安全

- 检查脚本间通信的安全性，防止敏感数据泄露。
- 在 `background.js` 中添加消息验证。

### [低] 代码复用

- 将 `popup-utils.js` 的加密/解密函数提取到共享库，与前端共用。

### [低] UI/UX

- 优化 `popup.html` 与 `popup.css`，增加清晰的操作反馈。

---

## V. 爬虫 (crawler)

### [中] 健壮性与维护

- 增强错误处理与日志记录。
- 添加数据验证步骤。
- 定期检测 UNSW Handbook 结构变化。
- 优化 `_extract_embedded_json` 与 DOM 回退逻辑。

### [低] 效率

- 评估并优化并发参数 (`MAX_WORKERS`) 与延迟策略。

---

## VI. 通用 / DevOps

### [中] CI/CD

- 建立自动化测试、构建、部署流水线。

### [中] 部署

- 制定前后端部署策略（Docker, Nginx, Gunicorn/Uvicorn）。

### [低] 监控与日志

- 集成日志与监控系统（Sentry, ELK, Prometheus, Grafana）。

### [低] 文档

- 更新 `README.md` 与环境变量、部署说明等文档。
