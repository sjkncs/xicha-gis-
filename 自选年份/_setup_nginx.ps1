$pass = ConvertTo-SecureString 'asR84SiRzqhbDvZF' -AsPlainText -Force
$creds = New-Object PSCredential('Administrator', $pass)
$s = New-PSSession -ComputerName '64.90.0.78' -Port 5985 -Credential $creds

Write-Host "[1] Stop existing nginx processes..."
Invoke-Command -Session $s -ScriptBlock {
    Get-Process nginx -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped"
}

Write-Host "[2] Remove old C:\nginx..."
Invoke-Command -Session $s -ScriptBlock {
    if (Test-Path C:\nginx) { Remove-Item C:\nginx -Recurse -Force }
    Write-Host "Removed"
}

Write-Host "[3] Extract full nginx package to C:\nginx..."
Invoke-Command -Session $s -ScriptBlock {
    $zip = "C:\Users\Administrator\nginx.zip"
    $dest = "C:\nginx"
    New-Item -ItemType Directory -Path $dest -Force | Out-Null
    Expand-Archive -Path $zip -DestinationPath $dest -Force
    # Move contents of nginx-1.26.0/* up to C:\nginx\
    $inner = "C:\nginx\nginx-1.26.0"
    Get-ChildItem $inner | Move-Item -Destination $dest -Force
    Remove-Item $inner -Force
    Write-Host "Extracted"
    Get-ChildItem $dest | Select-Object Name | Format-Table
}

Write-Host "[4] Update nginx.conf with correct paths..."
Invoke-Command -Session $s -ScriptBlock {
    param($rp)
    $confPath = "C:\nginx\conf\nginx.conf"
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
    [IO.File]::WriteAllText($confPath, $conf)
    Write-Host "nginx.conf updated"
} -ArgumentList "C:\www\15min"

Write-Host "[5] Start nginx from its directory..."
Invoke-Command -Session $s -ScriptBlock {
    Set-Location C:\nginx
    & .\nginx.exe
    Start-Sleep 3
    $p = Get-Process nginx -ErrorAction SilentlyContinue
    if ($p) { Write-Host "SUCCESS: nginx running PID $($p.Id)" }
    else { Write-Host "WARNING: nginx not running" }
}

Write-Host "[6] Test HTTP response..."
Invoke-Command -Session $s -ScriptBlock {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost/" -UseBasicParsing -TimeoutSec 5
        Write-Host "HTTP $($r.StatusCode), length $($r.Content.Length)"
        Write-Host "First 100 chars: $($r.Content.Substring(0, [Math]::Min(100, $r.Content.Length)))"
    } catch {
        Write-Host "HTTP error: $_"
    }
}

Write-Host "[7] Cleanup nginx zip..."
Invoke-Command -Session $s -ScriptBlock {
    Remove-Item "C:\Users\Administrator\nginx.zip" -Force -ErrorAction SilentlyContinue
    Write-Host "Done"
}

Remove-PSSession $s
Write-Host "ALL DONE"
