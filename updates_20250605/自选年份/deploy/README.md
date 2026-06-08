# 15分钟生活圈 — 子域名部署指南
**子域名：`15min.globalreviewops.xyz`**
**不影响母域名 `globalreviewops.xyz` 的任何现有服务**

---

## 架构

```
浏览器
  └─► https://15min.globalreviewops.xyz/
        ├─► 静态文件 (C:\www\15min\static\)
        │     city_twin_viewer.html  ← 地图交互界面
        │     base_data.json
        │     trajectory_data.json
        └─► /api/* → 反代到 127.0.0.1:8765 (FastAPI)
              routing_api.py (Windows Python)
```

---

## 部署步骤（共 4 步）

### 步骤 1：本地 — 上传文件到服务器

运行本地脚本：

```bat
# 在 部署包 文件夹中打开 PowerShell / CMD
# 或直接双击 upload.bat（前提：已运行 city_twin_builder.py 生成输出）

# 会自动上传：
#   city_twin_viewer.html
#   base_data.json
#   trajectory_data.json
# 到服务器的 C:\www\15min\static\

# 需要手动上传（或 scp）：
#   routing_api.py
#   network_graph.pkl
#   nodes.json
#   facility_locations.json
# 到服务器的 C:\www\15min\api\
```

**手动 scp（如果 upload.bat SSH 失败）：**

```bash
# Linux/Mac 本地 或 Git Bash：
scp -i ~/.ssh/id_rsa city_twin_viewer.html base_data.json trajectory_data.json \
    root@15min.globalreviewops.xyz:C:/www/15min/static/

scp -i ~/.ssh/id_rsa routing_api.py network_graph.pkl nodes.json \
    facility_locations.json \
    root@15min.globalreviewops.xyz:C:/www/15min/api/
```

**Windows PowerShell：**
```powershell
# 如果有 pscp（PuTTY）：
pscp -i C:\Users\Administrator\.ssh\id_rsa.ppk `
    city_twin_viewer.html `
    root@15min.globalreviewops.xyz:C:/www/15min/static/
```

### 步骤 2：服务器 — 安装 Nginx 子域名配置

上传 `15min-subdomain.conf` 到服务器（如放到管理员桌面），然后：

```powershell
# 确认 Nginx 目录
# 常见路径：C:\nginx\  或  C:\tools\nginx\  或  C:\Program Files\nginx\

# 复制配置
copy C:\Users\Administrator\Desktop\15min-subdomain.conf `
     C:\nginx\conf\sites-available\15min-subdomain.conf

# 在 nginx.conf 末尾添加一行（不改动现有配置）：
#   include conf/sites-available/15min-subdomain.conf;

# 创建符号链接（可选）
mklink /D C:\nginx\conf\sites-enabled\15min-subdomain.conf `
          C:\nginx\conf\sites-available\15min-subdomain.conf

# 验证配置
C:\nginx\nginx.exe -t

# 重载 Nginx
C:\nginx\nginx.exe -s reload
```

### 步骤 3：服务器 — 安装 SSL 证书

```bash
certbot --nginx -d 15min.globalreviewops.xyz --non-interactive --agree-tos -m admin@globalreviewops.xyz
```

> 如果服务器是 Windows（无 certbot）：
> 下载 [certbot-windows](https://certbot.eff.org/) 或使用 [win-acme](https://win-acme.com/)

certbot 会自动：
1. 申请 Let's Encrypt 证书
2. 修改 `15min-subdomain.conf`，填入证书路径
3. 启用 HTTPS

### 步骤 4：服务器 — 启动 FastAPI

```powershell
# 安装依赖（首次）
python -m pip install fastapi "uvicorn[standard]" networkx

# 创建目录
mkdir C:\www\15min\api
mkdir C:\www\15min\logs

# 放入 routing_api.py 和数据文件后，启动：
cd C:\www\15min\api
python -m uvicorn routing_api:app --host 127.0.0.1 --port 8765

# 后台常驻启动（PowerShell）：
Start-Process -WindowStyle Hidden -FilePath python `
    -ArgumentList "-m uvicorn routing_api:app --host 127.0.0.1 --port 8765" `
    -WorkingDirectory C:\www\15min\api
```

---

## 一键部署（推荐）

在服务器上以 **管理员身份** 运行 `deploy-server.bat`：

```bat
# 服务器上，双击或以管理员身份运行：
deploy-server.bat
```

它会自动完成：
- [1/6] 检查 Python 依赖
- [2/6] 停止旧 FastAPI 进程
- [3/6] 安装 Nginx 子域名配置
- [4/6] 启动 FastAPI
- [5/6] 申请 SSL 证书
- [6/6] 最终验证

---

## 验证

```powershell
# 测试静态文件
curl http://15min.globalreviewops.xyz/
# 应返回 HTML

# 测试 API
curl http://15min.globalreviewops.xyz/api/stats
# 应返回 JSON

# HTTPS
curl https://15min.globalreviewops.xyz/api/stats
# 应返回 JSON

# Swagger 文档
# https://15min.globalreviewops.xyz/docs
```

---

## 常用维护命令

```powershell
# 查看谁在占用 8765 端口
netstat -ano | findstr :8765

# 停止 FastAPI
for /f "tokens=5" %a in ('netstat -ano ^| findstr :8765 ') do taskkill /F /PID %a

# 查看 API 日志
type C:\www\15min\logs\api.log

# 重启 Nginx
C:\nginx\nginx.exe -s reload

# 重新申请证书（证书90天过期前）
certbot renew
```

---

## 文件说明

| 文件 | 用途 | 上传位置 |
|------|------|---------|
| `city_twin_viewer.html` | 交互地图界面 | `C:\www\15min\static\` |
| `base_data.json` | GeoJSON 数据 | `C:\www\15min\static\` |
| `trajectory_data.json` | 轨迹数据 | `C:\www\15min\static\` |
| `routing_api.py` | FastAPI 后端代码 | `C:\www\15min\api\` |
| `network_graph.pkl` | 路网图数据 | `C:\www\15min\api\` |
| `nodes.json` | 节点数据 | `C:\www\15min\api\` |
| `facility_locations.json` | 设施POI数据 | `C:\www\15min\api\` |
| `15min-subdomain.conf` | Nginx 子域名配置 | 服务器桌面 → `C:\nginx\conf\sites-available\` |
| `deploy-server.bat` | 服务器一键部署 | 服务器桌面（管理员运行）|

---

## 故障排查

| 现象 | 原因 | 解决方法 |
|------|------|---------|
| 502 Bad Gateway | FastAPI 未启动 | 检查 `curl http://127.0.0.1:8765/` |
| 404 /api/* | Nginx `proxy_pass` 末尾少了 `/` | 检查配置中的 `proxy_pass http://127.0.0.1:8765/api/;` |
| SSL 证书错误 | 证书路径不对 | certbot 会自动填写，手动检查 ssl_certificate 路径 |
| 连接被重置 | 防火墙挡住 443 | Windows 防火墙：`netsh advfirewall firewall add rule ...` |
| 地图不加载 | base_data.json 没上传 | 检查 `C:\www\15min\static\` 内容 |
| 等时圈/路线报错 | API 未响应 | 检查 `C:\www\15min\logs\api.log` |
| 母域名受影响 | 配置写错到母域名配置 | 只改子域名配置，母域名 `nginx.conf` 不要动 |
