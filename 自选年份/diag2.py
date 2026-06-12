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
    Write-Host "=== 所有监听端口 ==="
    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Format-Table LocalAddress,LocalPort,State,OwningProcess
    Write-Host "=== PID 8908 是什么? ==="
    Get-Process -Id 8908 -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,Path | Format-Table
    Write-Host "=== Caddy 相关进程 ==="
    Get-Process | Where-Object {{ $_.ProcessName -like '*caddy*' -or $_.ProcessName -like '*Caddy*' }} | Select-Object Id,ProcessName,Path | Format-Table
    Write-Host "=== 服务列表 ==="
    Get-Service | Where-Object {{ $_.DisplayName -like '*caddy*' -or $_.Name -like '*caddy*' }} | Select-Object Status,StartType,DisplayName | Format-Table
    Write-Host "=== HTTP 本地测试 ==="
    try {{
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/city_visualization_3d.html' -TimeoutSec 5 -UseBasicParsing
        Write-Host "8080 OK Len=$($r.Content.Length)"
    }} catch {{
        Write-Host "8080 ERR: $($_.Exception.Message)"
    }}
    Write-Host "=== 直接读取静态文件 ==="
    $f = 'C:\\www\\15min\\static\\city_visualization_3d.html'
    if (Test-Path $f) {{ Write-Host "文件存在 Size=$(Get-Item $f).Length" }} else {{ Write-Host "文件不存在" }}
    Write-Host "=== 启动 Caddy (nohup 风格) ==="
    $caddyExe = 'C:\\globalreviewops\\caddy\\caddy.exe'
    Write-Host "Caddy路径存在=$(Test-Path $caddyExe)"
    # 使用 -WindowStyle Hidden 避免GUI窗口
    Start-Process -FilePath $caddyExe -ArgumentList 'run','--config','C:\\globalreviewops\\Caddyfile','--adapter','caddyfile' -NoNewWindow -PassThru | ForEach-Object {{ Write-Host "启动 PID=$($_.Id)" }}
    Start-Sleep 5
    $p = Get-Process caddy -ErrorAction SilentlyContinue
    if ($p) {{ Write-Host "Caddy运行 PID=$($p.Id)" }} else {{ Write-Host "Caddy未运行" }}
    Write-Host "=== 端口检测 ==="
    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {{ $_.LocalPort -in @(80,443) }} | Format-Table
    Write-Host "=== HTTP本地测试8080 ==="
    try {{
        $r2 = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/city_visualization_3d.html' -TimeoutSec 5 -UseBasicParsing
        Write-Host "8080 Len=$($r2.Content.Length)"
    }} catch {{
        Write-Host "8080 ERR: $($_.Exception.Message)"
    }}
}}
Remove-PSSession $s
"""],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
)
for line in r.stdout.split("\n"):
    if line.strip():
        print(line)
