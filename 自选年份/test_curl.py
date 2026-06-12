#!/usr/bin/env python3
import subprocess, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOST = "64.90.0.78"

# Use curl to test
r = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"""
curl.exe -v --max-time 15 http://{HOST}/connected_roads.geojson 2>&1 | Select-Object -First 50
"""],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
)
print("CURL STDOUT:", r.stdout[:2000])
print("CURL STDERR:", r.stderr[:1000])
print("RC:", r.returncode)
