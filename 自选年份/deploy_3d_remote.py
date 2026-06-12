# -*- coding: utf-8 -*-
"""部署 3D 可视化包到远程服务器 (WinRM + Base64 分块)"""
import subprocess, sys, os, base64, time

HOST = "64.90.0.78"
PORT = 5985
USER = "Administrator"
PASS = "asR84SiRzqhbDvZF"
ZIP_PATH = r"E:\xicha gis 智能定位\自选年份\deploy_3d.zip"
CHUNK_KB = 4096  # 4 MB per chunk

print(f"读取 ZIP: {ZIP_PATH}")
sz = os.path.getsize(ZIP_PATH)
print(f"文件大小: {sz/1024/1024:.1f} MB")
assert sz > 0, "ZIP 文件为空!"

with open(ZIP_PATH, "rb") as f:
    raw = f.read()
b64 = base64.b64encode(raw).decode("ascii")
print(f"Base64 长度: {len(b64)/1024/1024:.1f} MB")

# PowerShell 脚本模板
def ps(cmd):
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        capture_output=True, text=True, errors="replace"
    )
    if r.returncode != 0:
        print(f"ERROR: {r.stderr[:300]}")
    return r

# 连接测试
print("\n[1] 测试 WinRM 连接...")
r = ps(f"$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -ErrorAction Stop; Write-Host 'OK'; Remove-PSSession $s")
if r.returncode != 0:
    print("连接失败，请检查网络和凭据")
    sys.exit(1)
print("连接成功!")

# 建立持久会话
sess = ps(f"""$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force)))""")
print(f"会话建立: {sess.returncode}")

def remote(cmd):
    full = f"""Invoke-Command -Session $s -ScriptBlock {{ {cmd} }}"""
    return ps(full)

# 清理旧文件
print("\n[2] 清理旧文件...")
remote("if (Test-Path 'C:\\www\\15min\\static') { Remove-Item 'C:\\www\\15min\\static\\*' -Recurse -Force }")

# 分块传输
n_chunks = (len(b64) + CHUNK_KB*1024 - 1) // (CHUNK_KB*1024)
print(f"\n[3] 分块传输 ({n_chunks} 块, 每块 {CHUNK_KB} KB)...")
t0 = time.time()
for i in range(n_chunks):
    chunk = b64[i*(CHUNK_KB*1024):(i+1)*(CHUNK_KB*1024)]
    chunk_b64 = base64.b64encode(chunk.encode("ascii")).decode("ascii")
    chunk_len = len(chunk)
    mode = "a" if i > 0 else "w"
    cmd = f"""
    $tmp = 'C:\\dp3d_part_{i:03d}.b64';
    [IO.File]::WriteAllText($tmp, [Convert]::FromBase64String('{chunk_b64}'), [Text.Encoding]::ASCII);
    $f = if (Test-Path 'C:\\dp3d_all.b64') {{ [IO.File]::AppendAllText('C:\\dp3d_all.b64', [IO.File]::ReadAllText($tmp), [Text.Encoding]::ASCII) }} else {{ [IO.File]::WriteAllText('C:\\dp3d_all.b64', [IO.File]::ReadAllText($tmp), [Text.Encoding]::ASCII) }};
    Write-Host 'chunk_{i}:{chunk_len}:done'
    """
    r = ps(f"""$s = Get-PSSession -Id 1 -ErrorAction SilentlyContinue; if ($s) {{ Invoke-Command -Session $s -ScriptBlock {{ {cmd.strip()} }} }} else {{ Write-Host 'NO_SESSION' }}""")
    pct = (i+1)/n_chunks*100
    elapsed = time.time()-t0
    eta = elapsed/(i+1)*(n_chunks-i-1)
    print(f"  [{i+1}/{n_chunks}] {pct:.0f}% | 已传 {chunk_len/1024:.0f} KB | 预计剩余: {eta:.0f}s", end="\r")

print(f"\n传输完成! 耗时: {time.time()-t0:.0f}s")

# 解码并写入 zip
print("\n[4] 解码并写入 ZIP...")
decode_cmd = """
$b64 = [IO.File]::ReadAllText('C:\\dp3d_all.b64', [Text.Encoding]::ASCII);
$zip = [Convert]::FromBase64String($b64);
[IO.File]::WriteAllBytes('C:\\dp3d.zip', $zip);
Write-Host ('ZIP 大小:' + ([IO.File]::ReadAllBytes('C:\\dp3d.zip').Length / 1MB).ToString('F1') + 'MB')
"""
r = ps(f"""$s = Get-PSSession -Id 1; Invoke-Command -Session $s -ScriptBlock {{{decode_cmd}}}""")
print(r.stdout.strip())
print(r.stderr.strip()[:200] if r.stderr else "")

# 解压
print("\n[5] 解压到 C:\\www\\15min\\static...")
extract_cmd = """
if (Test-Path 'C:\\www\\15min\\static') {} else { New-Item -ItemType Directory -Path 'C:\\www\\15min\\static' -Force | Out-Null }
[IO.Compression.ZipFile]::ExtractToDirectory('C:\\dp3d.zip', 'C:\\www\\15min\\static');
Write-Host '解压完成'
Get-ChildItem 'C:\\www\\15min\\static' | Select-Object Name, Length | Format-Table -AutoSize
"""
r = ps(f"""$s = Get-PSSession -Id 1; Invoke-Command -Session $s -ScriptBlock {{ {extract_cmd} }}""")
print(r.stdout)
print(r.stderr[:300] if r.stderr else "")

# 重启 Caddy
print("\n[6] 重启 Caddy...")
restart_cmd = """
$caddy = Get-Process caddy -ErrorAction SilentlyContinue
if ($caddy) { Stop-Process caddy -Force; Start-Sleep 2; Write-Host 'Caddy stopped' }
Start-Process 'C:\\ProgramData\\caddy\\caddy.exe' -ArgumentList 'run','--config','C:\\globalreviewops\\Caddyfile','--adapter','caddyfile' -NoNewWindow -PassThru | Out-Null
Start-Sleep 3
Get-Process caddy -ErrorAction SilentlyContinue | Select-Object Id, ProcessName | Format-Table -AutoSize
Write-Host '部署完成!'
"""
r = ps(f"""$s = Get-PSSession -Id 1; Invoke-Command -Session $s -ScriptBlock {{{restart_cmd}}}""")
print(r.stdout)
print(r.stderr[:300] if r.stderr else "")

# 清理
print("\n[7] 清理临时文件...")
cleanup_cmd = """
Remove-Item 'C:\\dp3d_part_*.b64' -Force -ErrorAction SilentlyContinue
Remove-Item 'C:\\dp3d_all.b64' -Force -ErrorAction SilentlyContinue
Remove-Item 'C:\\dp3d.zip' -Force -ErrorAction SilentlyContinue
Write-Host '清理完成'
"""
ps(f"""$s = Get-PSSession -Id 1; Invoke-Command -Session $s -ScriptBlock {{{cleanup_cmd}}}""")

# 关闭会话
ps("""$s = Get-PSSession -Id 1 -ErrorAction SilentlyContinue; if ($s) { Remove-PSSession $s }""")
print("\n部署脚本完成!")
