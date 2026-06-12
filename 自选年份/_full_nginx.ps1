$pass = ConvertTo-SecureString 'asR84SiRzqhbDvZF' -AsPlainText -Force
$creds = New-Object PSCredential('Administrator', $pass)
$s = New-PSSession -ComputerName '64.90.0.78' -Port 5985 -Credential $creds

Write-Host "[1] Clean up old nginx..."
Invoke-Command -Session $s -ScriptBlock {
    Get-Process nginx -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    if (Test-Path C:\nginx) { Remove-Item C:\nginx -Recurse -Force }
    Write-Host "Cleaned"
}

Write-Host "[2] Download nginx..."
Invoke-Command -Session $s -ScriptBlock {
    $url = "https://nginx.org/download/nginx-1.26.0.zip"
    $out = "C:\Users\Administrator\nginx.zip"
    try {
        Invoke-WebRequest -Uri $url -OutFile $out -TimeoutSec 60
        Write-Host "Downloaded: $((Get-Item $out).Length) bytes"
    } catch {
        Write-Host "Download failed: $_"
    }
}

Write-Host "[3] Extract nginx..."
Invoke-Command -Session $s -ScriptBlock {
    $zip = "C:\Users\Administrator\nginx.zip"
    $dest = "C:\nginx"
    New-Item -ItemType Directory -Path $dest -Force | Out-Null
    Expand-Archive -Path $zip -DestinationPath $dest -Force
    $inner = Join-Path $dest "nginx-1.26.0"
    if (Test-Path $inner) {
        Get-ChildItem $inner | Move-Item -Destination $dest -Force
        Remove-Item $inner -Force
    }
    Write-Host "Extracted to C:\nginx"
    Get-ChildItem $dest | Select-Object Name | Format-Table
}

Write-Host "[4] Write nginx.conf..."
Invoke-Command -Session $s -ScriptBlock {
    param($rp)
    $confPath = "C:\nginx\conf\nginx.conf"
    $nl = [Environment]::NewLine
    $c = "worker_processes 1;$nl"
    $c += "events { worker_connections 1024; }$nl"
    $c += "http {$nl"
    $c += "    include       mime.types;$nl"
    $c += "    default_type  application/octet-stream;$nl"
    $c += "    sendfile        on;$nl"
    $c += "    keepalive_timeout  65;$nl"
    $c += "    server {$nl"
    $c += "        listen       80;$nl"
    $c += "        server_name  localhost;$nl"
    $c += "        client_max_body_size 100M;$nl"
    $c += "        location / {$nl"
    $c += "            root   `"$rp`";$nl"
    $c += "            index  index.html index.htm;$nl"
    $c += "            try_files " + '$' + "uri " + '$' + "uri/ /index.html;$nl"
    $c += "        }$nl"
    $c += "        location /api/ {$nl"
    $c += "            proxy_pass http://127.0.0.1:5000/;$nl"
    $c += "            proxy_set_header Host " + '$' + "host;$nl"
    $c += "            proxy_set_header X-Real-IP " + '$' + "remote_addr;$nl"
    $c += "        }$nl"
    $c += "    }$nl"
    $c += "}$nl"
    [IO.File]::WriteAllText($confPath, $c)
    Write-Host "nginx.conf written ($($c.Length) chars)"
} -ArgumentList "C:\www\15min"

Write-Host "[5] Start nginx..."
Invoke-Command -Session $s -ScriptBlock {
    Set-Location C:\nginx
    & .\nginx.exe
    Start-Sleep 3
    $p = Get-Process nginx -ErrorAction SilentlyContinue
    if ($p) { Write-Host "nginx running PID: $($p.Id)" }
    else { Write-Host "WARNING: not running" }
}

Write-Host "[6] Test HTTP..."
Invoke-Command -Session $s -ScriptBlock {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost/" -UseBasicParsing -TimeoutSec 5
        Write-Host "HTTP $($r.StatusCode) length=$($r.Content.Length)"
    } catch {
        Write-Host "HTTP error: $($_.Exception.Message)"
    }
}

Write-Host "[7] Cleanup..."
Invoke-Command -Session $s -ScriptBlock {
    Remove-Item "C:\Users\Administrator\nginx.zip" -Force -ErrorAction SilentlyContinue
    Write-Host "Done"
}

Remove-PSSession $s
Write-Host ""
Write-Host "========================================"
Write-Host "DONE - Visit http://64.90.0.78"
Write-Host "========================================"
