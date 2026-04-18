@echo off
echo ========================================
echo   FlyCat Mobile Terminal
echo   http://100.122.13.69:7681
echo ========================================
echo.
"C:\Users\he014\AppData\Local\Microsoft\WinGet\Packages\tsl0922.ttyd_Microsoft.Winget.Source_8wekyb3d8bbwe\ttyd.exe" --port 7681 --interface 0.0.0.0 --writable --t rendererType=canvas --t cols=80 --t rows=30 cmd /k "cd /d "D:\tset\FlyCatClaude Code" && claude"
