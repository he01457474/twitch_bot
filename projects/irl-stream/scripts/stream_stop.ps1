# 管理員用：關閉 IRL 中繼伺服器環境
chcp 65001 | Out-Null

Write-Host "關閉 IRL 中繼伺服器環境..." -ForegroundColor Cyan
Write-Host "這是管理員端腳本，不會關閉借用者電腦上的 NOALBS。" -ForegroundColor DarkGray

# mediamtx 容器
Write-Host "停止 mediamtx 容器..."
if (Get-Command docker -ErrorAction SilentlyContinue) {
    $exists = docker ps -a --filter "name=^/mediamtx$" --format "{{.Names}}" 2>&1
    if ($LASTEXITCODE -eq 0 -and $exists -match "^mediamtx$") {
        docker stop mediamtx 2>&1 | Out-Null
        Write-Host "mediamtx 已停止" -ForegroundColor Green
    } else {
        Write-Host "找不到 mediamtx 容器，略過" -ForegroundColor DarkGray
    }
} else {
    Write-Host "找不到 docker 指令，略過 mediamtx" -ForegroundColor Yellow
}

# No-IP DUC
$duc = Get-Process "DUC40" -ErrorAction SilentlyContinue
if ($duc) {
    Stop-Process -Name "DUC40" -Force
    Write-Host "No-IP DUC 已關閉" -ForegroundColor Green
} else {
    Write-Host "No-IP DUC 未在執行" -ForegroundColor DarkGray
}

# Docker Desktop（含 backend 守門員）
$docker = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
if ($docker) {
    Write-Host "正在關閉 Docker Desktop..."
    Stop-Service "com.docker.service" -Force -ErrorAction SilentlyContinue
    $dockerProcs = @("Docker Desktop", "com.docker.backend", "com.docker.build", "docker-sandbox", "dockerd")
    foreach ($proc in $dockerProcs) {
        Stop-Process -Name $proc -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
    if (Get-Process "Docker Desktop" -ErrorAction SilentlyContinue) {
        Write-Host "Docker Desktop 仍在執行，請手動確認" -ForegroundColor Yellow
    } else {
        Write-Host "Docker Desktop 已關閉" -ForegroundColor Green
    }
} else {
    Write-Host "Docker Desktop 未在執行" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "中繼伺服器環境已關閉完成。" -ForegroundColor Cyan
Start-Sleep -Seconds 8
