#!/usr/bin/env python3
"""Deploy 3D visualization package to remote Windows server."""
import subprocess
import os

HOST = "64.90.0.78"
PORT = 5985
USER = "Administrator"
PASS = "asR84SiRzqhbDvZF"
LOCAL_ZIP = r"E:\xicha gis 智能定位\自选年份\deploy_3d.zip"
REMOTE_DIR = r"C:\dp3d_work"
WWW_DIR = r"C:\www\15min\static"

def ps_block(block_name, commands):
    print(f"\n{'='*60}\n{block_name}\n{'='*60}")
    code = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", commands],
        capture_output=True, text=True, timeout=600,
        encoding="utf-8", errors="replace"
    )
    print(code.stdout or "(no stdout)")
    if code.stderr:
        print("STDERR:", code.stderr)
    return code.returncode

# Step 1: Test connection
rc = ps_block("Step 1: 连接测试", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Write-Host "会话ID: $($s.Id)"
Write-Host "会话状态: $($s.State)"
Invoke-Command -Session $s -ScriptBlock {{ Write-Host "远程Echo: 成功!" }}
Remove-PSSession $s
""")
print(f"返回码: {rc}")

# Step 2: Setup directories
rc = ps_block("Step 2: 初始化目录", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Invoke-Command -Session $s -ScriptBlock {{
    if (Test-Path '{REMOTE_DIR}') {{ Remove-Item '{REMOTE_DIR}' -Recurse -Force }}
    New-Item -ItemType Directory -Path '{REMOTE_DIR}' -Force | Out-Null
    Write-Host "远程目录: {REMOTE_DIR}"
    if (!(Test-Path '{WWW_DIR}')) {{ New-Item -ItemType Directory -Path '{WWW_DIR}' -Force | Out-Null }}
    Remove-Item '{WWW_DIR}\\*' -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "WWW目录已清空"
}}
Remove-PSSession $s
""")
print(f"返回码: {rc}")

# Step 3: Upload ZIP
rc = ps_block("Step 3: 上传ZIP", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Write-Host "会话ID: $($s.Id)"
Write-Host "开始上传ZIP..."
Copy-Item -Path '{LOCAL_ZIP}' -Destination '{REMOTE_DIR}\dp.zip' -ToSession $s
Invoke-Command -Session $s -ScriptBlock {{
    $sz = [math]::Round((Get-Item '{REMOTE_DIR}\dp.zip').Length / 1MB, 1)
    Write-Host "远程文件: $sz MB"
}}
Remove-PSSession $s
Write-Host "上传完成"
""")
print(f"返回码: {rc}")

# Step 4: Diagnose Caddy and .NET
rc = ps_block("Step 4: 诊断环境", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Invoke-Command -Session $s -ScriptBlock {{
    Write-Host "=== Caddy 进程 ==="
    Get-Process caddy -ErrorAction SilentlyContinue | Format-Table Id, ProcessName
    Write-Host "=== Caddy 服务 ==="
    Get-Service caddy -ErrorAction SilentlyContinue | Format-Table Status, StartType
    Write-Host "=== 搜索 Caddy ==="
    Get-ChildItem -Path 'C:\' -Filter 'caddy.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 5 FullName | Format-Table
    Write-Host "=== 当前解压文件 ==="
    Get-ChildItem '{WWW_DIR}' -ErrorAction SilentlyContinue | Select-Object Name, Length | Format-Table
}}
Remove-PSSession $s
""")
print(f"返回码: {rc}")
