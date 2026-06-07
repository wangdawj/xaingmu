@echo off
chcp 65001 >nul
title 校园能耗监测平台 - Docker 部署

echo ========================================
echo   校园能耗监测平台 - Docker 一键部署
echo ========================================
echo.
echo 镜像存储位置: E:\ZhouMIan\docker_images\DockerDesktopWSL
echo.

REM 检查 Docker Desktop 是否已运行
tasklist /FI "IMAGENAME eq Docker Desktop.exe" 2>NUL | find /I /N "Docker Desktop.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo Docker Desktop 已在运行
    goto check_engine
)

echo [1/3] 启动 Docker Desktop...
start "" "E:\ZhouMIan\docker\Docker Desktop.exe"

:check_engine
echo [2/3] 等待 Docker 引擎就绪（约 1-2 分钟）...
set /a count=0
:wait_docker
timeout /t 5 /nobreak >nul
set /a count+=5
"E:\ZhouMIan\docker\resources\bin\docker.exe" version >nul 2>&1
if %errorlevel% equ 0 goto docker_ready
if %count% lss 180 goto wait_docker
echo Docker 启动超时！
echo 请手动打开 Docker Desktop 并等待引擎启动完成后再运行此脚本。
pause
exit /b 1

:docker_ready
echo [OK] Docker 引擎已就绪！

echo.
echo [3/3] 拉取镜像并启动容器...
echo 首次运行需要下载约 2GB 镜像，请耐心等待...
echo 如果下载失败，请在 Docker Desktop 设置中添加国内镜像加速:
echo   Settings -^> Docker Engine -^> 添加:
echo   "registry-mirrors": ["https://docker.1panel.live"]
echo.
cd /d "E:\develop\workspace\xiangmu"
"E:\ZhouMIan\docker\resources\bin\docker.exe" compose up -d
if %errorlevel% neq 0 (
    echo.
    echo 启动失败！请检查网络连接或配置镜像加速后重试。
    pause
    exit /b 1
)

echo.
echo ========================================
echo   [成功] 所有容器已启动！
echo.
echo   前端页面: http://localhost:8080
echo   后端 API:  http://localhost:5000
echo.
echo   查看状态: docker compose ps
echo ========================================
pause
