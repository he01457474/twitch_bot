@echo off
chcp 65001 >nul
echo ========================================
echo   FlyCat Bot 部署腳本
echo ========================================
echo.

:: ── 1. 推送網站與 Netlify Function 到公開 repo ──
echo [1/3] 更新指令手冊 (index.html)...
cd /d "D:\tset\FlyCatClaude Code"
git add index.html deploy.bat netlify.toml netlify/functions/twitch-admins.mjs
git diff --cached --quiet && (echo   沒有變更，略過) || (git commit -m "update: 更新指令手冊" && git push origin master && echo   OK)
echo.

:: ── 2. 複製 3.py 並推送到私有 repo ──
echo [2/3] 更新機器人程式碼 (3.py)...
copy /Y "D:\tset\FlyCatClaude Code\3.py" "D:\tset\bot_private\src\test.py" >nul
cd /d "D:\tset\bot_private"
git add src/test.py
git diff --cached --quiet && (echo   沒有變更，略過) || (git commit -m "update: 更新 bot 程式碼" && git push origin master && echo   OK)
echo.

:: ── 3. 提示去另一台更新 ──
echo [3/3] 完成！
echo.
echo   請到 LAPTOP-6N12C053 執行 update_bot.bat 重啟 BOT
echo.
echo 按任意鍵關閉視窗...
pause >nul
