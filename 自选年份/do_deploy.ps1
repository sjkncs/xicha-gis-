$ErrorActionPreference = 'Stop'
$localZip = 'E:\xicha gis 智能定位\自选年份\deploy_package.zip'
$remotePath = 'C:\www\15min'

Write-Host '[1] Copy zip to remote desktop...'
$session | Copy-Item -Path $localZip -Destination 'C:\Users\Administrator\Desktop\dp.zip' -Force
Write-Host '[1] OK'

Write-Host '[2] Stop nginx...'
Invoke-Command -Session $session -ScriptBlock {
    Stop-Service nginx -Force -ErrorAction SilentlyContinue
    Get-Process nginx -ErrorAction SilentlyContinue | Stop-Process -Force
    Write-Host 'nginx stopped'
}
Write-Host '[2] OK'

Write-Host '[3] Extract files...'
Invoke-Command -Session $session -ScriptBlock {
    param($rp)
    if (Test-Path $rp) { Remove-Item $rp -Recurse -Force }
    New-Item -ItemType Directory -Path $rp -Force | Out-Null
    Expand-Archive -Path 'C:\Users\Administrator\Desktop\dp.zip' -DestinationPath $rp -Force
    Write-Host 'Extracted to:' $rp
    Get-ChildItem $rp | Select-Object Name | Format-Table
} -ArgumentList $remotePath
Write-Host '[3] OK'

Write-Host '[4] Write nginx.conf...'
Invoke-Command -Session $session -ScriptBlock {
    param($rp)
    $nginxDir = 'C:\nginx\conf'
    if (-not (Test-Path $nginxDir)) { New-Item -ItemType Directory -Path $nginxDir -Force | Out-Null }
    $confContent = 'worker_processes 1;' + "`n"
    $confContent += 'events { worker_connections 1024; }' + "`n"
    $confContent += 'http {' + "`n"
    $confContent += '    include       mime.types;' + "`n"
    $confContent += '    default_type  application/octet-stream;' + "`n"
    $confContent += '    sendfile        on;' + "`n"
    $confContent += '    keepalive_timeout  65;' + "`n"
    $confContent += '    server {' + "`n"
    $confContent += '        listen       80;' + "`n"
    $confContent += '        server_name  localhost;' + "`n"
    $confContent += '        client_max_body_size 100M;' + "`n"
    $confContent += '        location / {' + "`n"
    $confContent += '            root   "' + $rp + '";' + "`n"
    $confContent += '            index  index.html index.htm;' + "`n"
    $confContent += '            try_files $uri $uri/ /index.html;' + "`n"
    $confContent += '        }' + "`n"
    $confContent += '        location /api/ {' + "`n"
    $confContent += '            proxy_pass http://127.0.0.1:5000/;' + "`n"
    $confContent += '            proxy_set_header Host $host;' + "`n"
    $confContent += '            proxy_set_header X-Real-IP $remote_addr;' + "`n"
    $confContent += '        }' + "`n"
    $confContent += '    }' + "`n"
    $confContent += '}' + "`n"
    [IO.File]::WriteAllText("$nginxDir\nginx.conf", $confContent)
    Write-Host 'nginx.conf written'
} -ArgumentList $remotePath
Write-Host '[4] OK'

Write-Host '[5] Start nginx...'
Invoke-Command -Session $session -ScriptBlock {
    Start-Process C:\nginx\nginx.exe -WindowStyle Hidden -ErrorAction SilentlyContinue
    Start-Sleep 3
    $p = Get-Process nginx -ErrorAction SilentlyContinue
    if ($p) { Write-Host 'nginx running PID:' $p.Id }
    else { Write-Host 'WARNING: nginx not running' }
}
Write-Host '[5] OK'

Write-Host '[6] Cleanup...'
Invoke-Command -Session $session -ScriptBlock {
    Remove-Item 'C:\Users\Administrator\Desktop\dp.zip' -Force -ErrorAction SilentlyContinue
    Write-Host 'Cleanup done'
}
Write-Host '[6] OK'
