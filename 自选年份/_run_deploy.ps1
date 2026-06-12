$ErrorActionPreference = "Stop"
$server = "64.90.0.78"
$port = 5985
$user = "Administrator"
$pass = "asR84SiRzqhbDvZF"

$secPass = ConvertTo-SecureString $pass -AsPlainText -Force
$creds = New-Object System.Management.Automation.PSCredential($user, $secPass)
Write-Host "Connecting..."
$session = New-PSSession -ComputerName $server -Port $port -Credential $creds
Write-Host "Connected. Session ID: $($session.Id)"

Write-Host "[1] Copy zip..."
Copy-Item -Path "E:\xicha gis 智能定位\自选年份\deploy_package.zip" -Destination "C:\Users\Administrator\Desktop\dp.zip" -ToSession $session -Force
Write-Host "[1] OK"

Write-Host "[2] Stop nginx..."
Invoke-Command -Session $session -ScriptBlock {
    Stop-Service nginx -Force -ErrorAction SilentlyContinue
    Get-Process nginx -ErrorAction SilentlyContinue | Stop-Process -Force
    Write-Host "nginx stopped"
}

Write-Host "[3] Extract..."
Invoke-Command -Session $session -ScriptBlock {
    param($rp)
    if (Test-Path $rp) { Remove-Item $rp -Recurse -Force }
    New-Item -ItemType Directory -Path $rp -Force | Out-Null
    Expand-Archive -Path "C:\Users\Administrator\Desktop\dp.zip" -DestinationPath $rp -Force
    Get-ChildItem $rp | Select-Object Name | Format-Table
} -ArgumentList "C:\www\15min"

Write-Host "[4] nginx.conf..."
Invoke-Command -Session $session -ScriptBlock {
    param($rp)
    $nginxDir = "C:\nginx\conf"
    if (-not (Test-Path $nginxDir)) { New-Item -ItemType Directory -Path $nginxDir -Force | Out-Null }
    $b = [Environment]::NewLine
    $c = "worker_processes 1;$b"
    $c += "events { worker_connections 1024; }$b"
    $c += "http {$b"
    $c += "    include       mime.types;$b"
    $c += "    default_type  application/octet-stream;$b"
    $c += "    sendfile        on;$b"
    $c += "    keepalive_timeout  65;$b"
    $c += "    server {$b"
    $c += "        listen       80;$b"
    $c += "        server_name  localhost;$b"
    $c += "        client_max_body_size 100M;$b"
    $c += "        location / {$b"
    $c += "            root   `"$rp`";$b"
    $c += "            index  index.html index.htm;$b"
    $c += "            try_files `$uri `$uri/ /index.html;$b"
    $c += "        }$b"
    $c += "        location /api/ {$b"
    $c += "            proxy_pass http://127.0.0.1:5000/;$b"
    $c += "            proxy_set_header Host `$host;$b"
    $c += "            proxy_set_header X-Real-IP `$remote_addr;$b"
    $c += "        }$b"
    $c += "    }$b"
    $c += "}$b"
    [IO.File]::WriteAllText("$nginxDir\nginx.conf", $c)
    Write-Host "Written"
} -ArgumentList "C:\www\15min"

Write-Host "[5] Start nginx..."
Invoke-Command -Session $session -ScriptBlock {
    Start-Process C:\nginx\nginx.exe -WindowStyle Hidden -ErrorAction SilentlyContinue
    Start-Sleep 3
    $p = Get-Process nginx -ErrorAction SilentlyContinue
    if ($p) { Write-Host "nginx PID: $($p.Id)" }
    else { Write-Host "WARNING: nginx not running" }
}

Write-Host "[6] Cleanup..."
Invoke-Command -Session $session -ScriptBlock {
    Remove-Item "C:\Users\Administrator\Desktop\dp.zip" -Force -ErrorAction SilentlyContinue
}

Remove-PSSession $session
Write-Host "ALL DONE - http://64.90.0.78"
