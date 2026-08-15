# 阶段 1：构建前端（pnpm + lockfile 可复现）
FROM node:22-alpine AS frontend-builder
RUN corepack enable && corepack prepare pnpm@10 --activate
WORKDIR /build/frontend
# 先只拷贝依赖清单，充分利用构建缓存
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend ./
RUN pnpm run build

# 阶段 2：运行后端
FROM python:3.11-slim
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
