@echo off
chcp 65001 > nul
title SLS监控系统

echo ========================================
echo     🚀 SLS监控系统启动器
echo ========================================
echo.

echo 检查Python环境...
python --version > nul 2>&1
if errorlevel 1 (
    echo ❌ Python未安装或未添加到PATH
    echo 请安装Python 3.8+并添加到系统PATH
    pause
    exit /b 1
)

echo ✅ Python环境正常

echo.
echo 检查依赖包...
python -c "import cv2, numpy, serial, crcmod, cmapy, matplotlib, tkinter" > nul 2>&1
if errorlevel 1 (
    echo ⚠️ 部分依赖包缺失，正在安装...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ 依赖安装失败
        pause
        exit /b 1
    )
)

echo ✅ 依赖包完整

echo.
echo 启动SLS监控系统...
echo ========================================
python run.py

echo.
echo 系统已退出
pause