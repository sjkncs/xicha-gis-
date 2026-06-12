#!/usr/bin/env python3
import subprocess

HOST = "64.90.0.78"
PORT = 5985
USER = "Administrator"
PASS = "asR84SiRzqhbDvZF"
OUT = r"C:\Users\Administrator\remote_status.txt"

cmd = f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Write-Host "=== Caddy进程 ===" > '{OUT}'
Get-Process caddy -ErrorAction SilentlyContinue | ForEach-Object {{ Add-Content '{OUT}' -Value (\"PID=\" + $_.Id + \" Path=\" + $_.Path) }}
if (! (Get-Process caddy -ErrorAction SilentlyContinue)) {{ Add-Content '{OUT}' -Value \"Caddy未运行\" }}
Add-Content '{OUT}' -Value \"=== 监听80端口 ===\"
Get-NetTCPConnection -LocalPort 80 -ErrorAction SilentlyContinue | ForEach-Object {{ Add-Content '{OUT}' -Value (\"Port80 \" + $_.LocalAddress + \":\" + $_.State + \" PID=\" + $_.OwningProcess) }}
Add-Content '{OUT}' -Value \"=== WWW目录 ===\"
Get-ChildItem 'C:\\www\\15min\\static' -ErrorAction SilentlyContinue | ForEach-Object {{ Add-Content '{OUT}' -Value (\"File=\" + $_.Name + \" SizeMB=\" + [math]::Round($_.Length/1MB,1)) }}
Remove-PSSession $s
Write-Host DONE
"""

r = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
)
print("PowerShell rc:", r.returncode)
print(r.stdout.strip())

# Read the result file
try:
    with open(r"C:\Users\Administrator\remote_status.txt", "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    for line in content.split("\n"):
        print(line)
except Exception as e:
    print("Read error:", e)
