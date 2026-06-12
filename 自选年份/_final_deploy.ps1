# This script writes and executes everything via remote command
$ErrorActionPreference = "Stop"

Write-Host "Connecting to 64.90.0.78..."
$secPass = ConvertTo-SecureString "asR84SiRzqhbDvZF" -AsPlainText -Force
$creds = New-Object System.Management.Automation.PSCredential("Administrator", $secPass)
$session = New-PSSession -ComputerName "64.90.0.78" -Port 5985 -Credential $creds
Write-Host "Connected (Session $($session.Id))"

# Step 1: Upload zip via certutil base64
Write-Host "`n[1] Encoding zip to base64..."
$zipBytes = [IO.File]::ReadAllBytes("E:\xicha gis 智能定位\自选年份\deploy_package.zip")
$zipBase64 = [Convert]::ToBase64String($zipBytes)
$chunkSize = 50000
$chunks = @()
for ($i = 0; $i -lt $zipBase64.Length; $i += $chunkSize) {
    $chunks += $zipBase64.Substring($i, [Math]::Min($chunkSize, $zipBase64.Length - $i))
}
Write-Host "Zip encoded: $($zipBytes.Length) bytes -> $($zipBase64.Length) base64 chars, $($chunks.Count) chunks"

# Write chunks to remote temp
Write-Host "[2] Sending base64 chunks to remote..."
Invoke-Command -Session $session -ScriptBlock {
    Set-Content -Path "C:\Users\Administrator\dp.zip.b64" -Value "" -NoNewline
} -ArgumentList $null
foreach ($chunk in $chunks) {
    Invoke-Command -Session $session -ScriptBlock {
        param($c)
        Add-Content -Path "C:\Users\Administrator\dp.zip.b64" -Value $c -NoNewline
    } -ArgumentList $chunk
}
Write-Host "[2] All chunks sent"

# Step 3: Decode on remote
Write-Host "[3] Decoding base64 on remote..."
Invoke-Command -Session $session -ScriptBlock {
    Write-Host "Decoding..."
    $bytes = [Convert]::FromBase64String((Get-Content "C:\Users\Administrator\dp.zip.b64" -Raw))
    [IO.File]::WriteAllBytes("C:\Users\Administrator\Desktop\dp.zip", $bytes)
    $size = (Get-Item "C:\Users\Administrator\Desktop\dp.zip").Length
    Write-Host "Decoded: $size bytes"
    Remove-Item "C:\Users\Administrator\dp.zip.b64" -Force
    Write-Host "b64 file removed"
}

# Step 4: Stop nginx
Write-Host "[4] Stopping nginx..."
Invoke-Command -Session $session -ScriptBlock {
    Stop-Service nginx -Force -ErrorAction SilentlyContinue
    Get-Process nginx -ErrorAction SilentlyContinue | Stop-Process -Force
    Write-Host "nginx stopped"
}

# Step 5: Extract
Write-Host "[5] Extracting files..."
Invoke-Command -Session $session -ScriptBlock {
    param($rp)
    if (Test-Path $rp) { Remove-Item $rp -Recurse -Force }
    New-Item -ItemType Directory -Path $rp -Force | Out-Null
    Expand-Archive -Path "C:\Users\Administrator\Desktop\dp.zip" -DestinationPath $rp -Force
    $files = Get-ChildItem $rp -Name
    Write-Host "Extracted files:"
    foreach ($f in $files) { Write-Host "  $f" }
} -ArgumentList "C:\www\15min"

# Step 6: Write nginx.conf
Write-Host "[6] Writing nginx.conf..."
Invoke-Command -Session $session -ScriptBlock {
    param($rp)
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
    Write-Host "nginx.conf written ($($conf.Length) chars)"
} -ArgumentList "C:\www\15min"

# Step 7: Start nginx
Write-Host "[7] Starting nginx..."
Invoke-Command -Session $session -ScriptBlock {
    Start-Process C:\nginx\nginx.exe -WindowStyle Hidden -ErrorAction SilentlyContinue
    Start-Sleep 3
    $p = Get-Process nginx -ErrorAction SilentlyContinue
    if ($p) { Write-Host "nginx running (PID: $($p.Id))" }
    else { Write-Host "WARNING: nginx process not found" }
}

# Step 8: Cleanup
Write-Host "[8] Cleanup..."
Invoke-Command -Session $session -ScriptBlock {
    Remove-Item "C:\Users\Administrator\Desktop\dp.zip" -Force -ErrorAction SilentlyContinue
    Write-Host "dp.zip removed"
}

Remove-PSSession $session
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host "Visit: http://64.90.0.78" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Green
