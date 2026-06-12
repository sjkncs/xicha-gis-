#!/usr/bin/env python3
import subprocess, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

HOST = "64.90.0.78"
PORT = 5985
USER = "Administrator"
PASS = "asR84SiRzqhbDvZF"

r = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Invoke-Command -Session $s -ScriptBlock {{
    $p = Get-Process caddy -ErrorAction SilentlyContinue
    if ($p) {{ Write-Host "CADDY_RUN PID=$($p.Id) $($p.Path)" }} else {{ Write-Host "CADDY_DOWN" }}
    $l = Get-NetTCPConnection -LocalPort 80 -ErrorAction SilentlyContinue | Select-Object -First 3
    if ($l) {{ foreach($c in $l) {{ Write-Host "PORT80 PID=$($c.OwningProcess)" }} }} else {{ Write-Host "PORT80_NONE" }}
    Write-Host "FILES:"
    Get-ChildItem 'C:\\www\\15min\\static' -ErrorAction SilentlyContinue | ForEach-Object {{ Write-Host "$($_.Name)=$([math]::Round($_.Length/1MB,1))MB" }}
}}
Remove-PSSession $s
Write-Host "SESSION_CLOSED"
"""],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
)
for line in r.stdout.split("\n"):
    if line.strip():
        print(line)
if r.returncode != 0:
    print("RC:", r.returncode)
