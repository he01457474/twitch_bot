# 管理員用：關閉 IRL 中繼伺服器環境
chcp 65001 | Out-Null

Write-Host "關閉 IRL 中繼伺服器環境..." -ForegroundColor Cyan
Write-Host "這是管理員端腳本，不會關閉借用者電腦上的 NOALBS。" -ForegroundColor DarkGray

# MediaMTX 本機版
$mediamtx = Get-Process "mediamtx" -ErrorAction SilentlyContinue
if ($mediamtx) {
    Stop-Process -Name "mediamtx" -Force
    Write-Host "MediaMTX 已關閉" -ForegroundColor Green
} else {
    Write-Host "MediaMTX 未在執行" -ForegroundColor DarkGray
}

# No-IP DUC
$duc = Get-Process "DUC40" -ErrorAction SilentlyContinue
if ($duc) {
    Stop-Process -Name "DUC40" -Force
    Write-Host "No-IP DUC 已關閉" -ForegroundColor Green
} else {
    Write-Host "No-IP DUC 未在執行" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "中繼伺服器環境已關閉完成。" -ForegroundColor Cyan
Start-Sleep -Seconds 8
