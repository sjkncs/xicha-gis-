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
    Write-Host "=== Caddy 状态 ==="
    $p = Get-Process caddy -ErrorAction SilentlyContinue
    if ($p) {{ Write-Host "Caddy PID=$($p.Id)" }} else {{ Write-Host "CADDY_DOWN" }}

    Write-Host "=== 防火墙规则 ==="
    Get-NetFirewallRule | Where-Object {{ $_.DisplayName -like '*HTTP*' -or $_.DisplayName -like '*HTTPS*' -or $_.DisplayName -like '*80*' -or $_.DisplayName -like '*443*' -or $_.DisplayName -like '*Caddy*' }} | Select-Object Name,DisplayName,Enabled,Direction | Format-Table

    Write-Host "=== 端口监听 ==="
    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {{ $_.LocalPort -in @(80,443,8080) }} | Format-Table LocalAddress,LocalPort,State,OwningProcess

    Write-Host "=== 本地HTTP测试 ==="
    try {{
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1/city_visualization_3d.html' -TimeoutSec 5 -UseBasicParsing
        Write-Host "127 OK Len=$($r.Content.Length)"
    }} catch {{
        Write-Host "127 ERR: $($_.Exception.Message)"
    }}

    Write-Host "=== Caddy 版本 ==="
    & 'C:\\globalreviewops\\caddy\\caddy.exe' version 2>&1 | Select-Object -First 3

    Write-Host "=== Cloudflare 代理测试 ==="
    # 直接测试到 Cloudflare IP 的连通性
    Test-NetConnection -ComputerName 104.16.123.96 -Port 443 -InformationLevel Quiet
    Test-NetConnection -ComputerName 15min.globalreviewops.xyz -Port 443 -InformationLevel Quiet
}}
Remove-PSSession $s
"""],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
)
for line in r.stdout.split("\n"):
    if line.strip():
        print(line)
