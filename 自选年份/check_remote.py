#!/usr/bin/env python3
import subprocess

HOST = "64.90.0.78"
PORT = 5985
USER = "Administrator"
PASS = "asR84SiRzqhbDvZF"

cmd = f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Write-Host "=== Caddy 进程 ==="
$c = Get-Process caddy -ErrorAction SilentlyContinue
if ($c) {{ Write-Host "运行中 PID=$($c.Id) Path=$($c.Path)" }} else {{ Write-Host "未运行" }}
Write-Host "=== 监听端口 ==="
Get-NetTCPConnection -LocalPort 80 -ErrorAction SilentlyContinue | Format-Table LocalAddress,LocalPort,State,OwningProcess
Write-Host "=== Caddy 日志 ==="
Get-ChildItem 'C:\\globalreviewops\\caddy\\*.log' -ErrorAction SilentlyContinue | ForEach-Object {{ Get-Content $_.FullName -Tail 5 }}
Write-Host "=== Caddyfile ==="
if (Test-Path 'C:\\globalreviewops\\Caddyfile') {{ Write-Host "存在" }} else {{ Write-Host "不存在" }}
Write-Host "=== WWW目录 ==="
Get-ChildItem 'C:\\www\\15min\\static' -ErrorAction SilentlyContinue | Select-Object Name, Length | Format-Table
Remove-PSSession $s
"""

r = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
)
print("STDOUT:", r.stdout[:3000])
if r.stderr:
    print("STDERR:", r.stderr[:500])
print("RC:", r.returncode)
