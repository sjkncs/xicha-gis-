# ================================================================
# deploy-oneclick.ps1 — 一键部署：上传 + 配置 + 启动 + SSL
# 使用方式：以管理员身份打开 PowerShell，粘贴整个脚本运行
# ================================================================

$SERVER = "64.90.0.78"
$USER   = "root"
$KEY    = "$env:USERPROFILE\.ssh\globalreviewops_rainyun_ed25519"
$API_PORT = 8765

$LOCAL_DIR    = "e:\xicha gis 智能定位\自选年份"
$STATIC_DIR   = "C:\www\15min\static"
$API_DIR      = "C:\www\15min\api"
$NGINX_CONF   = "$env:USERPROFILE\Desktop\15min-subdomain.conf"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " 15分钟生活圈 — 一键部署" -ForegroundColor Cyan
Write-Host " $SERVER" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# ── 1. 检查 SSH Key ──────────────────────────────────────────────
Write-Host "`n[1/8] 检查 SSH Key..." -ForegroundColor Yellow
if (-not (Test-Path $KEY)) {
    Write-Host " [错误] 未找到 SSH Key: $KEY" -ForegroundColor Red
    Write-Host " 请先生成：ssh-keygen -t rsa -b 4096 -C 'admin@globalreviewops.xyz'" -ForegroundColor Yellow
    exit 1
}
Write-Host " [OK] SSH Key 存在"

# ── 2. 测试 SSH 连接 ─────────────────────────────────────────────
Write-Host "`n[2/8] 测试 SSH 连接..." -ForegroundColor Yellow
$result = ssh -i $KEY -o ConnectTimeout=15 -o StrictHostKeyChecking=no "$USER@$SERVER" "echo OK" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host " [错误] SSH 连接失败: $result" -ForegroundColor Red
    exit 1
}
Write-Host " [OK] SSH 连接成功"

# ── 3. 创建服务器目录 ─────────────────────────────────────────────
Write-Host "`n[3/8] 创建服务器目录..." -ForegroundColor Yellow
ssh -i $KEY "$USER@$SERVER" @"
mkdir -p $STATIC_DIR
mkdir -p $API_DIR
mkdir -p C:/www/15min/logs
mkdir -p C:/nginx/conf/sites-available
mkdir -p C:/nginx/conf/sites-enabled
echo OK
"@ | Out-Null
Write-Host " [OK] 目录已创建"

# ── 4. 上传文件 ──────────────────────────────────────────────────
Write-Host "`n[4/8] 上传 deploy_package.zip ..." -ForegroundColor Yellow
Set-Location $LOCAL_DIR
scp -i $KEY "deploy_package.zip" "$USER@$SERVER`:C:/Users/Administrator/Desktop/" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host " [错误] 上传失败" -ForegroundColor Red
    exit 1
}
Write-Host " [OK] deploy_package.zip 已上传"

Write-Host "`n[5/8] 上传 Nginx 配置..." -ForegroundColor Yellow
scp -i $KEY "自选年份\deploy\15min-subdomain.conf" "$USER@$SERVER`:C:/Users/Administrator/Desktop/" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host " [错误] Nginx 配置上传失败" -ForegroundColor Red
    exit 1
}
Write-Host " [OK] 15min-subdomain.conf 已上传"

# ── 5. 服务器端：解压 + 整理目录结构 ─────────────────────────────
Write-Host "`n[6/8] 服务器解压 + 整理目录..." -ForegroundColor Yellow
ssh -i $KEY "$USER@$SERVER" @"
Set-Location C:\Users\Administrator\Desktop
Expand-Archive -Path deploy_package.zip -DestinationPath C:\www\15min -Force

# 整理 network_output 到 api 目录
if (Test-Path C:\www\15min\network_output) {
    Copy-Item -Path C:\www\15min\network_output\* -Destination $API_DIR\ -Force
}
if (Test-Path C:\www\15min\city_twin_output) {
    Copy-Item -Path C:\www\15min\city_twin_output\* -Destination $STATIC_DIR\ -Force
}
if (Test-Path C:\www\15min\routing_api.py) {
    Copy-Item -Path C:\www\15min\routing_api.py -Destination $API_DIR\ -Force
}

Write-Host '  目录结构:'
Get-ChildItem C:\www\15min -Recurse -Depth 2 | Select-Object FullName
Write-Host '  文件数量:' (Get-ChildItem C:\www\15min -Recurse -File).Count
"@
Write-Host " [OK] 服务器解压完成"

