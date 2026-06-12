@echo off
REM Run: 双击此文件，或复制到不含中文的路径运行
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "deploy-remote-v2.ps1"
pause
