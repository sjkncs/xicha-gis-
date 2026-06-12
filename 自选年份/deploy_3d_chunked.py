# -*- coding: utf-8 -*-
"""分块传输大文件到远程 WinRM 服务器"""
import subprocess, os, base64, time, sys

HOST = "64.90.0.78"
PORT = 5985
USER = "Administrator"
PASS = "asR84SiRzqhbDvZF"
ZIP_PATH = r"E:\xicha gis 智能定位\自选年份\deploy_3d.zip"
CHUNK_KB = 512   # 每块 512 KB，避免超限
REMOTE_DIR = "C:\\dp3d_work"

def run_ps(cmd, timeout=60):
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        capture_output=True, text=True, errors="replace",
        timeout=timeout
    )
    return r

print("=" * 60)
print("3D 可视化部署 - 分块 WinRM 传输")
print("=" * 60)
print(f"ZIP: {ZIP_PATH}")
sz = os.path.getsize(ZIP_PATH)
print(f"大小: {sz/1024/1024:.1f} MB")

print("\n[1] 编码 ZIP 为 Base64...")
with open(ZIP_PATH, "rb") as f:
    raw = f.read()
b64 = base64.b64encode(raw).decode("ascii")
print(f"Base64 长度: {len(b64)/1024/1024:.1f} MB")

print("\n[2] 建立 WinRM 会话...")
r = run_ps(f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Write-Host "SESSION_ID=$($s.Id)"
""")
if r.returncode != 0:
    print(f"会话建立失败: {r.stderr[:200]}")
    sys.exit(1)
sess_id = None
for line in r.stdout.splitlines():
    if "SESSION_ID=" in line:
        sess_id = line.split("SESSION_ID=")[1].strip()
print(f"会话 ID: {sess_id}")

def remote(cmd, timeout=120):
    full = f"""
$s = Get-PSSession -Id {sess_id}
Invoke-Command -Session $s -ScriptBlock {{ {cmd} }}
"""
    return run_ps(full, timeout=timeout)

# 初始化远程目录
print("\n[3] 初始化远程目录...")
r = remote("""
if (Test-Path '{REMOTE_DIR}') {{ Remove-Item '{REMOTE_DIR}' -Recurse -Force }}
New-Item -ItemType Directory -Path '{REMOTE_DIR}' -Force | Out-Null
if (Test-Path 'C:\\www\\15min\\static') {{ Remove-Item 'C:\\www\\15min\\static\\*' -Recurse -Force }} else {{ New-Item -ItemType Directory -Path 'C:\\www\\15min\\static' -Force | Out-Null }}
Write-Host "目录初始化完成"
""")
print(r.stdout.strip() or r.stderr.strip()[:100])

# 分块传输 Base64
chunk_size = CHUNK_KB * 1024
n_chunks = (len(b64) + chunk_size - 1) // chunk_size
print(f"\n[4] 分块传输 ({n_chunks} 块, 每块 {CHUNK_KB} KB)...")
t0 = time.time()
for i in range(n_chunks):
    chunk = b64[i*chunk_size:(i+1)*chunk_size]
    chunk_b64 = base64.b64encode(chunk.encode()).decode()
    mode = "Overwrite" if i == 0 else "Append"
    cmd = f"""
$tmp = '{REMOTE_DIR}\\chunk_{i:04d}.b64';
[IO.File]::WriteAllText($tmp, [Convert]::FromBase64String('{chunk_b64}'), [Text.Encoding]::ASCII);
$all = if (Test-Path '{REMOTE_DIR}\\all.b64') {{ [IO.File]::ReadAllText('{REMOTE_DIR}\\all.b64', [Text.Encoding]::ASCII) + [IO.File]::ReadAllText($tmp, [Text.Encoding]::ASCII) }} else {{ [IO.File]::ReadAllText($tmp, [Text.Encoding]::ASCII) }};
[IO.File]::WriteAllText('{REMOTE_DIR}\\all.b64', $all, [Text.Encoding]::ASCII);
Remove-Item $tmp -Force;
Write-Host 'chunk_{i}'
"""
    r = remote(cmd, timeout=60)
    pct = (i+1)/n_chunks*100
    elapsed = time.time()-t0
    eta = elapsed/(i+1)*(n_chunks-i-1)
    bar = "#" * int(pct/5) + "-" * (20 - int(pct/5))
    print(f"  [{bar}] {pct:.0f}% chunk {i+1}/{n_chunks} | ETA: {eta:.0f}s", end="\r")

print(f"\n传输完成! 耗时: {time.time()-t0:.0f}s")

# 解码并写入 ZIP
print("\n[5] 解码为 ZIP...")
r = remote("""
$all = [IO.File]::ReadAllText('{REMOTE_DIR}\\all.b64', [Text.Encoding]::ASCII);
$bytes = [Convert]::FromBase64String($all);
[IO.File]::WriteAllBytes('{REMOTE_DIR}\\dp.zip', $bytes);
Write-Host ('ZIP: ' + ([IO.File]::ReadAllBytes('{REMOTE_DIR}\\dp.zip').Length / 1MB).ToString('F1') + ' MB')
""", timeout=120)
print(r.stdout.strip() or r.stderr[:100])

# 解压
print("\n[6] 解压到 C:\\www\\15min\\static...")
r = remote("""
[IO.Compression.ZipFile]::ExtractToDirectory('{REMOTE_DIR}\\dp.zip', 'C:\\www\\15min\\static');
Write-Host '解压完成'
Get-ChildItem 'C:\\www\\15min\\static' | ForEach-Object {{ Write-Host ('  ' + $_.Name + ' (' + [math]::Round($_.Length/1MB, 1).ToString() + ' MB)') }}
""", timeout=120)
print(r.stdout)

# 重启 Caddy
print("\n[7] 重启 Caddy...")
r = remote("""
$c = Get-Process caddy -ErrorAction SilentlyContinue
if ($c) {{ Stop-Process $c -Force; Start-Sleep 2; Write-Host 'Caddy stopped' }}
Start-Process 'C:\\ProgramData\\caddy\\caddy.exe' -ArgumentList 'run','--config','C:\\globalreviewops\\Caddyfile','--adapter','caddyfile' -NoNewWindow -PassThru | Out-Null
Start-Sleep 3
$n = Get-Process caddy -ErrorAction SilentlyContinue
Write-Host ('Caddy PID: ' + $n.Id)
Write-Host '部署完成!'
""")
print(r.stdout.strip())

# 清理
print("\n[8] 清理临时文件...")
remote(f"""
Remove-Item '{REMOTE_DIR}' -Recurse -Force -ErrorAction SilentlyContinue
Write-Host '清理完成'
""")

# 关闭会话
run_ps(f"$s = Get-PSSession -Id {sess_id}; Remove-PSSession $s")
print("会话已关闭")
print("\n=== 部署完成! ===")
