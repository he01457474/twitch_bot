@echo off
chcp 65001 >nul
setlocal
title Repair FlyCat Bot Update

echo ========================================
echo   Repair FlyCat Bot Update
echo ========================================
echo.
echo This fixes old update_bot.bat paths after moving the BOT folder.
echo.

echo [1/3] Checking Git repo...
git rev-parse --is-inside-work-tree >nul 2>nul
if %errorlevel% neq 0 (
    echo This folder is not a Git repo. Put this file in repo_temp and run it there.
    pause
    exit /b 1
)

for /f "delims=" %%I in ('git rev-parse --show-toplevel') do set "REPO_DIR=%%I"
if not exist "%REPO_DIR%\update_bot.bat" (
    echo Cannot find update_bot.bat in: %REPO_DIR%
    echo Put this file in the BOT repo_temp folder and run it there.
    pause
    exit /b 1
)

cd /d "%REPO_DIR%" || (
    echo Cannot enter BOT repo folder: %REPO_DIR%
    pause
    exit /b 1
)

echo [2/3] Pulling portable update scripts...
git fetch origin
if %errorlevel% neq 0 (
    echo Failed to fetch from GitHub. Check network or GitHub permission.
    pause
    exit /b 1
)

git reset --hard origin/master
if %errorlevel% neq 0 (
    echo Failed to reset to origin/master.
    pause
    exit /b 1
)

echo.
echo [3/3] Starting repaired update_bot.bat...
call "%REPO_DIR%update_bot.bat"
