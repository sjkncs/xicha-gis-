$ErrorActionPreference = 'Stop'
$server = '64.90.0.78'
$port = 5985
$user = 'Administrator'
$pass = 'asR84SiRzqhbDvZF'

$secPass = ConvertTo-SecureString $pass -AsPlainText -Force
$creds = New-Object System.Management.Automation.PSCredential($user, $secPass)
Write-Host "Connecting to $server`:$port..."
$session = New-PSSession -ComputerName $server -Port $port -Credential $creds
Write-Host "Session OK"

# Write the deploy script to remote disk
Write-Host "Writing deploy script to remote..."
$scriptContent = @"
`$ErrorActionPreference = 'Stop'
`$localZip = 'E:\xicha gis 智能定位\自选年份\deploy_package.zip'
`$remotePath = 'C:\www\15min'

Write-Host '[1] Copy zip to desktop...'
Copy-Item -Path `$localZip -Destination 'C:\Users\Administrator\Desktop\dp.zip' -Force
Write-Host '[1] OK'

Write-Host '[2] Stop nginx...'
Stop-Service nginx -Force -ErrorAction SilentlyContinue
Get-Process nginx -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host '[2] OK'

Write-Host '[3] Extract files...'
if (Test-Path `$remotePath) { Remove-Item `$remotePath -Recurse -Force }
New-Item -ItemType Directory -Path `$remotePath -Force | Out-Null
Expand-Archive -Path 'C:\Users\Administrator\Desktop\dp.zip' -DestinationPath `$remotePath -Force
Get-ChildItem `$remotePath | Select-Object Name | Format-Table
Write-Host '[3] OK'

Write-Host '[4] Write nginx.conf...'
`$conf = @"
worker_processes 1;
events { worker_connections 1024; }
http {
    include mime.types;
    default_type application/octet-stream;
    sendfile on;
    keepalive_timeout 65;
    server {
        listen 80;
        server_name localhost;
        client_max_body_size 100M;
        location / {
            root   "` + "`$remotePath" + `";
            index  index.html;
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
`$conf | Out-File -FilePath 'C:\nginx\conf\nginx.conf' -Encoding UTF8 -Force
Write-Host '[4] OK'

Write-Host '[5] Start nginx...'
Start-Process C:\nginx\nginx.exe -WindowStyle Hidden -ErrorAction SilentlyContinue
Start-Sleep 3
`$p = Get-Process nginx -ErrorAction SilentlyContinue
if (`$p) { Write-Host 'nginx PID:' `$p.Id }
else { Write-Host 'WARNING: nginx not running' }

Write-Host '[6] Cleanup...'
Remove-Item 'C:\Users\Administrator\Desktop\dp.zip' -Force -ErrorAction SilentlyContinue
Write-Host 'ALL DONE - http://64.90.0.78'
"@

$tmpPath = 'C:\Users\Administrator\deploy_doit.ps1'
Invoke-Command -Session $session -ScriptBlock {
    param($content, $path)
    [IO.File]::WriteAllText($path, $content, [Text.Encoding]::UTF8)
    Write-Host "Script written to $path"
} -ArgumentList $scriptContent, $tmpPath

# Execute the script on remote
Write-Host "Running deploy script on remote..."
Invoke-Command -Session $session -ScriptBlock {
    & 'C:\Users\Administrator\deploy_doit.ps1'
}

# Cleanup
Invoke-Command -Session $session -ScriptBlock {
    Remove-Item 'C:\Users\Administrator\deploy_doit.ps1' -Force -ErrorAction SilentlyContinue
    Write-Host "Script cleaned up"
}

Remove-PSSession $session
Write-Host "Session closed - DONE!"
