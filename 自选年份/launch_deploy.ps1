$ErrorActionPreference = 'Stop'
$server = '64.90.0.78'
$port = 5985
$user = 'Administrator'
$pass = 'asR84SiRzqhbDvZF'

$secPass = ConvertTo-SecureString $pass -AsPlainText -Force
$creds = New-Object System.Management.Automation.PSCredential($user, $secPass)
Write-Host "Connecting to $server`:$port..."
$session = New-PSSession -ComputerName $server -Port $port -Credential $creds
Write-Host "Session established."

# Now run the deploy steps directly in this session (not -ToSession)
Write-Host "[1] Copy zip to remote desktop..."
Copy-Item -Path 'E:\xicha gis 智能定位\自选年份\deploy_package.zip' -Destination 'C:\Users\Administrator\Desktop\dp.zip' -ToSession $session -Force
Write-Host "[1] OK"

Write-Host "[2] Stop nginx..."
Invoke-Command -Session $session -ScriptBlock {
    Stop-Service nginx -Force -ErrorAction SilentlyContinue
    Get-Process nginx -ErrorAction SilentlyContinue | Stop-Process -Force
    Write-Host 'nginx stopped'
}
Write-Host "[2] OK"

Write-Host "[3] Extract files..."
Invoke-Command -Session $session -ScriptBlock {
    param($rp)
    if (Test-Path $rp) { Remove-Item $rp -Recurse -Force }
    New-Item -ItemType Directory -Path $rp -Force | Out-Null
    Expand-Archive -Path 'C:\Users\Administrator\Desktop\dp.zip' -DestinationPath $rp -Force
    Write-Host "Extracted to: $rp"
    Get-ChildItem $rp | Select-Object Name | Format-Table
} -ArgumentList 'C:\www\15min'
Write-Host "[3] OK"

Write-Host "[4] Write nginx.conf..."
Invoke-Command -Session $session -ScriptBlock {
    param($rp)
    $nginxDir = 'C:\nginx\conf'
    if (-not (Test-Path $nginxDir)) { New-Item -ItemType Directory -Path $nginxDir -Force | Out-Null }
    $conf = 'worker_processes 1;' + [Environment]::NewLine
    $conf += 'events { worker_connections 1024; }' + [Environment]::NewLine
    $conf += 'http {' + [Environment]::NewLine
    $conf += '    include       mime.types;' + [Environment]::NewLine
    $conf += '    default_type  application/octet-stream;' + [Environment]::NewLine
    $conf += '    sendfile        on;' + [Environment]::NewLine
    $conf += '    keepalive_timeout  65;' + [Environment]::NewLine
    $conf += '    server {' + [Environment]::NewLine
    $conf += '        listen       80;' + [Environment]::NewLine
    $conf += '        server_name  localhost;' + [Environment]::NewLine
    $conf += '        client_max_body_size 100M;' + [Environment]::NewLine
    $conf += '        location / {' + [Environment]::NewLine
    $conf += '            root   "' + $rp + '";' + [Environment]::NewLine
    $conf += '            index  index.html index.htm;' + [Environment]::NewLine
    $conf += '            try_files $uri $uri/ /index.html;' + [Environment]::NewLine
    $conf += '        }' + [Environment]::NewLine
    $conf += '        location /api/ {' + [Environment]::NewLine
    $conf += '            proxy_pass http://127.0.0.1:5000/;' + [Environment]::NewLine
    $conf += '            proxy_set_header Host $host;' + [Environment]::NewLine
    $conf += '            proxy_set_header X-Real-IP $remote_addr;' + [Environment]::NewLine
    $conf += '        }' + [Environment]::NewLine
    $conf += '    }' + [Environment]::NewLine
    $conf += '}' + [Environment]::NewLine
    [IO.File]::WriteAllText("$nginxDir\nginx.conf", $conf)
    Write-Host "nginx.conf written"
} -ArgumentList 'C:\www\15min'
Write-Host "[4] OK"

Write-Host "[5] Start nginx..."
Invoke-Command -Session $session -ScriptBlock {
    Start-Process C:\nginx\nginx.exe -WindowStyle Hidden -ErrorAction SilentlyContinue
    Start-Sleep 3
    $p = Get-Process nginx -ErrorAction SilentlyContinue
    if ($p) { Write-Host "nginx running PID: $($p.Id)" }
    else { Write-Host "WARNING: nginx not running" }
}
Write-Host "[5] OK"

Write-Host "[6] Cleanup..."
Invoke-Command -Session $session -ScriptBlock {
    Remove-Item 'C:\Users\Administrator\Desktop\dp.zip' -Force -ErrorAction SilentlyContinue
    Write-Host "Cleanup done"
}
Write-Host "[6] OK"

Remove-PSSession $session
Write-Host ""
Write-Host "=== ALL DONE ===" -ForegroundColor Green
Write-Host "Visit: http://64.90.0.78" -ForegroundColor Cyan
