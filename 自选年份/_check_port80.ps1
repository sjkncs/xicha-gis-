$pass = ConvertTo-SecureString 'asR84SiRzqhbDvZF' -AsPlainText -Force
$creds = New-Object PSCredential('Administrator', $pass)
$s = New-PSSession -ComputerName '64.90.0.78' -Port 5985 -Credential $creds

Write-Host "=== Port 80 usage ==="
Invoke-Command -Session $s -ScriptBlock {
    $connections = Get-NetTCPConnection -LocalPort 80 -ErrorAction SilentlyContinue
    if ($connections) {
        foreach ($c in $connections) {
            $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
            Write-Host "PID=$($c.OwningProcess) Process=$($proc.ProcessName) State=$($c.State) Local=$($c.LocalAddress):$($c.LocalPort)"
        }
    } else {
        Write-Host "No TCP connections on port 80"
    }
}

Write-Host "=== HTTP service ==="
Invoke-Command -Session $s -ScriptBlock {
    Get-Service W3SVC, HTTP, WAS -ErrorAction SilentlyContinue | Format-Table Name, DisplayName, Status -AutoSize
}

Write-Host "=== IIS ==="
Invoke-Command -Session $s -ScriptBlock {
    if (Test-Path IIS:\Sites\DefaultWebSite) {
        Get-Website -Name "Default Web Site" -ErrorAction SilentlyContinue | Format-Table Name, Id, State, PhysicalPath, Bindings -AutoSize
    } else {
        Write-Host "No IIS Default Web Site"
    }
}

Remove-PSSession $s
