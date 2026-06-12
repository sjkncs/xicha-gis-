import subprocess
import sys
import os
import base64
import socket
import http.client

ZIP_PATH = r"E:\xicha gis 智能定位\自选年份\deploy_package.zip"
REMOTE_HOST = "64.90.0.78"
REMOTE_USER = "Administrator"
REMOTE_PASS = "asR84SiRzqhbDvZF"

def run_powershell(script):
    result = subprocess.run(
        ["powershell", "-Command", script],
        capture_output=True, text=True
    )
    return result.stdout + result.stderr

print("=== Step 1: Encode zip to base64 ===")
with open(ZIP_PATH, "rb") as f:
    data = f.read()
print(f"Zip size: {len(data):,} bytes")

b64 = base64.b64encode(data).decode("ascii")
chunk_size = 50000
chunks = [b64[i:i+chunk_size] for i in range(0, len(b64), chunk_size)]
print(f"Base64: {len(b64):,} chars, {len(chunks)} chunks")

# Write base64 to temp file on C drive
tmp_b64 = r"C:\temp_dp64.txt"
with open(tmp_b64, "w") as f:
    f.write(b64)
print(f"Base64 saved to {tmp_b64}")

print("\n=== Step 2: Test WinRM connection ===")
result = run_powershell(
    f"$pass = ConvertTo-SecureString '{REMOTE_PASS}' -AsPlainText -Force; "
    f"$creds = New-Object PSCredential('{REMOTE_USER}', $pass); "
    f"$s = New-PSSession -ComputerName {REMOTE_HOST} -Port 5985 -Credential $creds; "
    f"Write-Host 'SESSION_OK'; Remove-PSSession $s"
)
print(result.strip())
if "SESSION_OK" not in result:
    print("CONNECTION FAILED")
    sys.exit(1)
print("Connection OK")

print("\n=== Step 3: Upload base64 file via WinRM ===")
result = run_powershell(
    f"$pass = ConvertTo-SecureString '{REMOTE_PASS}' -AsPlainText -Force; "
    f"$creds = New-Object PSCredential('{REMOTE_USER}', $pass); "
    f"$s = New-PSSession -ComputerName {REMOTE_HOST} -Port 5985 -Credential $creds; "
    f"Copy-Item -Path 'C:\\temp_dp64.txt' -Destination 'C:\\Users\\Administrator\\dp64.txt' -ToSession $s -Force; "
    f"Write-Host 'UPLOAD_OK'; Remove-PSSession $s"
)
print(result.strip())
if "UPLOAD_OK" not in result:
    print("UPLOAD FAILED")
    sys.exit(1)
print("Upload OK")

print("\n=== Step 4: Decode base64 on remote ===")
result = run_powershell(
    f"$pass = ConvertTo-SecureString '{REMOTE_PASS}' -AsPlainText -Force; "
    f"$creds = New-Object PSCredential('{REMOTE_USER}', $pass); "
    f"$s = New-PSSession -ComputerName {REMOTE_HOST} -Port 5985 -Credential $creds; "
    f"Invoke-Command -Session $s -ScriptBlock {{"
    f"$b64 = Get-Content 'C:\\Users\\Administrator\\dp64.txt' -Raw; "
    f"$bytes = [Convert]::FromBase64String($b64); "
    f"[IO.File]::WriteAllBytes('C:\\Users\\Administrator\\Desktop\\dp.zip', $bytes); "
    f"$sz = (Get-Item 'C:\\Users\\Administrator\\Desktop\\dp.zip').Length; "
    f"Write-Host \"DECODE_OK SIZE=$sz\"; "
    f"Remove-Item 'C:\\Users\\Administrator\\dp64.txt' -Force; "
    f"}}; Remove-PSSession $s"
)
print(result.strip())
if "DECODE_OK" not in result:
    print("DECODE FAILED")
    sys.exit(1)
print("Decode OK")

print("\n=== Step 5: Stop nginx ===")
result = run_powershell(
    f"$pass = ConvertTo-SecureString '{REMOTE_PASS}' -AsPlainText -Force; "
    f"$creds = New-Object PSCredential('{REMOTE_USER}', $pass); "
    f"$s = New-PSSession -ComputerName {REMOTE_HOST} -Port 5985 -Credential $creds; "
    f"Invoke-Command -Session $s -ScriptBlock {{"
    f"Stop-Service nginx -Force -ErrorAction SilentlyContinue; "
    f"Get-Process nginx -ErrorAction SilentlyContinue | Stop-Process -Force; "
    f"Write-Host 'NGINX_STOPPED'"
    f"}}; Remove-PSSession $s"
)
print(result.strip())

