### [START] v1.0 部署与服务器配置 TODO List

#### [ ] 1. 容器化 (Docker)

- **目标**: 将你的 Django 后端和 React 前端打包成可移植、可重现的镜像。
- **文件**: `Dockerfile` (后端), `Dockerfile.frontend`, `docker-compose.yml`
- **TODOs**:
  - [ ] **后端 `Dockerfile`**:
    - 使用 `python:3.10` (或你的版本) 作为基础镜像。
    - 安装 `requirements.txt`。
    - **关键**: 确保 `CMD` 或 `ENTRYPOINT` 使用 `uvicorn` 启动 ASGI 服务（例如: `uvicorn backend.asgi:application --host 0.0.0.0 --port 8000`）。
  - [ ] **前端 `Dockerfile.frontend`** (如果需要单独部署):
    - 使用 `node:20` (或你的版本) 作为 `build` 阶段。
    - `RUN npm install` 和 `RUN npm run build`。
    - 使用 `nginx:alpine` (或类似) 作为最终阶段，并从 `build` 阶段 `COPY` 编译好的静态文件（`dist` 目录）。
  - [ ] **`docker-compose.yml`**:
    - 编排你的 `backend` 和 `nginx` 服务。
    - （_注意_：生产环境**强烈建议**使用“托管”的 MySQL 和 Redis，而不是在 `docker-compose.yml` 中启动它们）。

#### [ ] 2. 生产服务器配置 (Nginx)

- **目标**: 设置 Nginx 作为反向代理，处理 HTTP 请求、提供静态文件和终止 SSL (HTTPS)。
- **文件**: `/etc/nginx/sites-available/your_project`
- **TODOs**:
  - [ ] **安装 Nginx**: `sudo apt install nginx`。
  - [ ] **配置反向代理**:
    - `location / { ... }`: 将根路径 `/` 指向 React 的 `index.html` (由 Docker 镜像中的 Nginx 或你宿主机的 Nginx 提供服务)。
    - `location /api/ { ... }`: **(关键)** 代理所有 `/api/` 请求到后端的 Uvicorn (例如 `proxy_pass http://127.0.0.1:8000;`)。
    - `location /static/ { ... }`: （可选）配置 Nginx 直接提供 Django 的静态文件（`staticfiles` 目录）。
  - [ ] **(关键)** **配置 WebSocket 代理**: 你的聊天流 (`StreamingHttpResponse`) 需要 Nginx 正确代理。在 `/api/chat/` (或你的聊天 URL) 的 `location` 块中添加：
    ```nginx
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_buffering off; # 必须关闭缓冲
    proxy_cache off; # 必须关闭缓存
    ```

#### [ ] 3. 生产服务 (MySQL & Redis)

- **目标**: 建立稳定、可备份的生产数据库和缓存。
- **TODOs**:
  - [ ] **MySQL**:
    - **(推荐)** 使用云服务 (如 AWS RDS, DigitalOcean Managed Database)。
    - （_备选_）在服务器上 `sudo apt install mysql-server`。
    - 创建生产数据库 `CREATE DATABASE your_prod_db;`。
    - 创建专用的生产用户 `CREATE USER 'prod_user'@'%' IDENTIFIED BY '...';` 并授予权限 `GRANT ALL PRIVILEGES ON your_prod_db.* TO 'prod_user'@'%';`。
  - [ ] **Redis**:
    - **(推荐)** 使用云服务 (如 AWS ElastiCache, DigitalOcean Managed Redis)。
    - （_备选_）在服务器上 `sudo apt install redis-server`。
    - 配置 Redis 密码并持久化（如果需要）。

#### [ ] 4. 最终配置与安全

