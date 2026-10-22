@echo off
chcp 65001 >nul
title J.A.R.V.I.S. 桌面智能助理
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.9 及以上版本，并勾选 "Add python.exe to PATH"。
    pause
    exit /b 1
)

echo ==============================================
echo    J.A.R.V.I.S. 桌面智能助理  一键启动
echo ==============================================
python start.py
pause
