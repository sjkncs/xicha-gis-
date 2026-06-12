@echo off
REM ================================================================
REM deploy-server.bat — 在服务器（Windows）上运行（管理员身份）
REM ================================================================
REM 运行前提：
REM   1. deploy_package.zip 已解压到 C:\www\15min\
REM   2. Nginx 已安装（choco install nginx 或手动安装）
REM   3. Python 已安装（choco install python）
REM ================================================================
setlocal EnableDelayedExpansion

echo ================================================================
echo  15分钟生活圈 — 服务器部署
echo  15min.globalreviewops.xyz
echo ================================================================

REM ── 配置 ────────────────────────────────────────────────────
SET API_DIR=C:\www\15min\api
SET API_PORT=8765
SET NGINX_DIR=
SET STATIC_DIR=C:\www\15min\static

REM ── 0. 探测 Nginx 目录 ────────────────────────────────────────
echo.
echo [0/?] 探测 Nginx 安装位置...
REM 尝试常见路径
for %%p in (
    "C:\nginx"
    "C:\tools\nginx"
    "C:\Program Files\nginx"
    "C:\Program Files (x86)\nginx"
    "C:\Server\nginx"
) do (
    if exist "%%~p\conf\nginx.conf" (
        set "NGINX_DIR=%%~p"
    )
)
if not defined NGINX_DIR (
    echo [错误] 未找到 Nginx，请先安装：
    echo   choco install nginx
    echo 或从 https://nginx.org/en/download.html 下载 Windows 版
    exit /b 1
)
echo     找到 Nginx: %NGINX_DIR%
echo [OK] Nginx 位置已确定

REM ── 1. 检查 Python 依赖 ───────────────────────────────────────
echo.
echo [1/7] 检查 Python 依赖...
python -c "import fastapi, uvicorn, networkx" 2>nul
if errorlevel 1 (
    echo     安装 Python 依赖（fastapi, uvicorn, networkx）...
    python -m pip install fastapi "uvicorn[standard]" networkx --quiet
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请手动运行：
        echo   pip install fastapi "uvicorn[standard]" networkx
        exit /b 1
    )
    echo [OK] 依赖安装完成
) else (
    echo [OK] Python 依赖已就绪
)

REM ── 2. 检查 API 文件 ─────────────────────────────────────────
echo.
echo [2/7] 检查 API 文件...
if not exist "%API_DIR%\routing_api.py" (
    echo [错误] 未找到 routing_api.py
    echo   请解压 deploy_package.zip 到 C:\www\15min\
    exit /b 1
)
if not exist "%API_DIR%\network_output" (
    mkdir "%API_DIR%\network_output"
)
REM 把 network_output 移到 API_DIR 下（解压后可能是平铺的）
if exist "%API_DIR%\network_graph.pkl" (
    if not exist "%API_DIR%\network_output\network_graph.pkl" (
        move "%API_DIR%\network_graph.pkl" "%API_DIR%\network_output\" >nul 2>&1
    )
)
if exist "%API_DIR%\facility_locations.json" (
    if not exist "%API_DIR%\network_output\facility_locations.json" (
        move "%API_DIR%\facility_locations.json" "%API_DIR%\network_output\" >nul 2>&1
    )
)
if exist "%API_DIR%\network_nodes.json" (
    if not exist "%API_DIR%\network_output\network_nodes.json" (
        move "%API_DIR%\network_nodes.json" "%API_DIR%\network_output\" >nul 2>&1
    )
)
if exist "%API_DIR%\network_edges.json" (
    if not exist "%API_DIR%\network_output\network_edges.json" (
        move "%API_DIR%\network_edges.json" "%API_DIR%\network_output\" >nul 2>&1
    )
)
echo [OK] API 文件就绪

REM ── 3. 检查静态文件 ──────────────────────────────────────────
echo.
echo [3/7] 检查静态文件...
if not exist "%STATIC_DIR%\city_twin_viewer.html" (
    echo [警告] 未找到 city_twin_viewer.html
    echo   确保静态文件在 %STATIC_DIR%
) else (
    echo [OK] 静态文件就绪
)

REM ── 4. 停止旧的 FastAPI 进程 ───────────────────────────────
echo.
echo [4/7] 停止旧的 FastAPI 进程（端口 %API_PORT%）...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%API_PORT% ^| findstr LISTENING') do (
    echo     停止 PID %%a
    taskkill /F /PID %%a >nul 2>&1
)
REM 也按进程名杀
taskkill /F /IM python.exe >nul 2>&1
echo [OK] FastAPI 已停止

