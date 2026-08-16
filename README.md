# HTML Drop

> 把Html，变成链接。

[English](README.en.md)

HTML Drop 是一个面向个人使用的 HTML / ZIP 静态页面发布服务：上传一个页面，拿到一个链接；需要时加访问密码、看访问统计、扫二维码，事情就这么简单。

这个项目参考了 [Cloudflare Drop](https://drop.cloudflare.com/) 的轻量发布思路，尝试提供一个可以自己部署、自己掌握数据的开源个人版 Cloudflare Drop。

## 目录

- [功能](#功能)
- [界面截图](#界面截图)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [配置](#配置)
- [上传格式](#上传格式)
- [项目结构](#项目结构)
- [管理 API](#管理-api)
- [测试](#测试)
- [安全提示](#安全提示)
- [许可证](#许可证)

## 功能

- 支持 `.html` / `.htm` 单文件和包含 `index.html` 的 `.zip` 静态站点
- 点击选择或拖拽上传，发布后自动生成公开链接
- 发布页可选访问密码，也可以随时编辑或移除密码
- 管理台支持搜索、分页、编辑、替换文件、停止 / 恢复和删除
- 提供 PV / UV、每日访问、最近 24 小时、浏览器、设备、系统和来源统计；UV 使用第一方访客 Cookie 粗略统计，所有时间按北京时间显示
- 发布成功后可以复制链接、打开页面、查看二维码和下载二维码图片
- 使用 SQLite 保存数据，不需要额外数据库服务
- ZIP 解压具备路径穿越、符号链接、文件数量和总大小限制

## 界面截图

登录页：

<img src="docs/images/login.png" alt="HTML Drop 登录页" width="960">

概览和发布页：

<img src="docs/images/dashboard.png" alt="HTML Drop 概览和发布页" width="960">

页面管理列表：

<img src="docs/images/pages.png" alt="HTML Drop 页面管理列表" width="960">

访问统计：

<img src="docs/images/analytics.png" alt="HTML Drop 访问统计" width="960">

## 技术栈

| 部分 | 技术                               | 包管理 |
| ---- | ---------------------------------- | ------ |
| 后端 | FastAPI + SQLite + Uvicorn         | uv     |
| 前端 | React 18 + Vite + TypeScript       | pnpm   |
| 部署 | Docker multi-stage build + Compose | Docker |

## 快速开始

### Docker 部署（推荐）

准备本地配置文件：

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`，至少修改 `ADMIN_PASSWORD`、`SESSION_SECRET` 和 `ANALYTICS_SALT`，然后启动：

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f html-drop
```

默认访问地址是 `http://服务器IP:20080`。健康检查地址为 `/api/health`。

停止服务：

```bash
docker compose down
```

也可以使用部署脚本：

```bash
# Linux / macOS
bash scripts/deploy.sh

# Windows PowerShell
.\scripts\deploy.ps1
```

Compose 会从 `backend/.env` 读取容器环境变量。数据库和上传文件默认挂载到宿主机的 `/vol1/data/HTMLDrop/` 下；如果部署目录不同，请按实际环境修改 `docker-compose.yml` 中的挂载路径。

### 本地开发

后端：

```bash
cd backend
uv venv .venv
uv pip install --python .venv -r requirements.txt
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端另开一个终端：

```bash
cd frontend
pnpm install
pnpm run dev
```

打开 `http://localhost:5173`。Vite 已配置 `/api` 和 `/p` 代理到后端 8000 端口。

直接本地运行后端时，需要先把 `backend/.env` 中的变量导出到当前终端；Docker Compose 会自动读取该文件。

## 配置

复制 `backend/.env.example` 为 `backend/.env`，不要把真实的 `backend/.env` 提交到 Git：

| 变量              | 说明                                                                    |
| ----------------- | ----------------------------------------------------------------------- |
| `ADMIN_USERNAME`  | 管理员账号                                                              |
| `ADMIN_PASSWORD`  | 管理员密码，生产环境务必修改                                            |
| `SESSION_SECRET`  | 会话和访问密码 Cookie 的签名密钥，建议使用 `openssl rand -hex 32` 生成  |
| `ANALYTICS_SALT`  | 访客 Cookie 统计标识的哈希密钥，建议使用独立的随机值；修改后新访问会作为新的 UV |
| `PUBLIC_BASE_URL` | 公开链接的完整基址，例如 `https://page.example.com`；留空则使用请求来源 |
| `TZ`              | 容器时区，默认 `Asia/Shanghai`                                          |

修改管理员密码后重启容器即可同步；登录管理台后也可以在左下角直接修改密码。

## 上传格式

- `.html` / `.htm`：作为单文件页面发布。
- `.zip`：作为静态站点发布，ZIP 根目录需要有 `index.html`；也支持只有一个顶层目录且该目录包含 `index.html` 的 ZIP。
- 单文件上传限制为 50 MB。
- ZIP 解压后限制为 100 MB、最多 500 个文件，并拒绝路径穿越和符号链接。

## 项目结构

```text
.
├── backend/
│   ├── app/              # FastAPI 应用、数据库和业务逻辑
│   ├── tests/            # 后端测试
│   ├── .env.example      # 配置模板，真实配置使用 backend/.env
│   ├── Dockerfile        # 前端构建 + 后端运行的多阶段镜像
│   └── requirements.txt
├── frontend/
│   ├── src/              # React 管理台和前端测试
│   ├── package.json
│   └── pnpm-lock.yaml
├── docs/
│   └── images/           # README 截图
├── scripts/              # Linux / PowerShell 部署脚本
├── docker-compose.yml
├── LICENSE               # GPL-3.0
├── README.md             # 中文文档
└── README.en.md          # English documentation
```

运行时数据不放进 Git：SQLite 数据库和上传文件由 Compose 挂载到宿主机目录，`backend/.env` 也已被忽略。

## 管理 API

除公开页面（`/p/{slug}`）外，管理接口需要登录会话和登录返回的 API 令牌。前端会通过 `X-API-Token` 和 `Authorization: Bearer` 发送令牌。

| 接口                                      | 说明                       |
| ----------------------------------------- | -------------------------- |
| `POST /api/auth/login`                    | 登录，返回 `api_token`     |
| `GET /api/auth/me`                        | 当前用户信息和默认密码标记 |
| `POST /api/auth/password`                 | 修改密码                   |
| `POST /api/auth/logout`                   | 登出并使令牌失效           |
| `GET /api/links`                          | 分页获取页面列表           |
| `GET /api/links/summary`                  | 获取页面和浏览量汇总       |
| `POST /api/links`                         | 发布 HTML / ZIP 页面       |
| `PATCH /api/links/{id}`                   | 编辑页面信息或访问密码     |
| `POST /api/links/{id}/upload`             | 替换页面文件               |
| `POST /api/links/{id}/enable` / `disable` | 恢复 / 停止访问            |
| `DELETE /api/links/{id}`                  | 删除页面和对应文件         |
| `GET /api/links/{id}/stats`               | 获取访问统计               |
| `GET /api/health`                         | 健康检查                   |

## 测试

后端测试需要 `pytest`、`pytest-asyncio` 和 `httpx`：

```bash
cd backend
uv pip install --python .venv pytest pytest-asyncio httpx
uv run python -m pytest
```

前端测试：

```bash
cd frontend
pnpm test
```

## 安全提示

- 不要把真实的 `backend/.env`、管理员密码或 `SESSION_SECRET` 提交到仓库。
- UV 基于公开页的第一方访客 Cookie 估算，清理 Cookie、换浏览器或无痕模式会被视为新访客；旧统计记录会回退使用 IP 哈希。统计页面按北京时间显示。
- 管理令牌保存在当前浏览器标签页的 `sessionStorage` 中，刷新页面后仍可保持登录，关闭标签页后失效。
- 同源公开页面的脚本理论上可能读取 `sessionStorage`。如果要托管不可信页面，建议将公开页面反代到独立域名，把管理台和公开内容分开。
- 上线前务必修改管理员密码，并设置随机的 `SESSION_SECRET`。

## 许可证

本项目使用 [GNU General Public License v3.0](LICENSE)（GPL-3.0）发布。

你可以自由使用、修改和再发布，但基于本项目发布的衍生版本也需要按照 GPL-3.0 的要求开放相应源代码。简单说：欢迎拿去折腾，也请把改良后的好东西带回来。
