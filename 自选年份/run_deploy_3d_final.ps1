$ErrorActionPreference = 'Stop'

# 配置 TrustedHosts (允许非域机器)
$current = (Get-Item WSMan:\localhost\Client\TrustedHosts -ErrorAction SilentlyContinue).Value
$newVal = if ($current -and $current -ne '') { "$current,64.90.0.78" } else { "64.90.0.78" }
Set-Item WSMan:\localhost\Client\TrustedHosts -Value $newVal -Force
Write-Host ("TrustedHosts updated: " + (Get-Item WSMan:\localhost\Client\TrustedHosts).Value)

$RHOST = '64.90.0.78'
$RPORT = 5985
$RUSER = 'Administrator'
$RPASS = 'asR84SiRzqhbDvZF'
$REMOTE_DIR = 'C:\\dp3d_work'
$STATIC_DIR = 'C:\\www\\15min\\static'
$ZIP_PATH = 'E:\\xicha gis 智能定位\\自选年份\\deploy_3d.zip'

if (-not (Test-Path $ZIP_PATH)) { Write-Host "ZIP NOT FOUND: $ZIP_PATH"; exit 1 }

Write-Host "=== 3D Deploy ==="
Write-Host ("ZIP: " + $ZIP_PATH)
Write-Host ((Get-Item $ZIP_PATH).Length / 1MB).ToString('F1') + " MB"

Write-Host ("[1] Connecting to " + $RHOST + ":" + $RPORT + "...")
$secPass = ConvertTo-SecureString $RPASS -AsPlainText -Force
$cred = New-Object PSCredential($RUSER, $secPass)
$s = New-PSSession -ComputerName $RHOST -Port $RPORT -Credential $cred -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Write-Host ("Session ID: " + $s.Id)

Write-Host "[2] Init remote dirs..."
Invoke-Command -Session $s -ScriptBlock {
    param($rd, $sd)
    if (Test-Path $rd) { Remove-Item $rd -Recurse -Force }
    New-Item -ItemType Directory -Path $rd -Force | Out-Null
    if (-not (Test-Path $sd)) { New-Item -ItemType Directory -Path $sd -Force | Out-Null }
    Write-Host "Remote dirs ready"
} -ArgumentList $REMOTE_DIR, $STATIC_DIR

Write-Host "[3] Read local ZIP and Base64..."
$zipBytes = [IO.File]::ReadAllBytes($ZIP_PATH)
$zipB64 = [Convert]::ToBase64String($zipBytes)
Write-Host ((($zipB64.Length) / 1MB).ToString('F1') + " MB Base64")

Write-Host "[4] Create remote merge file..."
Invoke-Command -Session $s -ScriptBlock {
    param($p)
    $fs = [IO.File]::Create($p)
    $fs.Close()
    Write-Host ("Created: " + $p)
} -ArgumentList ($REMOTE_DIR + "\all.b64")

$CHUNK = 512KB
$total = [math]::Ceiling($zipB64.Length / $CHUNK)
Write-Host ("[5] Append " + $total + " chunks...")
$t0 = Get-Date

for ($i = 0; $i -lt $total; $i++) {
    $start = $i * $CHUNK
    $len = [math]::Min($CHUNK, $zipB64.Length - $start)
    $chunk = $zipB64.Substring($start, $len)

    Invoke-Command -Session $s -ScriptBlock {
        param($chunk, $tmpPath, $allPath)
        $chunkBytes = [Convert]::FromBase64String($chunk)
        [IO.File]::WriteAllBytes($tmpPath, $chunkBytes)
        $chunkBytes2 = [IO.File]::ReadAllBytes($tmpPath)
        $fs = [IO.File]::OpenWrite($allPath)
        $fs.Seek(0, [IO.SeekOrigin]::End) | Out-Null
        $fs.Write($chunkBytes2, 0, $chunkBytes2.Length)
        $fs.Close()
        Remove-Item $tmpPath -Force
        Write-Host ("chunk_" + $i)
    } -ArgumentList $chunk, ($REMOTE_DIR + "\chunk_$i.bin"), ($REMOTE_DIR + "\all.b64")

    $pct = ($i+1) / $total * 100
    $el = ((Get-Date)-$t0).TotalSeconds
    $eta = if ($i -gt 0) { $el/($i+1)*($total-$i-1) } else { 0 }
    $bar = ('=' * [math]::Floor($pct/2)).PadRight(50)
    Write-Host ("  [" + ('{0:D3}' -f ($i+1)) + "/" + $total + "] " + $bar + " " + ('{0,5:F0}' -f $pct) + "%  ETA:" + ([math]::Round($eta,0)) + "s") -NoNewline
}

Write-Host ""
Write-Host "[6] Decode ZIP..."
Invoke-Command -Session $s -ScriptBlock {
    param($src, $dst, $sd)
    Write-Host ("  Reading Base64 from: " + $src)
    $b64 = [IO.File]::ReadAllText($src, [Text.Encoding]::ASCII)
    Write-Host ("  Decoding " + (($b64.Length)/1MB).ToString('F1') + " MB Base64...")
    $bytes = [Convert]::FromBase64String($b64)
    Write-Host ("  Writing " + ($bytes.Length/1MB).ToString('F1') + " MB...")
    [IO.File]::WriteAllBytes($dst, $bytes)
    $z = (Get-Item $dst).Length / 1MB
    Write-Host ("  ZIP ready: " + $z.ToString('F1') + " MB")
} -ArgumentList ($REMOTE_DIR + "\all.b64"), ($REMOTE_DIR + "\dp.zip"), $STATIC_DIR

Write-Host "[7] Extract..."
Invoke-Command -Session $s -ScriptBlock {
    param($src, $sd)
    [IO.Compression.ZipFile]::ExtractToDirectory($src, $sd)
    Write-Host "  Done:"
    Get-ChildItem $sd | ForEach-Object {
        Write-Host ("    " + $_.Name + " (" + ($_.Length/1MB).ToString('F1') + " MB)")
    }
} -ArgumentList ($REMOTE_DIR + "\dp.zip"), $STATIC_DIR

Write-Host "[8] Restart Caddy..."
Invoke-Command -Session $s -ScriptBlock {
    $c = Get-Process caddy -EA SilentlyContinue
    if ($c) { Stop-Process $c -Force; Start-Sleep 2; Write-Host "  Stopped old Caddy" }
    Start-Process "C:\ProgramData\caddy\caddy.exe" -ArgumentList "run","--config","C:\globalreviewops\Caddyfile" -NoNewWindow | Out-Null
    Start-Sleep 3
    $n = Get-Process caddy -EA SilentlyContinue
    Write-Host ("  Caddy PID: " + $n.Id)
}

Write-Host "[9] Cleanup..."
Invoke-Command -Session $s -ScriptBlock {
    param($d)
    Remove-Item $d -Recurse -Force -EA SilentlyContinue
    Write-Host "  Done"
} -ArgumentList $REMOTE_DIR

Remove-PSSession $s
$el = ((Get-Date)-$t0).TotalSeconds
Write-Host ("=== DONE in " + [math]::Round($el,0) + "s ===")