# ── 6. Nginx 子域名配置 ───────────────────────────────────────────
Write-Host "`n[7/8] 安装 Nginx 子域名配置..." -ForegroundColor Yellow
ssh -i $KEY "$USER@$SERVER" @"
`$NGINX_CONF = 'C:\nginx\conf\nginx.conf'
if (-not (Test-Path `$NGINX_CONF)) { `$NGINX_CONF = 'C:\tools\nginx\conf\nginx.conf' }
if (-not (Test-Path `$NGINX_CONF)) { `$NGINX_CONF = 'C:\Program Files\nginx\conf\nginx.conf' }

Write-Host '  Nginx 目录:' `$NGINX_CONF
`$nginx_exe = Split-Path `$NGINX_CONF
Copy-Item -Path 'C:\Users\Administrator\Desktop\15min-subdomain.conf' -Destination "`$(`$nginx_exe)\conf\sites-available\15min-subdomain.conf" -Force

# 添加 include 到 nginx.conf（只加一次）
`$content = Get-Content `$NGINX_CONF -Raw
if (`$content -notmatch '15min-subdomain.conf') {
    Add-Content `$NGINX_CONF -Value "`ninclude conf/sites-available/15min-subdomain.conf;"
    Write-Host '  已添加 include 到 nginx.conf'
} else {
    Write-Host '  include 已存在，跳过'
}

# 验证配置
& "`$(`$nginx_exe)\nginx.exe" -t
Write-Host '  Nginx 配置语法:' `$LASTEXITCODE
& "`$(`$nginx_exe)\nginx.exe" -s reload
Write-Host '  Nginx 重载完成'
"@
Write-Host " [OK] Nginx 配置完成"

# ── 7. 启动 FastAPI ───────────────────────────────────────────────
Write-Host "`n[8/8] 启动 FastAPI..." -ForegroundColor Yellow
ssh -i $KEY "$USER@$SERVER" @"
# 停止旧进程
`$old = Get-NetTCPConnection -LocalPort $API_PORT -ErrorAction SilentlyContinue
if (`$old) {
    `$old | ForEach-Object { Stop-Process -Id `$_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Write-Host '  停止旧进程'
}

# 安装 Python 依赖
Write-Host '  检查 Python 依赖...'
python -c 'import fastapi,uvicorn,networkx' 2>nul
if (`$LASTEXITCODE -ne 0) {
    python -m pip install fastapi 'uvicorn[standard]' networkx --quiet
    Write-Host '  依赖安装完成'
}

# 后台启动
Set-Location $API_DIR
`$log = 'C:\www\15min\logs\api.log'
Start-Process -WindowStyle Hidden python -ArgumentList '-m uvicorn routing_api:app --host 127.0.0.1 --port $API_PORT' -RedirectStandardOutput `$log -WorkingDirectory $API_DIR

Start-Sleep 4

# 验证
`$check = Invoke-WebRequest -Uri "http://127.0.0.1:$API_PORT/" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
if (`$check.StatusCode -eq 200) {
    Write-Host '  FastAPI 启动成功 (200)'
} else {
    Write-Host '  FastAPI 可能未完全就绪，4秒后再试'
    Start-Sleep 4
    `$check2 = Invoke-WebRequest -Uri "http://127.0.0.1:$API_PORT/api/stats" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
    Write-Host '  /api/stats 状态:' `$check2.StatusCode
}
"@
Write-Host " [OK] FastAPI 启动完成"

# ── 最终报告 ────────────────────────────────────────────────────
Write-Host "`n============================================================" -ForegroundColor Green
Write-Host " 部署完成！" -ForegroundColor Green
Write-Host "`n 访问地址：" -ForegroundColor White
Write-Host "   Viewer: https://$SERVER/" -ForegroundColor Cyan
Write-Host "   API:    https://$SERVER/api/stats" -ForegroundColor Cyan
Write-Host "   Docs:   https://$SERVER/docs" -ForegroundColor Cyan
Write-Host "`n 维护命令（服务器 PowerShell）：" -ForegroundColor Yellow
Write-Host "   停止 API: Stop-NetTCPConnection -LocalPort $API_PORT -ErrorAction SilentlyContinue; Get-NetTCPConnection -LocalPort $API_PORT | Stop-Process -Force" -ForegroundColor Gray
Write-Host "   查看日志: Get-Content C:\www\15min\logs\api.log -Tail 20" -ForegroundColor Gray
Write-Host "   重载 Nginx: C:\nginx\nginx.exe -s reload" -ForegroundColor Gray
Write-Host "`n SSL 证书需要手动申请（certbot）：" -ForegroundColor Yellow
Write-Host "   certbot --nginx -d $SERVER" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Green
