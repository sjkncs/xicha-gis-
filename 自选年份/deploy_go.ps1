$ErrorActionPreference = "Stop"
$server = "64.90.0.78"
$port = 5985
$user = "Administrator"
$pass = "asR84SiRzqhbDvZF"
$remotePath = "C:\www\15min"
$localZip = "E:\xicha gis 智能定位\自选年份\deploy_package.zip"

$secPass = ConvertTo-SecureString $pass -AsPlainText -Force
$creds = New-Object System.Management.Automation.PSCredential($user, $secPass)

Write-Host "[1/7] WinRM session to $server`:$port..." -ForegroundColor Cyan
try {
    $session = New-PSSession -ComputerName $server -Port $port -Credential $creds
    Write-Host "[OK] Session connected" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] $_" -ForegroundColor Red; exit 1
}

Write-Host "[2/7] Copy zip to remote..." -ForegroundColor Cyan
Copy-Item $localZip -Destination "C:\Users\Administrator\Desktop\dp.zip" -ToSession $session -Force
Write-Host "[OK] Copied ($(int) MB)" -ForegroundColor Green

Write-Host "[3/7] Stop nginx..." -ForegroundColor Cyan
Invoke-Command -Session $session -ScriptBlock {
    $ErrorActionPreference = "SilentlyContinue"
    Stop-Service -Name nginx -Force
    Get-Process nginx | Stop-Process -Force
    Write-Host "nginx stopped"
}

Write-Host "[4/7] Extract files to $remotePath..." -ForegroundColor Cyan
Invoke-Command -Session $session -ScriptBlock {
    param($rp)
    $ErrorActionPreference = "Stop"
    if (Test-Path $rp) { Remove-Item $rp -Recurse -Force }
    New-Item -ItemType Directory -Path $rp -Force | Out-Null
    Expand-Archive -Path "C:\Users\Administrator\Desktop\dp.zip" -DestinationPath $rp -Force
    Write-Host "Extracted:"
    Get-ChildItem $rp | Select-Object Name | Format-Table
} -ArgumentList $remotePath

Write-Host "[5/7] Write nginx.conf..." -ForegroundColor Cyan
Invoke-Command -Session $session -ScriptBlock {
    param($rp)
    $ErrorActionPreference = "Stop"
    $conf = @"
worker_processes 1;
events { worker_connections 1024; }
http {
    include       mime.types;
    default_type  application/octet-stream;
    sendfile        on;
    keepalive_timeout  65;
    server {
        listen       80;
        server_name  localhost;
        client_max_body_size 100M;
        location / {
            root   "$rp";
            index  index.html index.htm;
            try_files `$uri `$uri/ /index.html;
        }
        location /api/ {
            proxy_pass http://127.0.0.1:5000/;
            proxy_set_header Host `$host;
            proxy_set_header X-Real-IP `$remote_addr;
        }
    }
}
"@
    $conf | Out-File -FilePath "C:\nginx\conf\nginx.conf" -Encoding UTF8 -Force
    Write-Host "nginx.conf written"
} -ArgumentList $remotePath

Write-Host "[6/7] Start nginx..." -ForegroundColor Cyan
Invoke-Command -Session $session -ScriptBlock {
    $ErrorActionPreference = "SilentlyContinue"
    Start-Process C:\nginx\nginx.exe -WindowStyle Hidden
    Start-Sleep -Seconds 3
    $p = Get-Process nginx -ErrorAction SilentlyContinue
    if ($p) { Write-Host "nginx running (PID: $($p.Id))" }
    else { Write-Host "WARNING: nginx not running" }
}

Write-Host "[7/7] Cleanup..." -ForegroundColor Cyan
Invoke-Command -Session $session -ScriptBlock {
    Remove-Item "C:\Users\Administrator\Desktop\dp.zip" -Force -ErrorAction SilentlyContinue
}

Remove-PSSession $session
Write-Host "`n=== ALL DONE ===" -ForegroundColor Green
Write-Host "Visit: http://$server" -ForegroundColor Cyan
