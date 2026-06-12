$pass = ConvertTo-SecureString 'asR84SiRzqhbDvZF' -AsPlainText -Force
$creds = New-Object PSCredential('Administrator', $pass)
$s = New-PSSession -ComputerName '64.90.0.78' -Port 5985 -Credential $creds

Write-Host "=== Python ==="
Invoke-Command -Session $s -ScriptBlock {
    try {
        $v = & python --version 2>&1
        Write-Host "Python: $v"
        $py = (Get-Command python -ErrorAction SilentlyContinue).Source
        Write-Host "Path: $py"
    } catch { Write-Host "Python not found: $_" }
}

Write-Host "=== Python3 ==="
Invoke-Command -Session $s -ScriptBlock {
    try {
        $v = & python3 --version 2>&1
        Write-Host "Python3: $v"
    } catch { Write-Host "python3: $_" }
}

Write-Host "=== IIS ==="
Invoke-Command -Session $s -ScriptBlock {
    Get-Service W3SVC -ErrorAction SilentlyContinue | Format-Table Name, Status -AutoSize
}

Write-Host "=== Download tools ==="
Invoke-Command -Session $s -ScriptBlock {
    try { Invoke-WebRequest -Uri "https://nginx.org/download/nginx-1.26.0.zip" -OutFile "C:\Users\Administrator\nginx.zip" -TimeoutSec 30; Write-Host "Invoke-WebRequest OK" } catch { Write-Host "Invoke-WebRequest FAILED: $_" }
}

Remove-PSSession $s
