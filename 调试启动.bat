@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === yt-dlp 图形用户界面 调试模式 ===
python -m app.main
echo.
echo === 程序已退出，按任意键关闭窗口 ===
pause >nul
