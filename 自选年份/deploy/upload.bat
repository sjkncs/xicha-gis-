@echo off
REM ================================================================
REM upload.bat — 本地打包并上传到服务器
REM ================================================================
REM 运行前提：先运行 build_and_package.bat 生成 deploy_package.zip
REM ================================================================
setlocal EnableDelayedExpansion

cd /d "%~dp0"

REM ── 配置 ──────────────────────────────────────────────────────
SET SERVER=15min.globalreviewops.xyz
SET USER=root
SET KEY=C:\Users\Administrator\.ssh\id_rsa

echo ================================================================
echo  打包 + 上传到 %SERVER%
echo ================================================================

REM ── 1. 检查 deploy_package.zip ────────────────────────────────
echo.
echo [1/3] 检查 deploy_package.zip...
if not exist "deploy_package.zip" (
    echo     未找到 deploy_package.zip
    echo     先运行 build_and_package.bat 生成
    exit /b 1
)
echo [OK] deploy_package.zip 存在

REM ── 2. SSH 连接测试 ────────────────────────────────────────
echo.
echo [2/3] 测试 SSH 连接...
ssh -i "%KEY%" -o ConnectTimeout=10 %USER%@%SERVER% "echo OK" 2>nul
if errorlevel 1 (
    echo [错误] SSH 连接失败
    echo   请检查：
    echo   1. 服务器地址是否正确：%SERVER%
    echo   2. SSH Key 是否配置：%KEY%
    echo   3. 服务器 SSH 是否运行
    exit /b 1
)
echo [OK] SSH 连接成功

REM ── 3. 上传 ─────────────────────────────────────────────────
echo.
echo [3/3] 上传 deploy_package.zip...
scp -i "%KEY%" deploy_package.zip %USER%@%SERVER%:C:/Users/Administrator/Desktop/
if errorlevel 1 (
    echo [错误] 上传失败
    exit /b 1
)
echo [OK] 已上传到服务器桌面

REM ── 4. 服务器端：解压到 C:\www\15min ─────────────────────────
echo.
echo [4/3] 在服务器上解压到 C:\www\15min\...
ssh -i "%KEY%" %USER%@%SERVER% "powershell -Command ^
    mkdir -Force C:\www\15min > $$null; ^
    Expand-Archive -Path 'C:\Users\Administrator\Desktop\deploy_package.zip' -DestinationPath 'C:\www\15min' -Force; ^
    Write-Host '解压完成'; ^
    Get-ChildItem C:\www\15min"
echo [OK] 服务器解压完成

echo.
echo ================================================================
echo  上传完成！
echo.
echo  下一步：在服务器上以管理员身份运行
echo  C:\Users\Administrator\Desktop\deploy-server.bat
echo ================================================================
pause
