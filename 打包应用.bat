@echo off
chcp 65001 >nul
echo.
echo ===================================
echo   IntelliAnnotate 应用打包工具
echo ===================================
echo.

echo 正在检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误: 未检测到Python环境
    echo 请确保已安装Python并添加到PATH环境变量
    pause
    exit /b 1
)

echo 正在检查依赖库...
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo 🔧 安装PyInstaller...
    pip install pyinstaller
)

echo.
echo 🚀 开始打包应用...
python build.py

echo.
echo 按任意键退出...
pause >nul 