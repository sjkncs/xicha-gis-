$pass = ConvertTo-SecureString 'asR84SiRzqhbDvZF' -AsPlainText -Force
$creds = New-Object PSCredential('Administrator', $pass)
$s = New-PSSession -ComputerName '64.90.0.78' -Port 5985 -Credential $creds

Write-Host "[1] Check current static dir..."
Invoke-Command -Session $s -ScriptBlock {
    if (Test-Path "C:\www\15min\static") {
        Write-Host "static exists, listing files:"
        Get-ChildItem "C:\www\15min\static" | Select-Object Name | Format-Table
    } else {
        Write-Host "static NOT found"
        Get-ChildItem "C:\www\15min" | Select-Object Name | Format-Table
    }
}

Write-Host "[2] Move files to static/..."
Invoke-Command -Session $s -ScriptBlock {
    $src = "C:\www\15min"
    $dst = "C:\www\15min\static"
    New-Item -ItemType Directory -Path $dst -Force | Out-Null
    Get-ChildItem $src -File | Move-Item -Destination $dst -Force
    Write-Host "Moved files to static/"
    Get-ChildItem $dst | Select-Object Name | Format-Table
}

Write-Host "[3] Backup and update Caddyfile..."
Invoke-Command -Session $s -ScriptBlock {
    $cf = "C:\globalreviewops\Caddyfile"
    $bak = "C:\globalreviewops\Caddyfile.bak_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Copy-Item $cf $bak -Force
    Write-Host "Backup: $bak"

    $lines = Get-Content $cf
    $newLines = @()
    $skip = $false
    foreach ($line in $lines) {
        if ($line -match '# Isolated Caddy site for 15min') { $skip = $true }
        if ($skip) { continue }
        $newLines += $line
    }

    $newLines += ""
    $newLines += "# Updated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    $newLines += "http://64.90.0.78 {"
    $newLines += "    encode gzip zstd"
    $newLines += "    handle /api/* {"
    $newLines += "        reverse_proxy 127.0.0.1:8765"
    $newLines += "    }"
    $newLines += "    handle {"
    $newLines += "        root * C:/www/15min/static"
    $newLines += "        try_files {path} /city_twin_viewer.html"
    $newLines += "        file_server"
    $newLines += "    }"
    $newLines += "    header {"
    $newLines += "        X-Content-Type-Options nosniff"
    $newLines += "        Referrer-Policy strict-origin-when-cross-origin"
    $newLines += "    }"
    $newLines += "}"

    $newContent = $newLines -join [Environment]::NewLine
    [IO.File]::WriteAllText($cf, $newContent)
    Write-Host "Caddyfile updated"
}

Write-Host "[4] Stop old Caddy..."
Invoke-Command -Session $s -ScriptBlock {
    Get-Process caddy -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep 2
    Write-Host "Caddy stopped"
}

Write-Host "[5] Start Caddy..."
Invoke-Command -Session $s -ScriptBlock {
    Start-Process -FilePath "C:\globalreviewops\caddy\caddy.exe" -ArgumentList "run","--config","C:\globalreviewops\Caddyfile","--adapter","caddyfile" -WindowStyle Hidden
    Start-Sleep 3
    $p = Get-Process caddy -ErrorAction SilentlyContinue
    if ($p) { Write-Host "Caddy running PID: $($p.Id)" }
    else { Write-Host "WARNING: Caddy not running" }
}

Write-Host "[6] Test http://64.90.0.78..."
Invoke-Command -Session $s -ScriptBlock {
    try {
        $r = Invoke-WebRequest -Uri "http://64.90.0.78/" -UseBasicParsing -TimeoutSec 10 -MaximumRedirection 0
        Write-Host "HTTP $($r.StatusCode) $($r.StatusDescription)"
        if ($r.Content) {
            Write-Host "Content length: $($r.Content.Length)"
            Write-Host "First 200: $($r.Content.Substring(0, [Math]::Min(200, $r.Content.Length)))"
        }
    } catch {
        $resp = $_.Exception.Response
        if ($resp) {
            Write-Host "HTTP $($resp.StatusCode.value__) $($resp.StatusDescription)"
            Write-Host "Location: $($resp.Headers['Location'])"
        } else {
            Write-Host "No response: $($_.Exception.Message)"
        }
    }
}

Remove-PSSession $s
Write-Host ""
Write-Host "========================================"
Write-Host "DONE - Visit http://64.90.0.78"
Write-Host "========================================"