print("\n=== Step 6: Extract files ===")
result = run_powershell(
    f"$pass = ConvertTo-SecureString '{REMOTE_PASS}' -AsPlainText -Force; "
    f"$creds = New-Object PSCredential('{REMOTE_USER}', $pass); "
    f"$s = New-PSSession -ComputerName {REMOTE_HOST} -Port 5985 -Credential $creds; "
    f"Invoke-Command -Session $s -ScriptBlock {{"
    f"$rp = 'C:\\www\\15min'; "
    f"if (Test-Path $rp) {{ Remove-Item $rp -Recurse -Force }}; "
    f"New-Item -ItemType Directory -Path $rp -Force | Out-Null; "
    f"Expand-Archive -Path 'C:\\Users\\Administrator\\Desktop\\dp.zip' -DestinationPath $rp -Force; "
    f"$files = Get-ChildItem $rp -Name; "
    f"Write-Host 'EXTRACT_OK FILES=' $files.Count; "
    f"foreach ($fn in $files) {{ Write-Host \"  $fn\" }}"
    f"}}; Remove-PSSession $s"
)
print(result.strip())
if "EXTRACT_OK" not in result:
    print("EXTRACT FAILED")
    sys.exit(1)

print("\n=== Step 7: Write nginx.conf ===")
result = run_powershell(
    f"$pass = ConvertTo-SecureString '{REMOTE_PASS}' -AsPlainText -Force; "
    f"$creds = New-Object PSCredential('{REMOTE_USER}', $pass); "
    f"$s = New-PSSession -ComputerName {REMOTE_HOST} -Port 5985 -Credential $creds; "
    f"Invoke-Command -Session $s -ScriptBlock {{"
    f"$rp = 'C:\\www\\15min'; "
    f"$nd = 'C:\\nginx\\conf'; "
    f"if (-not (Test-Path $nd)) {{ New-Item -ItemType Directory -Path $nd -Force | Out-Null }}; "
    f"$nl = [Environment]::NewLine; "
    f"$conf = 'worker_processes 1;' + $nl; "
    f"$conf += 'events {{ worker_connections 1024; }}' + $nl; "
    f"$conf += 'http {{' + $nl; "
    f"$conf += '    include       mime.types;' + $nl; "
    f"$conf += '    default_type  application/octet-stream;' + $nl; "
    f"$conf += '    sendfile        on;' + $nl; "
    f"$conf += '    keepalive_timeout  65;' + $nl; "
    f"$conf += '    server {{' + $nl; "
    f"$conf += '        listen       80;' + $nl; "
    f"$conf += '        server_name  localhost;' + $nl; "
    f"$conf += '        client_max_body_size 100M;' + $nl; "
    f"$conf += '        location / {{' + $nl; "
    f"$conf += '            root   ' + '\"' + '$rp' + '\";' + $nl; "
    f"$conf += '            index  index.html index.htm;' + $nl; "
    f"$conf += '            try_files ' + '$uri ' + '$uri/ /index.html;' + $nl; "
    f"$conf += '        }}' + $nl; "
    f"$conf += '        location /api/ {{' + $nl; "
    f"$conf += '            proxy_pass http://127.0.0.1:5000/;' + $nl; "
    f"$conf += '            proxy_set_header Host ' + '$host;' + $nl; "
    f"$conf += '            proxy_set_header X-Real-IP ' + '$remote_addr;' + $nl; "
    f"$conf += '        }}' + $nl; "
    f"$conf += '    }}' + $nl; "
    f"$conf += '}}' + $nl; "
    f"[IO.File]::WriteAllText(\"$nd\\nginx.conf\", $conf); "
    f"Write-Host 'NGINX_CONF_OK'"
    f"}}; Remove-PSSession $s"
)
print(result.strip())
if "NGINX_CONF_OK" not in result:
    print("NGINX CONF FAILED")
    sys.exit(1)

print("\n=== Step 8: Start nginx ===")
result = run_powershell(
    f"$pass = ConvertTo-SecureString '{REMOTE_PASS}' -AsPlainText -Force; "
    f"$creds = New-Object PSCredential('{REMOTE_USER}', $pass); "
    f"$s = New-PSSession -ComputerName {REMOTE_HOST} -Port 5985 -Credential $creds; "
    f"Invoke-Command -Session $s -ScriptBlock {{"
    f"Start-Process 'C:\\nginx\\nginx.exe' -WindowStyle Hidden -ErrorAction SilentlyContinue; "
    f"Start-Sleep 3; "
    f"$p = Get-Process nginx -ErrorAction SilentlyContinue; "
    f"if ($p) {{ Write-Host 'NGINX_RUNNING PID=' $p.Id }} else {{ Write-Host 'NGINX_WARNING' }}"
    f"}}; Remove-PSSession $s"
)
print(result.strip())

print("\n=== Step 9: Cleanup ===")
result = run_powershell(
    f"$pass = ConvertTo-SecureString '{REMOTE_PASS}' -AsPlainText -Force; "
    f"$creds = New-Object PSCredential('{REMOTE_USER}', $pass); "
    f"$s = New-PSSession -ComputerName {REMOTE_HOST} -Port 5985 -Credential $creds; "
    f"Invoke-Command -Session $s -ScriptBlock {{"
    f"Remove-Item 'C:\\Users\\Administrator\\Desktop\\dp.zip' -Force -ErrorAction SilentlyContinue; "
    f"Write-Host 'CLEANUP_OK'"
    f"}}; Remove-PSSession $s"
)
print(result.strip())

# Cleanup local temp
try:
    os.remove(tmp_b64)
    print(f"Local temp file removed")
except:
    pass

print("\n" + "=" * 50)
print("DEPLOYMENT COMPLETE!")
print("Visit: http://64.90.0.78")
print("=" * 50)
