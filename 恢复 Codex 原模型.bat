@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title 恢复 Codex 原模型

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap-windows.ps1" -Mode restore
set "RESTORE_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %RESTORE_RESULT%
