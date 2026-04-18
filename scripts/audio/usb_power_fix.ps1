[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

Write-Host '正在關閉 Halo PixelBar USB 省電模式...' -ForegroundColor Cyan
Write-Host ''

$found = $false
Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Enum\USB' |
    Where-Object { $_.PSChildName -like 'VID_2D99*' } |
    ForEach-Object {
        Get-ChildItem $_.PSPath | ForEach-Object {
            $dp = $_.PSPath + '\Device Parameters'
            if (Test-Path $dp) {
                Set-ItemProperty -Path $dp -Name 'EnhancedPowerManagementEnabled' -Value 0 -Type DWord -Force -ErrorAction SilentlyContinue
                Write-Host ('  OK: ' + $_.PSChildName) -ForegroundColor Green
                $found = $true
            }
        }
    }

Write-Host ''
if ($found) {
    Write-Host '裝置省電已關閉！' -ForegroundColor Green
} else {
    Write-Host '找不到喇叭裝置，請確認喇叭已插上。' -ForegroundColor Red
}

Write-Host ''
Write-Host '關閉電源計畫 USB 選擇性暫停...' -ForegroundColor Cyan
powercfg /SETACVALUEINDEX SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
powercfg /SETDCVALUEINDEX SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
powercfg /SETACTIVE SCHEME_CURRENT
Write-Host '  OK' -ForegroundColor Green

Write-Host ''
Write-Host '完成！請重新插拔喇叭 USB 讓設定生效。' -ForegroundColor Yellow
Write-Host ''
Read-Host '按 Enter 關閉'
