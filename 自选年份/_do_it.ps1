$ErrorActionPreference = "Stop"

# Part A: Connect and upload zip
Write-Host "=== Part A: Upload & Deploy ===" -ForegroundColor Cyan
$server = "64.90.0.78"
$port = 5985
$user = "Administrator"
$pass = "asR84SiRzqhbDvZF"

$secPass = ConvertTo-SecureString $pass -AsPlainText -Force
$creds = New-Object System.Management.Automation.PSCredential($user, $secPass)
Write-Host "Connecting to $server..."
$session = New-PSSession -ComputerName $server -Port $port -Credential $creds
Write-Host "Connected. Session ID: $($session.Id)" -ForegroundColor Green

Write-Host "`n[1] Copy zip..."
$localZip = "E:\xicha gis 智能定位\自选年份\deploy_package.zip"
Copy-Item -Path $localZip -Destination "C:\Users\Administrator\Desktop\dp.zip" -ToSession $session -Force
Write-Host "[1] OK" -ForegroundColor Green

Write-Host "`n[2] Stop nginx..."
Invoke-Command -Session $session -ScriptBlock {
    Stop-Service nginx -Force -ErrorAction SilentlyContinue
    Get-Process nginx -ErrorAction SilentlyContinue | Stop-Process -Force
    Write-Host "nginx stopped"
}

Write-Host "`n[3] Extract files..."
Invoke-Command -Session $session -ScriptBlock {
    param($rp)
    if (Test-Path $rp) { Remove-Item $rp -Recurse -Force }
    New-Item -ItemType Directory -Path $rp -Force | Out-Null
    Expand-Archive -Path "C:\Users\Administrator\Desktop\dp.zip" -DestinationPath $rp -Force
    Write-Host "Files in $rp:"
    Get-ChildItem $rp | Select-Object Name | Format-Table
} -ArgumentList "C:\www\15min"

Write-Host "`n[4] Write nginx.conf..."
Invoke-Command -Session $session -ScriptBlock {
    param($rp)
    $nd = "C:\nginx\conf"
    if (-not (Test-Path $nd)) { New-Item -ItemType Directory -Path $nd -Force | Out-Null }
    $b = [Environment]::NewLine
    $c = "worker_processes 1;$b"
    $c += "events { worker_connections 1024; }" + $b
    $c += "http {" + $b
    $c += "    include       mime.types;" + $b
    $c += "    default_type  application/octet-stream;" + $b
    $c += "    sendfile        on;" + $b
    $c += "    keepalive_timeout  65;" + $b
    $c += "    server {" + $b
    $c += "        listen       80;" + $b
    $c += "        server_name  localhost;" + $b
    $c += "        client_max_body_size 100M;" + $b
    $c += "        location / {" + $b
    $c += "            root   `"$rp`";" + $b
    $c += "            index  index.html index.htm;" + $b
    $c += "            try_files `$uri `$uri/ /index.html;" + $b
    $c += "        }" + $b
    $c += "        location /api/ {" + $b
    $c += "            proxy_pass http://127.0.0.1:5000/;" + $b
    $c += "            proxy_set_header Host `$host;" + $b
    $c += "            proxy_set_header X-Real-IP `$remote_addr;" + $b
    $c += "        }" + $b
    $c += "    }" + $b
    $c += "}" + $b
    [IO.File]::WriteAllText("$nd\nginx.conf", $c)
    Write-Host "nginx.conf written"
} -ArgumentList "C:\www\15min"

Write-Host "`n[5] Start nginx..."
Invoke-Command -Session $session -ScriptBlock {
    Start-Process C:\nginx\nginx.exe -WindowStyle Hidden -ErrorAction SilentlyContinue
    Start-Sleep 3
    $p = Get-Process nginx -ErrorAction SilentlyContinue
    if ($p) { Write-Host "nginx running, PID: $($p.Id)" }
    else { Write-Host "WARNING: nginx not running" }
}

Write-Host "`n[6] Cleanup..."
Invoke-Command -Session $session -ScriptBlock {
    Remove-Item "C:\Users\Administrator\Desktop\dp.zip" -Force -ErrorAction SilentlyContinue
    Write-Host "Cleanup done"
}

Remove-PSSession $session
Write-Host "`n=== ALL DONE ===" -ForegroundColor Green
Write-Host "Visit: http://64.90.0.78" -ForegroundColor Cyan
