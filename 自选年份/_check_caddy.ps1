$pass = ConvertTo-SecureString 'asR84SiRzqhbDvZF' -AsPlainText -Force
$creds = New-Object PSCredential('Administrator', $pass)
$s = New-PSSession -ComputerName '64.90.0.78' -Port 5985 -Credential $creds

Write-Host "[1] Check Caddy..."
Invoke-Command -Session $s -ScriptBlock {
    $caddyProc = Get-Process -Id 7996 -ErrorAction SilentlyContinue
    if ($caddyProc) {
        Write-Host "Caddy PID: $($caddyProc.Id), Path: $($caddyProc.Path)"
    } else {
        Write-Host "Caddy PID changed, finding current..."
        Get-Process caddy -ErrorAction SilentlyContinue | Select-Object Id, Path | Format-Table
    }
}

Write-Host "[2] Caddyfile location..."
Invoke-Command -Session $s -ScriptBlock {
    $paths = @(
        "C:\Caddy\Caddyfile",
        "C:\caddy\Caddyfile",
        "C:\Users\Administrator\Caddyfile",
        "C:\www\Caddyfile",
        "C:\Caddyfile"
    )
    foreach ($p in $paths) {
        if (Test-Path $p) {
            Write-Host "Found: $p"
            Get-Content $p
        }
    }
    # Also check for running config
    Get-Process caddy -ErrorAction SilentlyContinue | Select-Object Id, Path | Format-Table
}

Write-Host "[3] Test current site..."
Invoke-Command -Session $s -ScriptBlock {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost/" -UseBasicParsing -TimeoutSec 5
        Write-Host "HTTP $($r.StatusCode) len=$($r.Content.Length)"
    } catch {
        Write-Host "HTTP error: $($_.Exception.Message)"
    }
}

Remove-PSSession $s
