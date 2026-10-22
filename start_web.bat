@echo off
chcp 65001 >nul
title J.A.R.V.I.S. Web 版启动器
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.9 及以上版本。
    pause
    exit /b 1
)
echo ==============================================
echo    J.A.R.V.I.S. Web 版（局域网可访问）
echo ==============================================
python start_web.py
pause
