# HTML Drop Docker 部署脚本（Windows PowerShell）
# 用法：.\scripts\deploy.ps1
param(
    [switch]$SkipEnv  # 跳过 .env 生成检查
)
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

# 1. 首次运行生成 backend/.env
if (-not $SkipEnv -and -not (Test-Path "backend\.env")) {
    Copy-Item "backend\.env.example" "backend\.env"
    Write-Host "==================================================" -ForegroundColor Yellow
    Write-Host " 已生成 backend/.env" -ForegroundColor Yellow
    Write-Host " 请编辑该文件，修改 ADMIN_PASSWORD 与 SESSION_SECRET" -ForegroundColor Yellow
    Write-Host " 请修改后再启动，尤其是 ADMIN_PASSWORD 与 SESSION_SECRET" -ForegroundColor Yellow
    Write-Host "==================================================" -ForegroundColor Yellow
}

# 2. 构建并启动
Write-Host ">>> 构建并启动容器..."
docker compose up -d --build

# 3. 等待健康检查
Write-Host ">>> 等待服务就绪..."
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 3
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:20080/api/health" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) {
            Write-Host "✔ 部署成功：http://127.0.0.1:20080" -ForegroundColor Green
            exit 0
        }
    } catch { }
}
Write-Host "⚠ 服务未在 60 秒内就绪，请检查日志：docker compose logs html-drop" -ForegroundColor Red
exit 1
