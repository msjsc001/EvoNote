@echo off
chcp 65001 >nul
title EvoNote Launcher
echo.
echo  ◈ EvoNote - 正在启动开发服务器...
echo.
cd /d "%~dp0app"
npm run tauri dev
pause
