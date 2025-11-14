@echo off
chcp 65001 >nul
echo ╔════════════════════════════════════════╗
echo ║   Claude Chat Ultimate - 啟動器        ║
echo ╔════════════════════════════════════════╗
echo.

REM 檢查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未檢測到Python
    echo 請先從 https://www.python.org/ 下載並安裝Python 3.7+
    echo.
    pause
    exit /b
)

echo ✅ Python已安裝
echo.

REM 檢查並安裝依賴
echo 📦 檢查依賴庫...
echo.

REM 必需的庫
python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo [安裝] requests...
    python -m pip install requests
)

REM 可選但推薦的庫
python -c "from PIL import Image" >nul 2>&1
if errorlevel 1 (
    echo [推薦] Pillow (圖片處理)...
    set /p install_pil="是否安裝Pillow? (y/n): "
    if /i "%install_pil%"=="y" python -m pip install Pillow
)

python -c "import PyPDF2" >nul 2>&1
if errorlevel 1 (
    echo [推薦] PyPDF2 (PDF處理)...
    set /p install_pdf="是否安裝PyPDF2? (y/n): "
    if /i "%install_pdf%"=="y" python -m pip install PyPDF2
)

python -c "import docx" >nul 2>&1
if errorlevel 1 (
    echo [推薦] python-docx (Word文檔處理)...
    set /p install_docx="是否安裝python-docx? (y/n): "
    if /i "%install_docx%"=="y" python -m pip install python-docx
)

echo.
echo ✅ 依賴檢查完成
echo.
echo 🚀 啟動Claude Chat Ultimate...
echo.

python claude_chat_ultimate.py

if errorlevel 1 (
    echo.
    echo ❌ 程序執行出錯
    pause
)
