#!/usr/bin/env python3
import subprocess
import time
import sys
import os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

HOST = "64.90.0.78"
PORT = 5985
USER = "Administrator"
PASS = "asR84SiRzqhbDvZF"
LOCAL_ZIP = r"E:\xicha gis 智能定位\自选年份\deploy_3d.zip"
REMOTE_DIR = r"C:\dp3d_work"
WWW_DIR = r"C:\www\15min\static"

CREDS = f"{USER}@{HOST}"
LOCAL_B64 = r"C:\Users\Administrator\dp3d.b64"
LOCAL_BAT = r"C:\Users\Administrator\deploy_step.bat"

def ps(script, timeout=120):
    """Run PowerShell command via subprocess"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-Command", script],
        capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace", env=env
    )
    out = result.stdout.strip()
    err = result.stderr.strip()
    if out:
        for line in out.splitlines():
            print(line)
    if err:
        for line in err.splitlines():
            print(f"ERR: {line}")
    return out, result.returncode

def ps_file(script_path, timeout=600):
    """Run PowerShell script file"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", script_path],
        capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace", env=env
    )
    out = result.stdout.strip()
    err = result.stderr.strip()
    if out:
        for line in out.splitlines():
            print(line)
    if err:
        for line in err.splitlines():
            print(f"ERR: {line}")
    return result.returncode

# Step 1: Test basic connectivity
print("=" * 60)
print("Step 1: 测试远程连接...")
print("=" * 60)
out, code = ps(f"""
$srv = '{HOST}'
$prt = {PORT}
$usr = '{USER}'
$pwd = '{PASS}'
$sec = ConvertTo-SecureString $pwd -AsPlainText -Force
$crd = New-Object PSCredential($usr, $sec)
Write-Host '建立会话...'
$s = New-PSSession -ComputerName $srv -Port $prt -Credential $crd -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Write-Host ('会话ID: ' + $s.Id)
Write-Host ('会话状态: ' + $s.State)
Write-Host '测试 Echo...'
$r = Invoke-Command -Session $s -ScriptBlock {{ Write-Host '远程Echo成功!' }}
Write-Host $r
Remove-PSSession $s -ErrorAction SilentlyContinue
Write-Host '完成'
""", timeout=60)
print(f"Step 1 返回码: {code}")
print()

# Step 2: Create remote directory
print("=" * 60)
print("Step 2: 创建远程目录...")
print("=" * 60)
out, code = ps(f"""
$srv = '{HOST}'
$prt = {PORT}
$usr = '{USER}'
$pwd = '{PASS}'
$sec = ConvertTo-SecureString $pwd -AsPlainText -Force
$crd = New-Object PSCredential($usr, $sec)
$s = New-PSSession -ComputerName $srv -Port $prt -Credential $crd -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Write-Host ('会话ID: ' + $s.Id)
Invoke-Command -Session $s -ScriptBlock {{
    $d = '{REMOTE_DIR}'
    if (Test-Path $d) {{ Remove-Item $d -Recurse -Force }}
    New-Item -ItemType Directory -Path $d -Force | Out-Null
    Write-Host ('目录创建: ' + $d)
    if (!(Test-Path 'C:\\www\\15min\\static')) {{
        New-Item -ItemType Directory -Path 'C:\\www\\15min\\static' -Force | Out-Null
    }}
    Remove-Item 'C:\\www\\15min\\static\\*' -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host 'www目录已清空'
}}
Remove-PSSession $s -ErrorAction SilentlyContinue
Write-Host 'Step2完成'
""", timeout=60)
print(f"Step 2 返回码: {code}")
print()

# Step 3: Upload ZIP via Copy-Item
zip_size_mb = round(os.path.getsize(LOCAL_ZIP) / 1024 / 1024, 1)
print("=" * 60)
print(f"Step 3: 上传 ZIP ({zip_size_mb} MB)...")
print("=" * 60)
print("预计时间约 5-15 分钟，请耐心等待...")
t0 = time.time()
out, code = ps(f"""
$srv = '{HOST}'
$prt = {PORT}
$usr = '{USER}'
$pwd = '{PASS}'
$sec = ConvertTo-SecureString $pwd -AsPlainText -Force
$crd = New-Object PSCredential($usr, $sec)
$s = New-PSSession -ComputerName $srv -Port $prt -Credential $crd -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Write-Host ('会话ID: ' + $s.Id)
Write-Host '开始Copy-Item...'
Copy-Item -Path '{LOCAL_ZIP}' -Destination '{REMOTE_DIR}\\dp.zip' -ToSession $s
Write-Host 'Copy-Item完成!'
Invoke-Command -Session $s -ScriptBlock {{
    $sz = (Get-Item '{REMOTE_DIR}\\dp.zip').Length / 1MB
    Write-Host ('远程文件大小: ' + [math]::Round($sz,1) + ' MB')
}}
Remove-PSSession $s -ErrorAction SilentlyContinue
Write-Host 'Step3完成'
""", timeout=900)
elapsed = time.time() - t0
print(f"Step 3 返回码: {code}, 耗时: {elapsed:.0f}s")
print()

# Step 4: Extract and deploy
print("=" * 60)
print("Step 4: 解压并部署...")
print("=" * 60)
out, code = ps(f"""
$srv = '{HOST}'
$prt = {PORT}
$usr = '{USER}'
$pwd = '{PASS}'
$sec = ConvertTo-SecureString $pwd -AsPlainText -Force
$crd = New-Object PSCredential($usr, $sec)
$s = New-PSSession -ComputerName $srv -Port $prt -Credential $crd -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Write-Host ('会话ID: ' + $s.Id)
Invoke-Command -Session $s -ScriptBlock {{
    Write-Host '开始解压...'
    try {{
        [IO.Compression.ZipFile]::ExtractToDirectory('{REMOTE_DIR}\\dp.zip', '{WWW_DIR}')
        Write-Host '解压完成'
    }} catch {{
        Write-Host ('解压失败: ' + $_.Exception.Message)
    }}
    Write-Host '列出文件:'
    Get-ChildItem '{WWW_DIR}' | ForEach-Object {{
        $mb = [math]::Round($_.Length / 1MB, 1)
        Write-Host ('  ' + $_.Name + ' (' + $mb + ' MB)')
    }}
    Write-Host '重启Caddy...'
    $c = Get-Process caddy -ErrorAction SilentlyContinue
    if ($c) {{ Stop-Process $c -Force; Start-Sleep 2 }}
    Start-Process 'C:\\ProgramData\\caddy\\caddy.exe' -ArgumentList 'run','--config','C:\\globalreviewops\\Caddyfile','--adapter','caddyfile' -NoNewWindow -PassThru | Out-Null
    Start-Sleep 3
    $n = Get-Process caddy -ErrorAction SilentlyContinue
    Write-Host ('Caddy PID: ' + $n.Id)
    Write-Host '清理临时文件...'
    Remove-Item '{REMOTE_DIR}' -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host '清理完成'
}}
Remove-PSSession $s -ErrorAction SilentlyContinue
Write-Host 'Step4完成'
Write-Host '=== 部署完成 ==='
Write-Host '访问: http://{HOST}/city_visualization_3d.html'
""", timeout=300)
print(f"Step 4 返回码: {code}")
print()
print("=" * 60)
print("部署完成!")
print(f"访问: http://{HOST}/city_visualization_3d.html")
print("=" * 60)
