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
    Write-Host "=== Caddy 内存 ==="
    $p = Get-Process caddy -ErrorAction SilentlyContinue
    if ($p) {{ Write-Host "WorkingSet=$(($p.WorkingSet64)/1MB)MB Private=$(($p.PrivateMemorySize64)/1MB)MB" }} else {{ Write-Host "Caddy未运行" }}

    Write-Host "=== 系统内存 ==="
    $mem = Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory
    $totalMB = [math]::Round($mem.TotalVisibleMemorySize/1KB,0)
    $freeMB = [math]::Round($mem.FreePhysicalMemory/1KB,0)
    Write-Host "Total={0}MB Free={1}MB" -f $totalMB,$freeMB

    Write-Host "=== 磁盘空间 ==="
    Get-Volume -ErrorAction SilentlyContinue | Where-Object {{ $_.DriveLetter -eq 'C' }} | Select-Object DriveLetter,FileSystemLabel,SizeRemaining | Format-Table

    Write-Host "=== 测试小文件 ==="
    try {{
        $r2 = Invoke-WebRequest -Uri 'http://15min.globalreviewops.xyz/city_visualization.html' -TimeoutSec 10 -UseBasicParsing
        Write-Host "small HTML OK Len=$($r2.Content.Length)"
    }} catch {{
        Write-Host "small HTML ERR: $($_.Exception.Message)"
    }}

    Write-Host "=== Caddy 重启 ==="
    Get-Process caddy -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep 2
    schtasks /run /tn "CaddyWebServer" 2>&1 | ForEach-Object {{ Write-Host "SCH: $_" }}
    Start-Sleep 8
    $p2 = Get-Process caddy -ErrorAction SilentlyContinue
    if ($p2) {{ Write-Host "Caddy PID=$($p2.Id) Mem=$(($p2.WorkingSet64)/1MB)MB" }} else {{ Write-Host "Caddy未启动" }}
    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {{ $_.LocalPort -in @(80,443) }} | Format-Table LocalAddress,LocalPort,OwningProcess

    Write-Host "=== 测试大文件 ==="
    try {{
        $r3 = Invoke-WebRequest -Uri 'http://15min.globalreviewops.xyz/connected_roads.geojson' -TimeoutSec 15 -UseBasicParsing
        Write-Host "roads OK Len=$($r3.Content.Length)"
    }} catch {{
        Write-Host "roads ERR: $($_.Exception.Message)"
    }}
}}
Remove-PSSession $s
"""],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
)
for line in r.stdout.split("\n"):
    if line.strip(): print(line)
