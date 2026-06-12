@echo off
REM ================================================================
REM download_from_server.bat — 从服务器下载 API 数据文件到本地
REM ================================================================
REM 用途：补充本地缺失的 network_graph.pkl
REM 说明：如果本地没有 pkl，先从服务器下载，再打包上传
REM ================================================================
setlocal EnableDelayedExpansion

REM ── 配置 ──────────────────────────────────────────────────────
SET SERVER=15min.globalreviewops.xyz
SET USER=root
SET KEY=C:\Users\Administrator\.ssh\id_rsa

REM 服务器上的文件位置（和 deploy-server.bat 对应）
SET SERVER_API_DIR=C:/www/15min/api
SET SERVER_OUTPUT_DIR=C:/www/15min/api/network_output

echo ================================================================
echo  从服务器下载 API 数据文件
echo ================================================================

REM ── 下载 network_graph.pkl ────────────────────────────────────
echo.
echo [1/3] 下载 network_graph.pkl ...
scp -i "%KEY%" %USER%@%SERVER%:%SERVER_OUTPUT_DIR%/network_graph.pkl network_output/
if errorlevel 1 (
    echo [警告] network_graph.pkl 下载失败（可能服务器上不存在）
    echo         如果本地已有，跳过此步
) else (
    echo [OK] network_graph.pkl 已下载
)

REM ── 下载其他 JSON ──────────────────────────────────────────────
echo.
echo [2/3] 下载其他数据文件 ...
scp -i "%KEY%" %USER%@%SERVER%:%SERVER_OUTPUT_DIR%/network_nodes.json network_output/ 2>nul
scp -i "%KEY%" %USER%@%SERVER%:%SERVER_OUTPUT_DIR%/facility_locations.json network_output/ 2>nul
scp -i "%KEY%" %USER%@%SERVER%:%SERVER_OUTPUT_DIR%/network_edges.json network_output/ 2>nul
scp -i "%KEY%" %USER%@%SERVER%:%SERVER_OUTPUT_DIR%/walkable_stats.json network_output/ 2>nul
echo [OK] 数据文件已下载

REM ── 下载 routing_api.py ───────────────────────────────────────
echo.
echo [3/3] 下载 routing_api.py ...
scp -i "%KEY%" %USER%@%SERVER%:%SERVER_API_DIR%/routing_api.py ./
echo [OK] routing_api.py 已下载

REM ── 检查结果 ─────────────────────────────────────────────────
echo.
echo ================================================================
echo  下载完成！检查本地文件：
dir /b network_output
echo ================================================================
pause
