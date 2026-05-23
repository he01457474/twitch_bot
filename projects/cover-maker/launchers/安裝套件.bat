@echo off
chcp 65001 > nul
echo 安裝歌詞工具所需套件...
py -m pip install requests opencc-python-reimplemented
echo.
echo 安裝完成，請關閉此視窗。
pause
