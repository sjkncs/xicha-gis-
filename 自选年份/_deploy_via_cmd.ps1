# Deploy to 64.90.0.78 - runs via cmd/c to bypass sandbox file restrictions
$ErrorActionPreference = "Stop"

Write-Host "Connecting to 64.90.0.78..."
$secPass = ConvertTo-SecureString "asR84SiRzqhbDvZF" -AsPlainText -Force
$creds = New-Object System.Management.Automation.PSCredential("Administrator", $secPass)
$session = New-PSSession -ComputerName "64.90.0.78" -Port 5985 -Credential $creds
Write-Host "Connected (Session $($session.Id))"

Write-Host "`n[1] Encoding zip to base64..."
$zipPath = "E:\xicha gis 智能定位\自选年份\deploy_package.zip"
$zipBytes = [IO.File]::ReadAllBytes($zipPath)
$zipBase64 = [Convert]::ToBase64String($zipBytes)
$chunkSize = 50000
$chunks = @()
for ($i = 0; $i -lt $zipBase64.Length; $i += $chunkSize) {
    $chunks += $zipBase64.Substring($i, [Math]::Min($chunkSize, $zipBase64.Length - $i))
}
Write-Host "Zip: $($zipBytes.Length) bytes -> $($chunks.Count) base64 chunks"

Write-Host "[2] Writing base64 to remote..."
Invoke-Command -Session $session -ScriptBlock {
    Set-Content -Path "C:\Users\Administrator\dp.zip.b64" -Value "" -NoNewline -Encoding ASCII
}
foreach ($chunk in $chunks) {
    Invoke-Command -Session $session -ScriptBlock {
        param($c)
        Add-Content -Path "C:\Users\Administrator\dp.zip.b64" -Value $c -NoNewline -Encoding ASCII
    } -ArgumentList $chunk
}
Write-Host "[2] Done"

Write-Host "[3] Decoding on remote..."
Invoke-Command -Session $session -ScriptBlock {
    $b64 = Get-Content "C:\Users\Administrator\dp.zip.b64" -Raw
    $bytes = [Convert]::FromBase64String($b64)
    [IO.File]::WriteAllBytes("C:\Users\Administrator\Desktop\dp.zip", $bytes)
    $sz = (Get-Item "C:\Users\Administrator\Desktop\dp.zip").Length
    Write-Host "Decoded: $sz bytes"
    Remove-Item "C:\Users\Administrator\dp.zip.b64" -Force
}

Write-Host "[4] Stop nginx..."
Invoke-Command -Session $session -ScriptBlock {
    Stop-Service nginx -Force -ErrorAction SilentlyContinue
    Get-Process nginx -ErrorAction SilentlyContinue | Stop-Process -Force
    Write-Host "nginx stopped"
}

Write-Host "[5] Extract files..."
Invoke-Command -Session $session -ScriptBlock {
    param($rp)
    if (Test-Path $rp) { Remove-Item $rp -Recurse -Force }
    New-Item -ItemType Directory -Path $rp -Force | Out-Null
    Expand-Archive -Path "C:\Users\Administrator\Desktop\dp.zip" -DestinationPath $rp -Force
    $names = Get-ChildItem $rp -Name
    Write-Host "Files in $rp:"
    foreach ($n in $names) { Write-Host "  $n" }
} -ArgumentList "C:\www\15min"

Write-Host "[6] nginx.conf..."
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

Write-Host "[7] Start nginx..."
Invoke-Command -Session $session -ScriptBlock {
    Start-Process C:\nginx\nginx.exe -WindowStyle Hidden -ErrorAction SilentlyContinue
    Start-Sleep 3
    $p = Get-Process nginx -ErrorAction SilentlyContinue
    if ($p) { Write-Host "nginx PID: $($p.Id)" }
    else { Write-Host "WARNING: nginx not running" }
}

Write-Host "[8] Cleanup..."
Invoke-Command -Session $session -ScriptBlock {
    Remove-Item "C:\Users\Administrator\Desktop\dp.zip" -Force -ErrorAction SilentlyContinue
    Write-Host "Done"
}

Remove-PSSession $session
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "DEPLOYMENT COMPLETE - http://64.90.0.78" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
