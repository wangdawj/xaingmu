# 校园能耗监测平台 - Docker 一键启动脚本
# 使用方法: 右键此文件 -> "使用 PowerShell 运行"，或在 PowerShell 中执行 .\start-docker.ps1

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

$dockerExe = "E:\ZhouMIan\docker\resources\bin\docker.exe"
$dockerDesktop = "E:\ZhouMIan\docker\Docker Desktop.exe"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  校园能耗监测平台 - Docker 部署" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 启动 Docker Desktop
Write-Host "[1/4] 启动 Docker Desktop..." -ForegroundColor Yellow
$dockerProcess = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
if (-not $dockerProcess) {
    Start-Process $dockerDesktop
    Write-Host "  Docker Desktop 正在启动，等待引擎就绪..."
}

# 2. 等待 Docker 引擎
Write-Host "[2/4] 等待 Docker 引擎就绪..." -ForegroundColor Yellow
$maxWait = 120
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

# 3. 配置镜像加速（如需要）
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

# 4. 启动项目
Write-Host "[4/4] 启动项目容器..." -ForegroundColor Yellow
Push-Location "E:\develop\workspace\xiangmu"
Write-Host "  执行: docker compose up -d"
Write-Host "  (首次运行会拉取镜像，可能需要 5-20 分钟)" -ForegroundColor DarkYellow
Write-Host ""
& $dockerExe compose up -d 2>&1 | ForEach-Object { Write-Host "  $_" }

Pop-Location

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  启动完成！" -ForegroundColor Green
Write-Host "  前端访问: http://localhost:8080" -ForegroundColor White
Write-Host "  后端 API: http://localhost:5000" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
pause
