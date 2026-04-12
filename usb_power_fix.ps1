[Console]::OutputEncoding = [System.Text.Encoding]::GetEncoding(936)
chcp 936 | Out-Null

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
    Write-Host '完成！請重新插拔喭筒 USB 讓設定生效。' -ForegroundColor Yellow
} else {
    Write-Host '找不到喭筒裝置，請確認喭筒已插上。' -ForegroundColor Red
}
Write-Host ''
Read-Host '按 Enter 關閉'