# HTML Drop

个人使用的 HTML / ZIP 静态页面发布服务。上传文件后生成可访问链接，内置管理台可查看丰富访问统计、设置访问密码、生成二维码。

## 功能特性

- **发布页面**：支持 `.html` / `.htm` 单文件与 `.zip` 静态站点（点击选择或直接拖拽上传）
- **访问密码**：发布/编辑时可设置访问密码，访客需输入密码才能访问；可随时移除
- **链接二维码**：发布成功弹窗与列表行均可查看二维码（中心嵌品牌 logo），支持下载 PNG
- **访问统计**：PV / UV 双柱图（最近 24 小时按小时 + 7 / 30 / 90 天按日）、峰值日、日均、UV/PV 占比、7 天环比、浏览器 / 设备 / 操作系统 / 访问来源分布、最近访问记录
- **页面管理**：搜索、分页、编辑、替换文件、停止 / 恢复访问、删除
- **安全**：管理 API 令牌认证、密码用 scrypt 哈希、ZIP 解压防路径穿越 / 符号链接 / 炸弹
- **可爱风页面**：停止访问、页面不存在、密码输入页均为定制趣味页面

## 技术栈与工具

| 端 | 技术 | 包管理 |
|---|---|---|
| 后端 | FastAPI + SQLite + uvicorn | [uv](https://docs.astral.sh/uv/) |
| 前端 | React 18 + Vite + TypeScript | [pnpm](https://pnpm.io/) |

## 本地运行

### 1. 启动后端（uv）

```powershell
cd backend
uv venv .venv
uv pip install --python .venv -r requirements.txt
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

> 首次启动会自动建库并创建默认账号 `admin / admin123`。

### 2. 启动前端开发服务器（pnpm）

另开一个终端：

```powershell
cd frontend
pnpm install
pnpm run dev
```

打开 http://localhost:5173（vite 已配置 `/api`、`/p` 代理到 8000）。

> **注意**：管理 API 使用登录时签发的令牌（`X-API-Token` / `Authorization: Bearer`）。令牌保存在当前标签页的 `sessionStorage` 中，刷新页面后可继续保持登录，关闭标签页后失效。

## 配置（环境变量）

复制 `backend/.env.example` 到**项目根目录**并命名为 `.env`（docker compose 启动时自动读取根目录的 `.env`），按需修改：

| 变量 | 说明 |
|---|---|
| `ADMIN_USERNAME` | 管理员账号（默认 `admin`） |
| `ADMIN_PASSWORD` | 管理员密码（默认 `admin123`，**生产务必修改**）。修改后重启即同步生效；也可登录后在管理台左下角「修改密码」 |
| `SESSION_SECRET` | 会话与访问密码 cookie 的签名密钥，**务必设置长随机值**（如 `openssl rand -hex 32`）。未设置时每次重启生成随机密钥（已有会话失效、IP 统计哈希漂移） |
| `PUBLIC_BASE_URL` | 公开链接的完整基址，如 `https://page.example.com`；留空则使用请求来源 |
| `TZ` | 容器时区（仅 Docker 部署生效，默认 `Asia/Shanghai`） |

## 使用说明

- **发布页面**：概览页选择/拖拽文件 → 填写页面名称、备注、访问密码（可选）→ 立即发布；成功后弹窗提供复制链接、打开页面、下载二维码
- **我的页面**：列表支持搜索与完整分页（页码跳转、省略号折叠、共 N 条）；每行操作：打开、查看二维码、复制链接、更多（统计 / 编辑 / 停止或恢复 / 删除）
- **访问统计**：点击「查看统计」查看 PV/UV 双柱图与多维度分析
- **访问密码**：设置后访客先看到密码输入页（可爱风），验证成功签发 30 天 cookie；修改密码后旧 cookie 立即失效
- **修改密码**：左下角账号区「修改密码」（校验旧密码，新密码至少 6 位）

## 上传格式

- `.html` / `.htm`：作为单文件页面发布。
- `.zip`：作为静态站点发布，ZIP 根目录需要有 `index.html`；也支持 ZIP 只有一个顶层目录且该目录中包含 `index.html`。
- ZIP 解压后会限制在 100MB、最多 500 个文件，并拒绝路径穿越和符号链接；上传单文件限制 50MB。

## 管理 API 一览

除公开页面（`/p/{slug}`）外，所有 `/api/*` 管理接口需携带登录返回的令牌请求头：

| 接口 | 说明 |
|---|---|
| `POST /api/auth/login` | 登录，返回 `api_token`（内存令牌） |
| `GET /api/auth/me` | 当前用户信息（含 `default_password` 标记） |
| `POST /api/auth/password` | 修改密码（旧密码 + 新密码 ≥ 6 位） |
| `POST /api/auth/logout` | 登出（使令牌失效） |
| `GET /api/links` | 分页列表（`page` / `page_size`） |
| `GET /api/links/summary` | 汇总（总数 / 总浏览量 / 活跃数） |
| `POST /api/links` | 发布页面（multipart：文件 + 名称 + 备注 + 密码可选） |
| `PATCH /api/links/{id}` | 编辑（`password` 留空不修改，`clear_password=1` 移除密码） |
| `POST /api/links/{id}/upload` | 替换文件（失败不丢失原内容） |
| `POST /api/links/{id}/enable` / `disable` | 恢复 / 停止访问 |
| `DELETE /api/links/{id}` | 删除（同时清理文件） |
| `GET /api/links/{id}/stats` | 访问统计（日/小时、PV/UV、分布、最近访问） |
| `GET /api/health` | 健康检查 |

## 测试

```powershell
# 后端（pytest，隔离临时数据库，不会污染数据）
cd backend
uv pip install --python .venv pytest pytest-asyncio httpx
uv run python -m pytest

# 前端（vitest + Testing Library）
cd frontend
pnpm test
```

## 生产构建与部署

### 方式一：Docker 部署（推荐）

项目已内置多阶段 Dockerfile（Node 构建前端 → Python 运行后端）与 docker-compose：

```powershell
# Windows（PowerShell）
.\scripts\deploy.ps1

# Linux / macOS
bash scripts/deploy.sh
```

脚本会自动：生成 `.env`（首次）→ 构建镜像 → 启动容器 → 等待健康检查通过。

也可以手动执行：

```powershell
# 1. 准备环境变量（首次，复制到项目根目录）
Copy-Item backend\.env.example .env
# 编辑 .env：务必修改 ADMIN_PASSWORD 与 SESSION_SECRET

# 2. 构建并启动（多阶段构建：Node + pnpm（frozen-lockfile 可复现）构建前端 → Python 运行）
docker compose up -d --build

# 3. 查看状态 / 日志 / 停止
docker compose ps
docker compose logs -f html-drop
docker compose down
```

数据持久化：`backend/data`（SQLite 数据库）与 `backend/uploads`（发布文件）已挂载到宿主机，容器重建不丢数据。镜像内置健康检查（`/api/health`）。

### 方式二：直接运行

```powershell
cd frontend
pnpm install
pnpm run build        # tsc 类型检查 + vite 打包到 frontend/dist
cd ..
uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

构建完成后 FastAPI 会自动托管 `frontend/dist`。

## 外网访问与安全

- 公开页面路径为 `/p/{随机标识}`；个人使用可把 8000 端口通过 Cloudflare Tunnel、frp 或 Nginx 暴露出去。
- **同源风险**：管理台与公开页面共用同一服务。管理接口除会话 cookie 外还要求 API 令牌；令牌为当前标签页的 `sessionStorage`，因此刷新可保持登录，但同源公开页面的脚本理论上可能读取它。对不可信公开页面，建议将公开页面反代到独立域名（如 `page.example.com`），管理台保持独立。
- 上线前务必：修改默认密码、设置 `SESSION_SECRET`、按需配置 `PUBLIC_BASE_URL`。
