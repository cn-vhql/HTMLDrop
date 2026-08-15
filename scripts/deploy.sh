#!/usr/bin/env bash
# HTML Drop Docker 部署脚本（Linux / macOS）
# 用法：bash scripts/deploy.sh
set -euo pipefail

cd "$(dirname "$0")/.."

# 1. 首次运行生成 backend/.env（已存在则跳过）
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "=================================================="
  echo " 已生成 backend/.env"
  echo " 请编辑该文件，修改 ADMIN_PASSWORD 与 SESSION_SECRET"
  echo " 请修改后再启动，尤其是 ADMIN_PASSWORD 与 SESSION_SECRET"
  echo "=================================================="
fi

# 2. 构建并启动（--build 保证使用最新镜像）
echo ">>> 构建并启动容器..."
docker compose up -d --build

# 3. 等待健康检查通过
echo ">>> 等待服务就绪..."
for _ in $(seq 1 20); do
  if curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://127.0.0.1:20080/api/health 2>/dev/null | grep -q "200"; then
    echo "✔ 部署成功：http://127.0.0.1:20080"
    exit 0
  fi
  sleep 3
done

echo "⚠ 服务未在 60 秒内就绪，请检查日志：docker compose logs html-drop"
exit 1
