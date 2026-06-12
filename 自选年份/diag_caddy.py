#!/usr/bin/env python3
import subprocess, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOST = "64.90.0.78"
PORT = 5985
USER = "Administrator"
PASS = "asR84SiRzqhbDvZF"

r = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Invoke-Command -Session $s -ScriptBlock {{
    Write-Host "=== Caddyfile ==="
    Get-Content 'C:\\globalreviewops\\Caddyfile' -ErrorAction SilentlyContinue | ForEach-Object {{ Write-Host $_ }}
    Write-Host "=== Caddy 进程 ==="
    $p = Get-Process caddy -ErrorAction SilentlyContinue
    if ($p) {{ Write-Host "Caddy PID=$($p.Id)" }} else {{ Write-Host "CADDY_DOWN" }}
    Write-Host "=== 监听端口 ==="
    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {{ $_.LocalPort -in @(80,443,8080) }} | Format-Table LocalAddress,LocalPort,State,OwningProcess
    Write-Host "=== HTTP 本地测试 ==="
    try {{
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1/' -TimeoutSec 5 -UseBasicParsing
        Write-Host "127.0.0.1 OK $($r.StatusCode)"
    }} catch {{
        Write-Host "127 ERR: $($_.Exception.Message)"
    }}
    try {{
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1/city_visualization_3d.html' -TimeoutSec 5 -UseBasicParsing
        Write-Host "3D OK Len=$($r.Content.Length)"
    }} catch {{
        Write-Host "3D ERR: $($_.Exception.Message)"
    }}
    Write-Host "=== Caddy 日志 ==="
    Get-ChildItem 'C:\\globalreviewops\\caddy\\*.log' -ErrorAction SilentlyContinue | ForEach-Object {{
        Write-Host "--- $($_.Name) ---"
        Get-Content $_.FullName -Tail 10 -ErrorAction SilentlyContinue | ForEach-Object {{ Write-Host $_ }}
    }}
}}
Remove-PSSession $s
"""],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
)
for line in r.stdout.split("\n"):
    if line.strip():
        print(line)
