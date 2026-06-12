# -*- coding: utf-8 -*-
"""
分块传输 3D 可视化部署包到 WinRM 服务器
策略: Python 写 Base64 到本地文本 → Copy-Item 上传 → PowerShell 脚本解码
"""
import subprocess, os, base64, time, sys

HOST = "64.90.0.78"
PORT = 5985
USER = "Administrator"
PASS = "asR84SiRzqhbDvZF"
ZIP_PATH = r"E:\xicha gis 智能定位\自选年份\deploy_3d.zip"
LOCAL_B64 = r"C:\Users\Administrator\dp3d_3d.b64"
REMOTE_B64 = "C:\\Users\\Administrator\\dp3d.b64"
REMOTE_ZIP = "C:\\Users\\Administrator\\dp3d.zip"
REMOTE_DIR = "C:\\Users\\Administrator\\dp3d_work"

def ps_cmd(cmd):
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        capture_output=True, text=True, errors="replace", timeout=120
    )
    return r

print("=" * 60)
print("3D 可视化部署 - Copy-Item + PowerShell 解码")
print("=" * 60)
print(f"ZIP: {ZIP_PATH}")
sz = os.path.getsize(ZIP_PATH)
print(f"大小: {sz/1024/1024:.1f} MB")

# Step 1: 建立 WinRM 会话
print("\n[1] 建立 WinRM 会话...")
r = ps_cmd(f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Write-Host "SESSION_ID=$($s.Id)"
""")
if r.returncode != 0:
    print(f"会话失败: {r.stderr[:300]}")
    sys.exit(1)
sess_id = None
for line in r.stdout.splitlines():
    if "SESSION_ID=" in line:
        sess_id = line.split("SESSION_ID=")[1].strip()
print(f"会话 ID: {sess_id}")
assert sess_id, "无法获取会话 ID"

# Step 2: 读取并编码 ZIP
print("\n[2] Base64 编码...")
with open(ZIP_PATH, "rb") as f:
    raw = f.read()
b64 = base64.b64encode(raw).decode("ascii")
print(f"Base64 长度: {len(b64)/1024/1024:.1f} MB")

# Step 3: 写本地临时文件
print("\n[3] 写本地临时 Base64 文件...")
with open(LOCAL_B64, "w", encoding="ascii") as f:
    f.write(b64)
print(f"已写入: {LOCAL_B64}")

# Step 4: Copy-Item 上传到远程
print("\n[4] 上传到远程服务器...")
t0 = time.time()

def remote(cmd, timeout=120):
    return ps_cmd(f"""
$s = Get-PSSession -Id {sess_id}
Invoke-Command -Session $s -ScriptBlock {{{cmd}}}
""")

# 建立远程目录
remote("""
if (Test-Path '{REMOTE_DIR}') {{ Remove-Item '{REMOTE_DIR}' -Recurse -Force }}
New-Item -ItemType Directory -Path '{REMOTE_DIR}' -Force | Out-Null
if (!(Test-Path 'C:\\www\\15min\\static')) {{ New-Item -ItemType Directory -Path 'C:\\www\\15min\\static' -Force | Out-Null }}
Remove-Item 'C:\\www\\15min\\static\\*' -Recurse -Force -ErrorAction SilentlyContinue
Write-Host '目录初始化完成'
""")

# 使用 Copy-Item -ToSession 上传 Base64 文件
r = ps_cmd(f"""
$s = Get-PSSession -Id {sess_id}
$session = $s
Copy-Item -Path '{LOCAL_B64}' -Destination '{REMOTE_B64}' -ToSession $session
Write-Host 'COPY_OK'
Get-Item '{REMOTE_B64}' | Select-Object Length
""")
print(r.stdout)
if "COPY_OK" not in r.stdout:
    print(f"上传失败: {r.stderr[:200]}")
    sys.exit(1)
print(f"上传耗时: {time.time()-t0:.0f}s")

# Step 5: PowerShell 远程解码并解压
print("\n[5] 远程解码并解压...")
r = remote(f"""
Write-Host '读取 Base64 文件...'
$b64 = [IO.File]::ReadAllText('{REMOTE_B64}', [Text.Encoding]::ASCII)
Write-Host ('Base64 长度: ' + $b64.Length)
Write-Host '解码为 ZIP...'
$bytes = [Convert]::FromBase64String($b64)
[IO.File]::WriteAllBytes('{REMOTE_ZIP}', $bytes)
Write-Host ('ZIP 大小: ' + ($bytes.Length / 1MB).ToString('F1') + ' MB')
Write-Host '解压到 static...'
[IO.Compression.ZipFile]::ExtractToDirectory('{REMOTE_ZIP}', 'C:\\www\\15min\\static')
Write-Host '解压完成'
Get-ChildItem 'C:\\www\\15min\\static' | ForEach-Object {{
    Write-Host ('  ' + $_.Name + ' (' + [math]::Round($_.Length/1MB, 1).ToString() + ' MB)')
}}
""", timeout=180)
print(r.stdout)
print(r.stderr[:200] if r.stderr else "")

# Step 6: 重启 Caddy
print("\n[6] 重启 Caddy...")
r = remote("""
$c = Get-Process caddy -ErrorAction SilentlyContinue
if ($c) { Stop-Process $c -Force; Start-Sleep 2; Write-Host 'Caddy stopped' }
Start-Process 'C:\\ProgramData\\caddy\\caddy.exe' -ArgumentList 'run','--config','C:\\globalreviewops\\Caddyfile','--adapter','caddyfile' -NoNewWindow -PassThru | Out-Null
Start-Sleep 3
$n = Get-Process caddy -ErrorAction SilentlyContinue
Write-Host ('Caddy PID: ' + $n.Id)
""")
print(r.stdout)

# Step 7: 清理本地和远程临时文件
print("\n[7] 清理临时文件...")
os.remove(LOCAL_B64)
remote(f"""
Remove-Item '{REMOTE_B64}' -Force -ErrorAction SilentlyContinue
Remove-Item '{REMOTE_ZIP}' -Force -ErrorAction SilentlyContinue
Remove-Item '{REMOTE_DIR}' -Recurse -Force -ErrorAction SilentlyContinue
Write-Host '清理完成'
""")
print(f"本地临时文件已删除: {LOCAL_B64}")

# 关闭会话
ps_cmd(f"$s = Get-PSSession -Id {sess_id}; Remove-PSSession $s")
print("\n=== 部署完成! ===")
print(f"总耗时: {time.time()-t0:.0f}s")
print("访问: http://64.90.0.78/city_visualization_3d.html")
