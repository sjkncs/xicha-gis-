#!/usr/bin/env python3
import subprocess, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

HOST = "64.90.0.78"
PORT = 5985
USER = "Administrator"
PASS = "asR84SiRzqhbDvZF"

# Start Caddy via Task Scheduler so it persists after session ends
r = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Invoke-Command -Session $s -ScriptBlock {{
    Write-Host "=== Caddy 启动 ==="
    $caddyExe = 'C:\\globalreviewops\\caddy\\caddy.exe'
    $caddyArgs = 'run --config C:\\globalreviewops\\Caddyfile --adapter caddyfile'

    # 停止现有进程
    $existing = Get-Process caddy -ErrorAction SilentlyContinue
    if ($existing) {{
        Write-Host "停止现有 Caddy (PID=$($existing.Id))..."
        Stop-Process $existing -Force
        Start-Sleep 3
    }}

    # 方案1: 通过 Start-Process 启动（测试用）
    Write-Host "尝试 Start-Process 启动..."
    Start-Process -FilePath $caddyExe -ArgumentList $caddyArgs -NoNewWindow -PassThru | Out-Null
    Start-Sleep 5

    $p = Get-Process caddy -ErrorAction SilentlyContinue
    if ($p) {{
        Write-Host "SUCCESS: Caddy 运行中 PID=$($p.Id)"
    }} else {{
        Write-Host "Start-Process 失败，尝试 schtasks..."
        # 方案2: 通过 Task Scheduler
        schtasks /create /tn "CaddyWeb" /tr "\\"$caddyExe\\" $caddyArgs" /sc onstart /ru SYSTEM /f /rl HIGHEST 2>&1 | ForEach-Object {{ Write-Host "SCHTASK: $_" }}
        Start-Sleep 2
        schtasks /run /tn "CaddyWeb" 2>&1 | ForEach-Object {{ Write-Host "RUN: $_" }}
        Start-Sleep 5
        $p = Get-Process caddy -ErrorAction SilentlyContinue
        if ($p) {{ Write-Host "SUCCESS via schtasks: PID=$($p.Id)" }} else {{ Write-Host "SCHTASKS_FAILED" }}
    }}

    # 验证端口
    Start-Sleep 2
    $conn = Get-NetTCPConnection -LocalPort 80 -ErrorAction SilentlyContinue | Select-Object -First 3
    if ($conn) {{ foreach($c in $conn) {{ Write-Host "PORT80 OK PID=$($c.OwningProcess)" }} }} else {{ Write-Host "PORT80_NOT_LISTENING" }}

    # 尝试直接HTTP测试
    try {{
        $resp = Invoke-WebRequest -Uri 'http://localhost/' -TimeoutSec 5 -UseBasicParsing
        Write-Host "HTTP OK $($resp.StatusCode)"
    }} catch {{
        Write-Host "HTTP TEST: $($_.Exception.Message)"
    }}
}}
Remove-PSSession $s
"""],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
)
for line in r.stdout.split("\n"):
    if line.strip():
        print(line)
if r.returncode != 0:
    print("RC:", r.returncode)
