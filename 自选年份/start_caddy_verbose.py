#!/usr/bin/env python3
import subprocess, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOST = "64.90.0.78"
PORT = 5985
USER = "Administrator"
PASS = "asR84SiRzqhbDvZF"

# Stop existing Caddy first
print("Stopping existing Caddy...")
r = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Invoke-Command -Session $s -ScriptBlock {{
    Get-Process caddy -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep 2
    Write-Host "Caddy已停止"
}}
Remove-PSSession $s
"""],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
)
for line in r.stdout.split("\n"):
    if line.strip():
        print(line)

time.sleep(3)

# Start Caddy in foreground and capture output
print("\nStarting Caddy in foreground (10s)...")
r = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Invoke-Command -Session $s -ScriptBlock {{
    Write-Host "=== 启动 Caddy ==="
    $caddyExe = 'C:\\globalreviewops\\caddy\\caddy.exe'
    $caddyArgs = @('run','--config','C:\\globalreviewops\\Caddyfile','--adapter','caddyfile')
    Write-Host "exe=$caddyExe"
    Write-Host "args=$caddyArgs"

    # Start as background job to capture output
    $job = Start-Job -ScriptBlock {{
        param($exe, $args, $wait)
        $proc = Start-Process -FilePath $exe -ArgumentList $args -NoNewWindow -PassThru -RedirectStandardOutput 'C:\\Users\\Administrator\\caddy_out.txt' -RedirectStandardError 'C:\\Users\\Administrator\\caddy_err.txt'
        Start-Sleep $wait
        $proc | Stop-Process -Force -ErrorAction SilentlyContinue
        Write-Host "进程已停止"
    }} -ArgumentList $caddyExe, $caddyArgs, 10

    Start-Sleep 12

    Write-Host "=== Caddy stdout ==="
    Get-Content 'C:\\Users\\Administrator\\caddy_out.txt' -ErrorAction SilentlyContinue | Select-Object -First 30 | ForEach-Object {{ Write-Host "OUT: $_" }}
    Write-Host "=== Caddy stderr ==="
    Get-Content 'C:\\Users\\Administrator\\caddy_err.txt' -ErrorAction SilentlyContinue | Select-Object -First 30 | ForEach-Object {{ Write-Host "ERR: $_" }}

    $p = Get-Process caddy -ErrorAction SilentlyContinue
    if ($p) {{ Write-Host "Caddy运行 PID=$($p.Id)" }} else {{ Write-Host "Caddy未运行" }}

    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {{ $_.LocalPort -in @(80,443) }} | Format-Table LocalAddress,LocalPort,State,OwningProcess
}}
Remove-PSSession $s
"""],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
)
for line in r.stdout.split("\n"):
    if line.strip():
        print(line)
