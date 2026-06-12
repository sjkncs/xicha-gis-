#!/usr/bin/env python3
import subprocess, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOST = "64.90.0.78"
PORT = 5985
USER = "Administrator"
PASS = "asR84SiRzqhbDvZF"

# Kill existing Caddy
print("Stopping all Caddy processes...")
r = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Invoke-Command -Session $s -ScriptBlock {{
    Get-Process caddy -ErrorAction SilentlyContinue | Stop-Process -Force
    Write-Host "Killed"
}}
Remove-PSSession $s
"""],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
)
for line in r.stdout.split("\n"):
    if line.strip(): print(line)
time.sleep(3)

# Create Task Scheduler task to start Caddy as SYSTEM
print("\nCreating Task Scheduler task...")
r = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Invoke-Command -Session $s -ScriptBlock {{
    # Delete existing task
    schtasks /delete /tn "CaddyWebServer" /f 2>&1 | Out-Null

    # Create new task
    $cmd = 'C:\\globalreviewops\\caddy\\caddy.exe run --config C:\\globalreviewops\\Caddyfile --adapter caddyfile'
    schtasks /create /tn "CaddyWebServer" /tr "$cmd" /sc once /st 00:00 /ru SYSTEM /f /rl HIGHEST 2>&1 | ForEach-Object {{ Write-Host "SCH: $_" }}

    # Run it now
    Start-Sleep 1
    schtasks /run /tn "CaddyWebServer" 2>&1 | ForEach-Object {{ Write-Host "RUN: $_" }}
    Write-Host "Task started"
}}
Remove-PSSession $s
"""],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
)
for line in r.stdout.split("\n"):
    if line.strip(): print(line)

# Wait and check
time.sleep(10)
print("\nChecking status...")
r = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Invoke-Command -Session $s -ScriptBlock {{
    $p = Get-Process caddy -ErrorAction SilentlyContinue
    if ($p) {{ Write-Host "Caddy PID=$($p.Id)" }} else {{ Write-Host "Caddy not running" }}
    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {{ $_.LocalPort -in @(80,443) }} | Format-Table LocalAddress,LocalPort,State,OwningProcess
    Write-Host "HTTP test:"
    try {{
        $r2 = Invoke-WebRequest -Uri 'http://127.0.0.1/city_visualization_3d.html' -TimeoutSec 5 -UseBasicParsing
        Write-Host "OK Len=$($r2.Content.Length)"
    }} catch {{
        Write-Host "ERR: $($_.Exception.Message)"
    }}
}}
Remove-PSSession $s
"""],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
)
for line in r.stdout.split("\n"):
    if line.strip(): print(line)
