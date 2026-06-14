# =============================================================================
# 校园综合能耗监测平台 — Docker 一键部署脚本 (PowerShell)
# =============================================================================
# 功能:
#   1. 启动 Docker Desktop
#   2. 等待 Docker 引擎就绪
#   3. 检查 Docker 镜像加速配置
#   4. 执行 docker compose up -d 启动所有容器
#
# 使用方法:
#   方式 1 (推荐): 右键此文件 -> "使用 PowerShell 运行"
#   方式 2: 在 PowerShell 中执行 .\start-docker.ps1
#
# 前提条件: Docker Desktop 已安装在 E:\ZhouMIan\docker\
# =============================================================================

# 临时绕过当前进程的执行策略限制
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

# Docker 路径配置
$dockerExe = "E:\ZhouMIan\docker\resources\bin\docker.exe"
$dockerDesktop = "E:\ZhouMIan\docker\Docker Desktop.exe"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  校园能耗监测平台 - Docker 部署" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ======================== 步骤 1：启动 Docker Desktop ========================
Write-Host "[1/4] 启动 Docker Desktop..." -ForegroundColor Yellow
$dockerProcess = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
if (-not $dockerProcess) {
    Start-Process $dockerDesktop
    Write-Host "  Docker Desktop 正在启动，等待引擎就绪..."
}

# ======================== 步骤 2：等待 Docker 引擎就绪 ========================
Write-Host "[2/4] 等待 Docker 引擎就绪..." -ForegroundColor Yellow
$maxWait = 120      # 最大等待 120 秒
$waited = 0
do {
    Start-Sleep -Seconds 5
    $waited += 5
    $result = & $dockerExe version 2>&1
    $ready = $LASTEXITCODE -eq 0 -and $result -match "Server:"
    if ($waited -gt $maxWait) {
        Write-Host "  Docker 启动超时，请检查 Docker Desktop 是否正常运行" -ForegroundColor Red
        pause
        exit 1
    }
} while (-not $ready)
Write-Host "  Docker 引擎已就绪!" -ForegroundColor Green

# ======================== 步骤 3：检查镜像加速配置 ========================
Write-Host "[3/4] 检查镜像配置..." -ForegroundColor Yellow
$daemonFile = "$env:USERPROFILE\.docker\daemon.json"
if (Test-Path $daemonFile) {
    $daemonJson = Get-Content $daemonFile -Raw | ConvertFrom-Json
    if (-not $daemonJson.'registry-mirrors') {
        Write-Host "  未配置镜像加速，请在 Docker Desktop 设置中手动添加:"
        Write-Host "    Settings -> Docker Engine -> 添加 registry-mirrors" -ForegroundColor Cyan
        Write-Host "    推荐镜像: https://docker.1panel.live" -ForegroundColor Cyan
    }
}

# ======================== 步骤 4：执行 docker compose up ========================
Write-Host "[4/4] 启动项目容器..." -ForegroundColor Yellow
Push-Location "E:\develop\workspace\xiangmu"
Write-Host "  执行: docker compose up -d"
Write-Host "  (首次运行会拉取镜像，可能需要 5-20 分钟)" -ForegroundColor DarkYellow
Write-Host ""
& $dockerExe compose up -d 2>&1 | ForEach-Object { Write-Host "  $_" }

Pop-Location

# ======================== 启动成功提示 ========================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  启动完成！" -ForegroundColor Green
Write-Host "  前端访问: http://localhost:8080" -ForegroundColor White
Write-Host "  后端 API: http://localhost:5000" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
pause
