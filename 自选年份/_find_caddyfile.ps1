$pass = ConvertTo-SecureString 'asR84SiRzqhbDvZF' -AsPlainText -Force
$creds = New-Object PSCredential('Administrator', $pass)
$s = New-PSSession -ComputerName '64.90.0.78' -Port 5985 -Credential $creds

Write-Host "=== Find Caddyfile ==="
Invoke-Command -Session $s -ScriptBlock {
    Get-ChildItem "C:\globalreviewops\caddy" -ErrorAction SilentlyContinue | Select-Object Name | Format-Table
    Get-ChildItem "C:\globalreviewops" -ErrorAction SilentlyContinue | Select-Object Name | Format-Table
}

Write-Host "=== Search for Caddyfile ==="
Invoke-Command -Session $s -ScriptBlock {
    Get-ChildItem C:\globalreviewops -Recurse -Filter "Caddyfile*" -ErrorAction SilentlyContinue | Select-Object FullName | Format-Table
    Get-ChildItem C:\ -Recurse -Filter "Caddyfile*" -Depth 2 -ErrorAction SilentlyContinue | Select-Object FullName | Format-Table
}

Write-Host "=== Test current HTTP response ==="
Invoke-Command -Session $s -ScriptBlock {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost/" -UseBasicParsing -TimeoutSec 5 -MaximumRedirection 0 -ErrorAction SilentlyContinue
        Write-Host "HTTP $($r.StatusCode) $($r.StatusDescription)"
        Write-Host "Headers:"
        $r.Headers | Format-Table -AutoSize
    } catch {
        $resp = $_.Exception.Response
        if ($resp) {
            Write-Host "HTTP $($resp.StatusCode) $($resp.StatusDescription)"
            Write-Host "Headers:"
            $resp.Headers | Format-Table -AutoSize
        } else {
            Write-Host "No response: $($_.Exception.Message)"
        }
    }
}

Write-Host "=== Caddy process details ==="
Invoke-Command -Session $s -ScriptBlock {
    Get-Process caddy | Select-Object Id, Path, @{N='Args';E={(Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine}} | Format-List
}

Remove-PSSession $s
