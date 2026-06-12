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
    Write-Host "=== 文件存在检查 ==="
    $files = @('city_cesium.geojson','connected_roads.geojson','network_nodes.geojson','routing_graph.json','city_visualization_3d.html')
    foreach ($f in $files) {{
        $p = 'C:\\www\\15min\\static\\' + $f
        if (Test-Path $p) {{
            $sz = [math]::Round((Get-Item $p).Length/1MB,1)
            Write-Host "OK $f = $sz MB"
        }} else {{
            Write-Host "MISSING $f"
        }}
    }}

    Write-Host "=== HTTP 本地测试 ==="
    try {{
        $r2 = Invoke-WebRequest -Uri 'http://127.0.0.1/city_visualization_3d.html' -TimeoutSec 10 -UseBasicParsing
        Write-Host "3D HTML OK Len=$($r2.Content.Length)"
    }} catch {{
        Write-Host "3D HTML ERR: $($_.Exception.Message)"
    }}
    try {{
        $r3 = Invoke-WebRequest -Uri 'http://127.0.0.1/connected_roads.geojson' -TimeoutSec 10 -UseBasicParsing
        Write-Host "roads geojson OK Len=$($r3.Content.Length)"
    }} catch {{
        Write-Host "roads ERR: $($_.Exception.Message)"
    }}
    try {{
        $r4 = Invoke-WebRequest -Uri 'http://127.0.0.1/routing_graph.json' -TimeoutSec 10 -UseBasicParsing
        Write-Host "routing JSON OK Len=$($r4.Content.Length)"
    }} catch {{
        Write-Host "routing ERR: $($_.Exception.Message)"
    }}

    Write-Host "=== Caddy 错误日志 ==="
    Get-ChildItem 'C:\\globalreviewops\\caddy\\' -Filter '*.log' -ErrorAction SilentlyContinue | ForEach-Object {{
        Write-Host "--- $($_.Name) ---"
        Get-Content $_.FullName -Tail 20 -ErrorAction SilentlyContinue | ForEach-Object {{ Write-Host $_ }}
    }}

    Write-Host "=== Caddy stderr ==="
    if (Test-Path 'C:\\Users\\Administrator\\caddy_err.txt') {{
        Get-Content 'C:\\Users\\Administrator\\caddy_err.txt' -ErrorAction SilentlyContinue | ForEach-Object {{ Write-Host $_ }}
    }}
}}
Remove-PSSession $s
"""],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
)
for line in r.stdout.split("\n"):
    if line.strip(): print(line)
