@echo off
chcp 65001 > nul
echo 安裝歌詞工具所需套件...
"D:\tset\FlyCatClaude Code\.tools\python-3.13.3-embed\python.exe" -m pip install requests opencc-python-reimplemented
echo.
echo 安裝完成，請關閉此視窗。
pause
