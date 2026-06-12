$ErrorActionPreference = "Stop"
$ErrorActionPreference = "Continue"

Write-Host "=== Encoding zip locally ==="
$zipPath = "E:\xicha gis 智能定位\自选年份\deploy_package.zip"
$tmpB64 = "$env:TEMP\dp64.txt"
$zipBytes = [IO.File]::ReadAllBytes($zipPath)
$zipBase64 = [Convert]::ToBase64String($zipBytes)
[IO.File]::WriteAllText($tmpB64, $zipBase64)
Write-Host "Base64 written to $tmpB64 ($zipBase64.Length chars)"

Write-Host "Connecting to 64.90.0.78..."
$secPass = ConvertTo-SecureString "asR84SiRzqhbDvZF" -AsPlainText -Force
$creds = New-Object System.Management.Automation.PSCredential("Administrator", $secPass)
$session = New-PSSession -ComputerName "64.90.0.78" -Port 5985 -Credential $creds
Write-Host "Connected"

Write-Host "Copying base64 to remote..."
Copy-Item -Path $tmpB64 -Destination "C:\Users\Administrator\dp64.txt" -ToSession $session -Force
Write-Host "Base64 copied to remote"

Write-Host "Decoding on remote..."
Invoke-Command -Session $session -ScriptBlock {
    $b64 = Get-Content "C:\Users\Administrator\dp64.txt" -Raw
    $bytes = [Convert]::FromBase64String($b64)
    [IO.File]::WriteAllBytes("C:\Users\Administrator\Desktop\dp.zip", $bytes)
    $sz = (Get-Item "C:\Users\Administrator\Desktop\dp.zip").Length
    Write-Host "Decoded $sz bytes"
    Remove-Item "C:\Users\Administrator\dp64.txt" -Force
}

Write-Host "Stopping nginx..."
Invoke-Command -Session $session -ScriptBlock {
    Stop-Service nginx -Force -ErrorAction SilentlyContinue
    Get-Process nginx -ErrorAction SilentlyContinue | Stop-Process -Force
    Write-Host "nginx stopped"
}

Write-Host "Extracting..."
Invoke-Command -Session $session -ScriptBlock {
    $rp = "C:\www\15min"
    if (Test-Path $rp) { Remove-Item $rp -Recurse -Force }
    New-Item -ItemType Directory -Path $rp -Force | Out-Null
    Expand-Archive -Path "C:\Users\Administrator\Desktop\dp.zip" -DestinationPath $rp -Force
    $names = Get-ChildItem $rp -Name
    Write-Host "Files--"
    foreach ($n in $names) { Write-Host " $n" }
}

Write-Host "Writing nginx.conf..."
Invoke-Command -Session $session -ScriptBlock {
    $rp = "C:\www\15min"
    $nd = "C:\nginx\conf"
    if (-not (Test-Path $nd)) { New-Item -ItemType Directory -Path $nd -Force | Out-Null }
    $nl = [Environment]::NewLine
    $conf = "worker_processes 1;$nl"
    $conf += "events { worker_connections 1024; }$nl"
    $conf += "http {$nl"
    $conf += "    include       mime.types;$nl"
    $conf += "    default_type  application/octet-stream;$nl"
    $conf += "    sendfile        on;$nl"
    $conf += "    keepalive_timeout  65;$nl"
    $conf += "    server {$nl"
    $conf += "        listen       80;$nl"
    $conf += "        server_name  localhost;$nl"
    $conf += "        client_max_body_size 100M;$nl"
    $conf += "        location / {$nl"
    $conf += "            root   `"$rp`";$nl"
    $conf += "            index  index.html index.htm;$nl"
    $conf += "            try_files " + '$' + "uri " + '$' + "uri/ /index.html;$nl"
    $conf += "        }$nl"
    $conf += "        location /api/ {$nl"
    $conf += "            proxy_pass http://127.0.0.1:5000/;$nl"
    $conf += "            proxy_set_header Host " + '$' + "host;$nl"
    $conf += "            proxy_set_header X-Real-IP " + '$' + "remote_addr;$nl"
    $conf += "        }$nl"
    $conf += "    }$nl"
    $conf += "}$nl"
    [IO.File]::WriteAllText("$nd\nginx.conf", $conf)
    Write-Host "nginx.conf written"
}

Write-Host "Starting nginx..."
Invoke-Command -Session $session -ScriptBlock {
    Start-Process C:\nginx\nginx.exe -WindowStyle Hidden -ErrorAction SilentlyContinue
    Start-Sleep 3
    $p = Get-Process nginx -ErrorAction SilentlyContinue
    if ($p) { Write-Host "nginx PID $($p.Id)" }
    else { Write-Host "WARNING: nginx not found" }
}

Write-Host "Cleanup..."
Invoke-Command -Session $session -ScriptBlock {
    Remove-Item "C:\Users\Administrator\Desktop\dp.zip" -Force -ErrorAction SilentlyContinue
    Write-Host "Done"
}

Remove-PSSession $session
Remove-Item $tmpB64 -Force -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "========================================"
Write-Host "DEPLOYMENT COMPLETE - http://64.90.0.78"
Write-Host "========================================"
