@echo off
REM ================================================================
REM build_and_package.bat — 本地构建 + 打包部署文件
REM ================================================================
REM 运行此脚本后会：
REM   1. 检查 Python 环境和依赖
REM   2. 运行 network.py 生成 network_graph.pkl 等数据文件
REM   3. 检查 city_twin_output 静态文件
REM   4. 打包为 deploy_package.zip
REM ================================================================
setlocal EnableDelayedExpansion

cd /d "%~dp0.."

echo ================================================================
echo  15分钟生活圈 — 构建 + 打包
echo ================================================================

REM ── 1. 检查 Python ───────────────────────────────────────────
echo.
echo [1/5] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.9+
    echo   下载地址：https://www.python.org/downloads/
    exit /b 1
)
echo [OK] Python 就绪

REM ── 2. 检查 / 安装依赖 ────────────────────────────────────────
echo.
echo [2/5] 检查 Python 依赖...
python -c "import fastapi, uvicorn, networkx, geopandas, shapely, scipy" 2>nul
if errorlevel 1 (
    echo     安装依赖中（fastapi, uvicorn, networkx, geopandas, shapely, scipy）...
    python -m pip install --quiet fastapi "uvicorn[standard]" networkx geopandas shapely scipy
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请手动运行：
        echo   pip install fastapi "uvicorn[standard]" networkx geopandas shapely scipy
        exit /b 1
    )
)
echo [OK] 依赖就绪

REM ── 3. 运行 network.py 生成 pkl ────────────────────────────────
echo.
echo [3/5] 运行 network.py 生成路网数据（network_graph.pkl）...
if exist "network_output\network_graph.pkl" (
    echo     [跳过] network_graph.pkl 已存在
) else (
    echo     运行中（可能需要 1-3 分钟）...
    python network.py
    if errorlevel 1 (
        echo [错误] network.py 运行失败
        echo   请检查 network_output 目录是否有 OSM shp 数据文件
        exit /b 1
    )
)

REM ── 4. 检查静态文件 ────────────────────────────────────────────
echo.
echo [4/5] 检查静态文件...
if not exist "city_twin_output\city_twin_viewer.html" (
    echo     [警告] city_twin_viewer.html 不存在
    echo     [提示] 请先运行: python city_twin_builder.py
)
if not exist "city_twin_output\base_data.json" (
    echo     [警告] base_data.json 不存在
)
if not exist "city_twin_output\base_core_data.json" (
    echo     [警告] base_core_data.json 不存在
)
if not exist "city_twin_output\roads_data.json" (
    echo     [警告] roads_data.json 不存在
)
if not exist "city_twin_output\trajectory_data.json" (
    echo     [警告] trajectory_data.json 不存在
)

REM ── 5. 打包 ─────────────────────────────────────────────────
echo.
echo [5/5] 打包 deploy_package.zip...
if exist "deploy_package.zip" del /q "deploy_package.zip"

REM 静态文件（白名单打包，避免上传历史 full GeoJSON 和临时检查文件）
powershell -NoProfile -Command "$static=@('city_twin_output\city_twin_viewer.html','city_twin_output\base_core_data.json','city_twin_output\roads_data.json','city_twin_output\base_data.json','city_twin_output\trajectory_data.json','city_twin_output\city_digital_twin.geojson') | Where-Object { Test-Path $_ }; Compress-Archive -Path $static -DestinationPath 'deploy_package.zip' -Update"

REM API 数据文件
powershell -c "Compress-Archive -Path 'network_output\*' -DestinationPath 'deploy_package.zip' -Update"

REM API 代码
powershell -c "Compress-Archive -Path 'routing_api.py' -DestinationPath 'deploy_package.zip' -Update"

echo [OK] 打包完成：deploy_package.zip

REM ── 最终报告 ────────────────────────────────────────────────
echo.
echo ================================================================
echo  构建完成！ deploy_package.zip 包含：
echo.
echo  [静态文件] city_twin_output/
echo  [API 数据]   network_output/
echo  [API 代码]   routing_api.py
echo.
echo  下一步：
echo    1. 上传 deploy_package.zip 到服务器
echo    2. 服务器解压到 C:\www\15min\
echo    3. 运行 deploy-server.bat
echo ================================================================
pause