- **目标**: 使用环境变量连接所有服务，并启用 HTTPS。
- **文件**: `.env.prod` (在服务器上)
- **TODOs**:

  - [ ] **创建 `.env.prod` 文件**: 这个文件**绝不能**提交到 Git。

    ```env
    DEBUG=False
    SECRET_KEY=... (生成一个新的强密钥)
    ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

    # 生产 MySQL (来自 TODO 3)
    DB_HOST=... (你的 RDS 地址或 127.0.0.1)
    DB_NAME=your_prod_db
    DB_USER=prod_user
    DB_PASSWORD=...

    # 生产 Redis (来自 TODO 3)
    REDIS_HOST=... (你的 ElastiCache 地址或 127.0.0.1)
    REDIS_PORT=6379

    # 你的 LLM API 密钥
    QWEN_API_KEY=...
    DASHSCOPE_API_KEY=...
    ```

  - [ ] **HTTPS (SSL)**:
    - 在 Nginx 上使用 `certbot` (Let's Encrypt) 自动配置免费的 SSL 证书。
    - `sudo apt install certbot python3-certbot-nginx`
    - `sudo certbot --nginx -d yourdomain.com`
  - [ ] **防火墙 (UFW)**:
    - `sudo ufw allow 'Nginx Full'` (允许 80/443 端口)。
    - `sudo ufw allow OpenSSH`。
    - `sudo ufw enable`。

#### [ ] 5. 启动 (Launch\!)

- **目标**: 在生产服务器上运行应用。
- **TODOs**:
  - [ ] **拉取代码/镜像**: `git pull` 或 `docker pull`。
  - [ ] **运行数据库迁移**: `docker-compose exec backend python manage.py migrate`。
  - [ ] **收集静态文件**: `docker-compose exec backend python manage.py collectstatic --noinput`。
  - [ ] **启动服务**: `docker-compose -f docker-compose.prod.yml up -d` (如果你使用 `docker-compose` 部署)。

---

### [START] 前端重构准备 TODO

- **[ ] 7. (前端) 实现基于路由的代码分割 (Code Splitting)**

  - _目标_：减小 v1.0 的初始 JS 包体积，加快首页加载。
  - _涉及文件_:
    - `frontend/src/App.tsx` (对 `SettingsPage` 等非核心页面使用 `React.lazy` 和 `<Suspense>`)

- **UI 适配**

  - `frontend/src/components/Chat/MessageItem.tsx`：检查 `message.metadata.retrieved_docs`，若存在显示“查看引用”按钮。
  - `frontend/src/components/RightPanel/RightPanel.tsx`：点击“查看引用”则从 message metadata 中读取并展示 `ResultCard`。

## dockerfile

---

## P2 / P3（中低优先，可并行推进）

### 多模态 Offer 解析（免修课程图首版）

- **新增** `backend/chatbot/services/multimodal_parser.py`

  - `parse_offer_image(image_file)`：图片 -> base64 -> 调用多模态模型（例如 qwen-vl），要求模型只返回 JSON：`{"courses":[...],"confidence":"high"|"low"}` -> 返回 dict。

- **新增 endpoint** `backend/chatbot/views.py`

  - `POST /api/chatbot/offers/`：接收图片，调用 parser。
  - 高置信度：自动合并 `exemptions` 到学生信息并保存；低置信度：写入 `pending_offer_confirmation`，返回 `status: pending_confirmation` 给前端确认。
  - 合并流程需 emit `profile.updated` SSE。

- **置信度策略说明**：高置信度自动写内存，低置信度走前端确认。

## 部署与运维清单（部署前核对项）

（列出要点供上线前检查；具体部署步骤不在此约定时间表）

- 域名与服务器（购买/选择云商）
- 防火墙/端口（22/80/443）
- Redis（托管或自建）
- 数据库：Postgres（托管/自建）并为 Django 创建用户与 DB
- SSL（certbot）
- 环境变量 `.env`：`DJANGO_SECRET_KEY`, `DASHSCOPE_API_KEY`, `QWEN_BASE_URL`, `DATABASE_URL`, `REDIS_URL`, `SERVER_MASTER_KEY`, `MEDIA_ROOT` 等
- Gunicorn + Nginx 配置（反向代理、静态与 media 服务）
- 前端构建（`npm run build`）与部署（Vercel/Netlify 或服务器上托管）
- 启动验证：`makemigrations` / `migrate` / `collectstatic` / Gunicorn 启动 / Nginx 配置生效

---

## 小结（便于 PR / Code Review）

- 按 **P0** 优先完成混合检索 + 重排、数据契约（TypedDict/Pydantic）与 SSE（retrieve 的 `rag.preview` 必须先实现）。
- **P1** 做自适应重写与工具失败重规划，提升鲁棒性。
- 前端需同步改为完整会话状态驱动（后端发 final_state 覆盖本地状态）。
- 每次修改都写入或更新 `sse_events`，方便前端可视化流程状态。

---
