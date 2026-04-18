# 關閉直播環境腳本
chcp 65001 | Out-Null

Write-Host "關閉直播環境..." -ForegroundColor Cyan

# NOALBS
$noalbs = Get-Process "noalbs" -ErrorAction SilentlyContinue
if ($noalbs) {
    Stop-Process -Name "noalbs" -Force
    Write-Host "NOALBS 已關閉" -ForegroundColor Green
} else {
    Write-Host "NOALBS 未在執行" -ForegroundColor DarkGray
}

# mediamtx 容器
Write-Host "停止 mediamtx 容器..."
docker stop mediamtx 2>&1 | Out-Null
Write-Host "mediamtx 已停止" -ForegroundColor Green

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
    # 停服務
    Stop-Service "com.docker.service" -Force -ErrorAction SilentlyContinue
    # 殺所有 Docker 相關程序（backend 會重啟 UI，要一起清）
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
Write-Host "全部關閉完成！" -ForegroundColor Cyan
Start-Sleep -Seconds 8
