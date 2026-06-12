$pass = ConvertTo-SecureString 'asR84SiRzqhbDvZF' -AsPlainText -Force
$creds = New-Object PSCredential('Administrator', $pass)
$s = New-PSSession -ComputerName '64.90.0.78' -Port 5985 -Credential $creds

Write-Host "=== Current Caddyfile ==="
Invoke-Command -Session $s -ScriptBlock {
    Get-Content "C:\globalreviewops\Caddyfile" | Select-Object -First 50
}

Write-Host "=== Full Caddyfile ==="
Invoke-Command -Session $s -ScriptBlock {
    Get-Content "C:\globalreviewops\Caddyfile"
}

Remove-PSSession $s