REM ── 5. 安装 Nginx 子域名配置 ────────────────────────────────
echo.
echo [5/7] 安装 Nginx 子域名配置...
REM 查找桌面上的配置文件
SET NGINX_CONF=
for %%f in (
    "%USERPROFILE%\Desktop\15min-subdomain.conf"
    "C:\Users\Administrator\Desktop\15min-subdomain.conf"
    "C:\www\15min\15min-subdomain.conf"
) do (
    if exist "%%~f" set "NGINX_CONF=%%~f"
)

if not defined NGINX_CONF (
    echo [错误] 未找到 15min-subdomain.conf
    echo   请上传配置文件到服务器（放在桌面）
    exit /b 1
)
echo     使用配置: %NGINX_CONF%

REM 备份原 nginx.conf
copy /Y "%NGINX_DIR%\conf\nginx.conf" "%NGINX_DIR%\conf\nginx.conf.backup" >nul 2>&1

REM 在 nginx.conf 末尾添加 include（只追加一次）
findstr /C:"15min-subdomain.conf" "%NGINX_DIR%\conf\nginx.conf" >nul 2>&1
if errorlevel 1 (
    echo     添加 include 到 nginx.conf...
    echo. >> "%NGINX_DIR%\conf\nginx.conf"
    echo include conf/sites-available/15min-subdomain.conf; >> "%NGINX_DIR%\conf\nginx.conf"
)

REM 复制子域名配置
if not exist "%NGINX_DIR%\conf\sites-available" mkdir "%NGINX_DIR%\conf\sites-available"
if not exist "%NGINX_DIR%\conf\sites-enabled" mkdir "%NGINX_DIR%\conf\sites-enabled"
copy /Y "%NGINX_CONF%" "%NGINX_DIR%\conf\sites-available\15min-subdomain.conf" >nul

REM 创建符号链接
mklink /D "%NGINX_DIR%\conf\sites-enabled\15min-subdomain.conf" "%NGINX_DIR%\conf\sites-available\15min-subdomain.conf" >nul 2>&1

REM 验证 + 重载
"%NGINX_DIR%\nginx.exe" -t
if errorlevel 1 (
    echo [错误] Nginx 配置语法错误，请检查 %NGINX_DIR%\conf\nginx.conf
    exit /b 1
)
"%NGINX_DIR%\nginx.exe" -s reload
echo [OK] Nginx 配置已安装并重载

REM ── 6. 启动 FastAPI ────────────────────────────────────────
echo.
echo [6/7] 启动 FastAPI（端口 %API_PORT%）...
if not exist "C:\www\15min\logs" mkdir "C:\www\15min\logs"

cd /d "%API_DIR%"
start /B "" cmd /c "python -m uvicorn routing_api:app --host 127.0.0.1 --port %API_PORT% >> C:\www\15min\logs\api.log 2>&1"

REM 等待启动
timeout /t 4 /nobreak >nul

REM 验证
curl -s --max-time 5 http://127.0.0.1:%API_PORT%/ >nul 2>&1
if errorlevel 1 (
    echo     [警告] API 可能未启动成功，请检查日志：
    echo     C:\www\15min\logs\api.log
) else (
    echo [OK] FastAPI 已启动
)

REM ── 7. SSL 证书 ────────────────────────────────────────────
echo.
echo [7/7] SSL 证书申请...
REM certbot 通常不在 Windows PATH，先尝试
where certbot >nul 2>&1
if errorlevel 1 (
    echo     [跳过] certbot 不在 PATH
    echo     请手动运行（安装 certbot-for-windows）：
    echo     certbot --nginx -d 15min.globalreviewops.xyz
    echo.
    echo     或使用 win-acme: https://win-acme.com/
    echo     成功后会自动修改 Nginx 配置中的证书路径
) else (
    certbot --nginx -d 15min.globalreviewops.xyz --non-interactive --agree-tos -m admin@globalreviewops.xyz
    if not errorlevel 1 (
        echo [OK] SSL 证书申请成功
    ) else (
        echo     [跳过] certbot 失败，请手动申请
    )
)

REM ── 最终验证 ────────────────────────────────────────────────
echo.
echo ================================================================
echo  部署完成！请验证以下地址：
echo.
curl -sk -o nul -w "  HTTPS /           : %%{http_code}\n" https://15min.globalreviewops.xyz/
curl -sk -o nul -w "  HTTPS /api/stats  : %%{http_code}\n" https://15min.globalreviewops.xyz/api/stats
echo.
echo  预期结果：
echo    / 返回 200 + HTML
echo    /api/stats 返回 200 + JSON
echo.
echo  如果返回 502 → API 未启动，检查 C:\www\15min\logs\api.log
echo  如果返回 404 → 静态文件未找到，检查 C:\www\15min\static\
echo ================================================================
pause
