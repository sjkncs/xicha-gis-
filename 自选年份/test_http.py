#!/usr/bin/env python3
import subprocess, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOST = "64.90.0.78"

r = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"""
Invoke-WebRequest -Uri 'http://{HOST}/city_visualization_3d.html' -TimeoutSec 15 -UseBasicParsing -MaximumRetryCount 2 | ForEach-Object {{
    Write-Host "Status=$($_.StatusCode)"
    Write-Host "Len=$($_.Content.Length)"
    Write-Host "Content-Type=$($_.Headers['Content-Type'])"
}}
Write-Host "--- Test 2: Root ---"
Invoke-WebRequest -Uri 'http://{HOST}/' -TimeoutSec 10 -UseBasicParsing | ForEach-Object {{
    Write-Host "Status=$($_.StatusCode) Len=$($_.Content.Length)"
}}
Write-Host "--- Test 3: connected_roads.geojson ---"
Invoke-WebRequest -Uri 'http://{HOST}/connected_roads.geojson' -TimeoutSec 10 -UseBasicParsing | ForEach-Object {{
    Write-Host "Status=$($_.StatusCode) Len=$($_.Content.Length)"
}}
Write-Host "DONE"
"""],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
)
for line in r.stdout.split("\n"):
    if line.strip():
        print(line)
