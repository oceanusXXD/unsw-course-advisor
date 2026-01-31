项目 TODO 列表 (UNSW Course Advisor)

优先级说明
滑动条 复制 gemini 样式
• [高]：关键 Bug 修复、安全问题、核心功能缺失

• [中]：重要功能完善、性能/体验优化、生产环境准备

• [低]：次要功能、代码优化、文档完善

I. 前端 (React / Vite / TypeScript)

[高] 功能完善与占位符替换

• SettingsProfileSection.tsx：实现头像上传 (handleFileChange)，更新用户信息并提供 UI 反馈。

[中] RAG 结果展示

• RightPanel.tsx：替换 mock 数据，修改 Chat.tsx 的 handleSources 回调，将流式响应结果传递给 App.tsx 的 results 状态并展示。

• ResultCard.tsx：根据真实数据结构调整 CourseData 接口和卡片显示内容。

[中] 配置与环境

• src/services/api.ts：将硬编码的 API_BASE 修改为从 Vite 环境变量 import.meta.env.VITE_API_BASE_URL 读取。[OK] DONE

[中] 错误处理与用户反馈

• 全局检查 api.ts 与各组件中的 catch 块，通过 Toaster 或组件消息提示错误，而非仅 console.error。[OK] DONE

[低] 性能优化

• ChatContext.tsx：优化聊天记录的 localStorage 持久化。[OK] DONE

[低] UI/UX 细节

• 优化响应式布局与可访问性。

[OK] 已完成

• 第三方登录状态管理 [OK] DONE

• InputPanel.tsx：实现文件上传功能 (handleUploadClick)，允许用户上传加密文件或选课列表。[OK] DONE

• SettingsAccountSection.tsx：实现删除账户功能，需后端 API 支持并添加确认提示。[OK] DONE

II. 后端 (Django)

实施步骤建议

1. 第一阶段（基础优化）
   • 引入类型提示

   • 重构状态管理

   • 添加基本错误处理

2. 第二阶段（性能提升）
   • 实施缓存机制

   • 优化数据库查询

   • 引入并行处理

3. 第三阶段（架构完善）
   • 实现完整的日志系统

   • 添加监控指标

   • 完善测试用例

[高] 核心规则集

• （测试）运行这个 LangGraph，从前端（或测试工具）传入一个 user_profile，并确认您能收到（3）返回的 JSON 作为最终输出。

• 确认流程实现

• redis 缓存

• 性能监控优化

• 上云

[高] 依赖修复与管理

• 更新 openai==2.3.0 -> openai>=1.0.0。

• 添加缺失依赖 pycryptodome。

• 考虑使用 pip-tools 或 Poetry/PDM 管理依赖版本。

[高] 移除/重构不稳定功能

• extension/views.py：launch_and_check_extension 使用 Selenium/PyAutoGUI，需标注为测试或寻找替代方案。

[中] 生产环境配置

• 设置生产数据库（PostgreSQL）、邮件后端、静态与媒体文件服务（Nginx, Whitenoise, S3）。

[中] LangGraph Agent 增强

• 增加错误处理与 fallback 机制。

• 扩展 tools 工具集。

[低] API 完善

• 添加 docstring 或使用 drf-spectacular 生成 API 文档。

• 标准化错误响应格式。

[低] 测试

• 增加针对加密逻辑、许可证、LangGraph 流程及 RAG 效果的测试。

[OK] 已完成

• （编译 1）编写 compile_courses.py 脚本，将所有"课程详情"JSON 合并并解析"先修规则"。[OK] DONE

• （编译 2）编写 compile_program_rules.py 脚本，将所有"专业要求"JSON 解析为结构化的"毕业规则"。[OK] DONE

• （工具）编写一个 HardRuleFilterTool 函数，它加载（1）和（2）的数据，并根据用户输入（专业、已修）筛选课程。[OK] DONE

• （建图）搭建一个最简单的 LangGraph，它只包含一个"工具节点"，该节点专门调用（3）的工具。[OK] DONE

• accounts/services.py：强制从环境变量读取 Base64 编码的主密钥，移除多余逻辑。[OK] DONE

• save_memory.py：限制历史记录长度、支持定期清理或摘要化。[OK] DONE

III. 模型 / RAG 优化

[中] 数据质量与覆盖

• 实现课程评价数据爬取与整合。[OK] DONE

• 建立数据清洗与验证流程。[OK] DONE

[中] Chunking 策略优化

• 调整 CHUNK_MAX_CHARS、CHUNK_OVERLAP 或基于语义的切分策略。

[中] 检索与重排策略

• 评估交叉编码器效果 (USE_CROSS_ENCODER=True)。

• 优化课程代码优先逻辑与排序。

• 探索混合检索策略（关键词+向量搜索）。

[中] Prompt Engineering

• 优化 .prompts.json 中的 Router、Generator、Grounding Check prompt。

[中] LangGraph Agent 调优

• 评估并优化 Router 与 Grounding Check 的准确率与阈值。

[低] 评估体系

• 实现 evaluation/ 下的评估脚本（Hit Rate、MRR、RAGAS 等）。

[OK] 已完成

• Embedding 模型与维度确认：确认 RAG_database 与 rag_chain_qwen.py 中模型与维度设置一致，避免向量不匹配。[OK] DONE

IV. Chrome 插件 (my-extension)

[高] 核心功能实现

• 实现课程规划、添加、移除功能。

• 实现 content_script.js 与 background.js 的交互，支持自动选课。

[中] 状态管理与鲁棒性

• 增强选课流程的状态管理与错误恢复机制。

• 优化 DOM 选择器与加载等待逻辑。

• 确保 \_\_apiRunner 与 token 获取逻辑稳定。

[中] 安全

• 检查脚本间通信的安全性，防止敏感数据泄露。

• 在 background.js 中添加消息验证。

[低] 代码复用

• 将 popup-utils.js 的加密/解密函数提取到共享库，与前端共用。

[低] UI/UX

• 优化 popup.html 与 popup.css，增加清晰的操作反馈。

V. 爬虫 (crawler)

[中] 健壮性与维护

• 增强错误处理与日志记录。

• 添加数据验证步骤。

• 定期检测 UNSW Handbook 结构变化。

• 优化 \_extract_embedded_json 与 DOM 回退逻辑。

[低] 效率

• 评估并优化并发参数 (MAX_WORKERS) 与延迟策略。
