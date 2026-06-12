# -*- coding: utf-8 -*-
"""
部署 3D 可视化 - 策略:
  Step 1: PowerShell 建立会话并上传 Base64 (Copy-Item -ToSession)
  Step 2: PowerShell 在同一会话内完成解码+解压+重启Caddy
"""
import subprocess, os, base64, time, sys

HOST = "64.90.0.78"
PORT = 5985
USER = "Administrator"
PASS = "asR84SiRzqhbDvZF"
ZIP_PATH = r"E:\xicha gis 智能定位\自选年份\deploy_3d.zip"
LOCAL_B64 = r"C:\Users\Administrator\dp3d_3d.b64"

def ps(script, timeout=300):
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True, text=True, errors="replace", timeout=timeout
    )
    return r

print("=" * 60)
print("3D 可视化部署 - 合并两步法")
print("=" * 60)
sz = os.path.getsize(ZIP_PATH)
print(f"ZIP 大小: {sz/1024/1024:.1f} MB")

# Step 1: Base64 编码并上传
print("\n[Step 1] 编码 ZIP 并上传到远程...")
with open(ZIP_PATH, "rb") as f:
    raw = f.read()
b64 = base64.b64encode(raw).decode("ascii")
print(f"Base64: {len(b64)/1024/1024:.1f} MB")

# 写本地临时文件
with open(LOCAL_B64, "w", encoding="ascii") as f:
    f.write(b64)
print(f"本地临时: {LOCAL_B64}")

# 用 Copy-Item 上传 (与远程会话在同一 PS 调用内)
print("上传中 (Copy-Item -ToSession)...")
t0 = time.time()
r = ps(f"""
$ErrorActionPreference = "Stop"
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Write-Host "SESSION_OK"

# 上传 Base64 文件
Copy-Item -Path '{LOCAL_B64}' -Destination 'C:\\Users\\Administrator\\dp3d.b64' -ToSession $s
Write-Host "UPLOAD_OK"

# 同一会话内: 解码 + 解压 + 重启 Caddy
Invoke-Command -Session $s -ScriptBlock {{
    $ErrorActionPreference = "Stop"
    Write-Host "=== 解码中 ==="
    $b64 = [IO.File]::ReadAllText('C:\\Users\\Administrator\\dp3d.b64', [Text.Encoding]::ASCII)
    Write-Host ("Base64 长度: " + $b64.Length)
    $bytes = [Convert]::FromBase64String($b64)
    $zipPath = 'C:\\Users\\Administrator\\dp3d.zip'
    [IO.File]::WriteAllBytes($zipPath, $bytes)
    Write-Host ("ZIP 大小: " + ($bytes.Length / 1MB).ToString("F1") + " MB")

    Write-Host "=== 清空旧文件 ==="
    if (!(Test-Path 'C:\\www\\15min\\static')) {{
        New-Item -ItemType Directory -Path 'C:\\www\\15min\\static' -Force | Out-Null
    }}
    Remove-Item 'C:\\www\\15min\\static\\*' -Recurse -Force -ErrorAction SilentlyContinue

    Write-Host "=== 解压 ==="
    [IO.Compression.ZipFile]::ExtractToDirectory($zipPath, 'C:\\www\\15min\\static')
    Write-Host "解压完成"
    Get-ChildItem 'C:\\www\\15min\\static' | ForEach-Object {{
        Write-Host ("  " + $_.Name + " (" + [math]::Round($_.Length/1MB, 1).ToString() + " MB)")
    }}

    Write-Host "=== 重启 Caddy ==="
    $c = Get-Process caddy -ErrorAction SilentlyContinue
    if ($c) {{
        Stop-Process $c -Force
        Start-Sleep 2
        Write-Host "Caddy stopped"
    }}
    Start-Process 'C:\\ProgramData\\caddy\\caddy.exe' -ArgumentList 'run','--config','C:\\globalreviewops\\Caddyfile','--adapter','caddyfile' -NoNewWindow -PassThru | Out-Null
    Start-Sleep 3
    $n = Get-Process caddy -ErrorAction SilentlyContinue
    Write-Host ("Caddy PID: " + $n.Id)

    Write-Host "=== 清理 ==="
    Remove-Item 'C:\\Users\\Administrator\\dp3d.b64' -Force -ErrorAction SilentlyContinue
    Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
    Write-Host "清理完成"
}}

Remove-PSSession $s
Write-Host "SESSION_CLOSED"
""", timeout=600)

print(r.stdout)
if r.stderr:
    print("STDERR:", r.stderr[:500])

# 清理本地临时文件
if os.path.exists(LOCAL_B64):
    os.remove(LOCAL_B64)
    print(f"\n本地临时文件已删除")

total = time.time() - t0
if r.returncode == 0:
    print(f"\n=== 部署完成! 总耗时: {total:.0f}s ===")
    print("访问: http://64.90.0.78/city_visualization_3d.html")
else:
    print(f"\n部署失败 (exit {r.returncode})")
    sys.exit(1)
