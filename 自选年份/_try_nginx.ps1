$pass = ConvertTo-SecureString 'asR84SiRzqhbDvZF' -AsPlainText -Force
$creds = New-Object PSCredential('Administrator', $pass)
$s = New-PSSession -ComputerName '64.90.0.78' -Port 5985 -Credential $creds

Write-Host "[1] Check nginx.exe exists..."
Invoke-Command -Session $s -ScriptBlock {
    $nginxExe = "C:\nginx\nginx.exe"
    if (Test-Path $nginxExe) {
        Write-Host "EXISTS: $nginxExe"
        Write-Host "Size: $((Get-Item $nginxExe).Length)"
    } else {
        Write-Host "NOT FOUND: $nginxExe"
    }
    $conf = "C:\nginx\conf\nginx.conf"
    if (Test-Path $conf) {
        Write-Host "CONF EXISTS: $conf"
    } else {
        Write-Host "CONF NOT FOUND: $conf"
    }
}

Write-Host "[2] Try start with -FilePath..."
Invoke-Command -Session $s -ScriptBlock {
    try {
        Start-Process -FilePath "C:\nginx\nginx.exe" -WindowStyle Hidden -PassThru | Format-Table Id, HasExited, ExitCode
        Start-Sleep 3
        $p = Get-Process nginx -ErrorAction SilentlyContinue
        if ($p) { Write-Host "nginx PID: $($p.Id)" }
        else { Write-Host "Still not running" }
    } catch {
        Write-Host "ERROR: $_"
    }
}

Write-Host "[3] Try direct invocation..."
Invoke-Command -Session $s -ScriptBlock {
    Set-Location C:\nginx
    & ".\nginx.exe" -v
    Write-Host "Started"
}

Write-Host "[4] Try via cmd..."
Invoke-Command -Session $s -ScriptBlock {
    cmd /c "C:\nginx\nginx.exe" 2>&1 | Select-Object -First 5
}

Remove-PSSession $s
