#!/usr/bin/env python3
import subprocess, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOST = "64.90.0.78"
PORT = 5985
USER = "Administrator"
PASS = "asR84SiRzqhbDvZF"

r = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Invoke-Command -Session $s -ScriptBlock {{
    Write-Host "=== 当前 Caddyfile ==="
    Get-Content 'C:\\globalreviewops\\Caddyfile' | ForEach-Object {{ Write-Host $_ }}
    Write-Host "=== 更新 Caddyfile ==="
    $caddyfile = @'
{{
    admin off
}}
globalreviewops.xyz, www.globalreviewops.xyz {{
    encode gzip
    handle /cs-agent {{
        redir /cs-agent/ 308
    }}
    handle_path /cs-agent/* {{
        reverse_proxy 127.0.0.1:8091
    }}
    reverse_proxy 127.0.0.1:8080
}}
http://64.90.0.18 {{
    encode gzip
    handle /cs-agent {{
        redir /cs-agent/ 308
    }}
    handle_path /cs-agent/* {{
        reverse_proxy 127.0.0.1:8091
    }}
    reverse_proxy 127.0.0.1:8080
}}
http://64.90.0.78 {{
    encode gzip zstd
    handle /api/* {{
        reverse_proxy 127.0.0.1:8765
    }}
    handle {{
        root * C:/www/15min/static
        try_files {{path}} /city_twin_viewer.html
        file_server
    }}
    header {{
        X-Content-Type-Options nosniff
        Referrer-Policy strict-origin-when-cross-origin
    }}
}}
15min.globalreviewops.xyz {{
    encode gzip zstd
    handle /api/* {{
        reverse_proxy 127.0.0.1:8765
    }}
    handle {{
        root * C:/www/15min/static
        try_files {{path}} /city_twin_viewer.html
        file_server
    }}
    header {{
        X-Content-Type-Options nosniff
        Referrer-Policy strict-origin-when-cross-origin
    }}
}}
'@
    Set-Content -Path 'C:\\globalreviewops\\Caddyfile' -Value $caddyfile -Encoding UTF8
    Write-Host "Caddyfile 已更新"
    Get-Content 'C:\\globalreviewops\\Caddyfile' | ForEach-Object {{ Write-Host $_ }}
}}
Remove-PSSession $s
"""],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
)
for line in r.stdout.split("\n"):
    if line.strip(): print(line)

time.sleep(2)

# Restart Caddy via Task Scheduler
print("\nRestarting Caddy...")
r2 = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Invoke-Command -Session $s -ScriptBlock {{
    Get-Process caddy -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep 2
    schtasks /run /tn "CaddyWebServer" 2>&1 | ForEach-Object {{ Write-Host $_ }}
    Start-Sleep 5
    $p = Get-Process caddy -ErrorAction SilentlyContinue
    if ($p) {{ Write-Host "Caddy PID=$($p.Id)" }} else {{ Write-Host "Caddy not running" }}
    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {{ $_.LocalPort -in @(80,443) }} | Format-Table LocalAddress,LocalPort,OwningProcess
}}
Remove-PSSession $s
"""],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
)
for line in r2.stdout.split("\n"):
    if line.strip(): print(line)
