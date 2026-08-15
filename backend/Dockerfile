# 阶段 1：构建前端（pnpm + lockfile 可复现）
# 默认使用国内镜像，避免 Docker Hub 在当前服务器上连接超时；需要时可通过
# --build-arg NODE_BASE_IMAGE=... 切换到其他兼容的 Node 镜像。
ARG NODE_BASE_IMAGE=docker.m.daocloud.io/library/node:22-alpine
ARG PYTHON_BASE_IMAGE=docker.m.daocloud.io/library/python:3.11-slim
FROM ${NODE_BASE_IMAGE} AS frontend-builder
RUN corepack enable && corepack prepare pnpm@10 --activate
WORKDIR /build/frontend
# 先只拷贝依赖清单，充分利用构建缓存
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend ./
RUN pnpm run build

# 阶段 2：运行后端
FROM ${PYTHON_BASE_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend ./backend
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist
RUN mkdir -p backend/data backend/uploads
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
