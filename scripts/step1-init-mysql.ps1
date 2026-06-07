# 第一步：初始化 MySQL 业务库
# 用法（PowerShell）：
#   .\scripts\step1-init-mysql.ps1 -RootPassword "你的root密码"

param(
    [Parameter(Mandatory = $true)]
    [string]$RootPassword
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$MysqlBin = "E:\MySQL\MySQL Server 8.0\bin\mysql.exe"

if (-not (Test-Path $MysqlBin)) {
    $MysqlBin = "mysql"  # 回退到 PATH
}

# 确保 MySQL 服务运行
$svc = Get-Service -Name "MySQL80" -ErrorAction SilentlyContinue
if ($svc -and $svc.Status -ne "Running") {
    Write-Host "正在启动 MySQL80 服务..."
    Start-Service MySQL80
    Start-Sleep -Seconds 3
}

Write-Host ">>> 导入表结构与初始数据..."
Get-Content "$ProjectRoot\database\mysql\schema.sql" -Raw -Encoding UTF8 |
    & $MysqlBin -u root "-p$RootPassword" --default-character-set=utf8mb4 2>&1

Write-Host ">>> 创建本地业务用户 energy..."
Get-Content "$ProjectRoot\database\mysql\init_local.sql" -Raw -Encoding UTF8 |
    & $MysqlBin -u root "-p$RootPassword" --default-character-set=utf8mb4 2>&1

Write-Host ">>> 验证连接..."
& $MysqlBin -u energy -penergy123 -e "USE campus_energy; SHOW TABLES;" 2>&1

Write-Host ""
Write-Host "✅ 第一步完成！MySQL 库 campus_energy 已就绪。"
Write-Host "   业务账号: energy / energy123"
Write-Host "   下一步: 初始化 InfluxDB 或启动后端 API"
