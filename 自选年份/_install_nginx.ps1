$pass = ConvertTo-SecureString 'asR84SiRzqhbDvZF' -AsPlainText -Force
$creds = New-Object PSCredential('Administrator', $pass)
$s = New-PSSession -ComputerName '64.90.0.78' -Port 5985 -Credential $creds

Write-Host "[1] Download nginx..."
Invoke-Command -Session $s -ScriptBlock {
    $url = "https://nginx.org/download/nginx-1.26.0.zip"
    $out = "C:\Users\Administrator\nginx.zip"
    try {
        Invoke-WebRequest -Uri $url -OutFile $out -TimeoutSec 60
        $sz = (Get-Item $out).Length
        Write-Host "Downloaded $sz bytes"
    } catch {
        Write-Host "ERROR: $_"
    }
}

Write-Host "[2] Extract nginx..."
Invoke-Command -Session $s -ScriptBlock {
    $zip = "C:\Users\Administrator\nginx.zip"
    $dest = "C:\Users\Administrator\nginx_tmp"
    if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
    New-Item -ItemType Directory -Path $dest -Force | Out-Null
    Expand-Archive -Path $zip -DestinationPath $dest -Force
    Write-Host "Extracted"
    Get-ChildItem $dest | Select-Object Name | Format-Table
}

Write-Host "[3] Copy nginx.exe..."
Invoke-Command -Session $s -ScriptBlock {
    $src = "C:\Users\Administrator\nginx_tmp\nginx-1.26.0\nginx.exe"
    $dst = "C:\nginx\nginx.exe"
    if (-not (Test-Path "C:\nginx")) { New-Item -ItemType Directory -Path "C:\nginx" -Force | Out-Null }
    Copy-Item -Path $src -Destination $dst -Force
    Write-Host "nginx.exe copied"
    (Get-Item $dst).Length
}

Write-Host "[4] Start nginx..."
Invoke-Command -Session $s -ScriptBlock {
    Start-Process C:\nginx\nginx.exe -WindowStyle Hidden -ErrorAction SilentlyContinue
    Start-Sleep 3
    $p = Get-Process nginx -ErrorAction SilentlyContinue
    if ($p) { Write-Host "nginx running PID: $($p.Id)" }
    else { Write-Host "WARNING: nginx not found" }
}

Write-Host "[5] Cleanup..."
Invoke-Command -Session $s -ScriptBlock {
    Remove-Item "C:\Users\Administrator\nginx.zip" -Force -ErrorAction SilentlyContinue
    Remove-Item "C:\Users\Administrator\nginx_tmp" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Done"
}

Remove-PSSession $s
Write-Host "ALL DONE"
