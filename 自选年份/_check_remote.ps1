$pass = ConvertTo-SecureString 'asR84SiRzqhbDvZF' -AsPlainText -Force
$creds = New-Object PSCredential('Administrator', $pass)
$s = New-PSSession -ComputerName '64.90.0.78' -Port 5985 -Credential $creds

Write-Host "=== Services ==="
Invoke-Command -Session $s -ScriptBlock {
    Get-Service nginx -ErrorAction SilentlyContinue | Format-Table Name, Status, DisplayName -AutoSize
}

Write-Host "=== NGINX Install Location ==="
Invoke-Command -Session $s -ScriptBlock {
    Get-ChildItem 'C:\nginx*' -Recurse -ErrorAction SilentlyContinue | Select-Object FullName | Format-Table -AutoSize
}

Write-Host "=== NGINX Processes ==="
Invoke-Command -Session $s -ScriptBlock {
    Get-Process nginx -ErrorAction SilentlyContinue | Select-Object Id, PathName | Format-Table -AutoSize
}

Write-Host "=== PATH entries ==="
Invoke-Command -Session $s -ScriptBlock {
    $env:Path -split ';'
}

Write-Host "=== C:\www\15min ==="
Invoke-Command -Session $s -ScriptBlock {
    Get-ChildItem 'C:\www\15min' -Name | Format-Table
}

Remove-PSSession $s
