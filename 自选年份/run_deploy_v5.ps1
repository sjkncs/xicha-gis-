$ErrorActionPreference = 'Stop'

# 配置 TrustedHosts
$cur = (Get-Item WSMan:\localhost\Client\TrustedHosts -EA SilentlyContinue).Value
$newV = if ($cur -and $cur -ne '') { "$cur,64.90.0.78" } else { "64.90.0.78" }
Set-Item WSMan:\localhost\Client\TrustedHosts -Value $newV -Force

$RHOST = '64.90.0.78'
$RPORT = 5985
$RUSER = 'Administrator'
$RPASS = 'asR84SiRzqhbDvZF'
$REMOTE_DIR = 'C:\\dp3d_work'
$STATIC_DIR = 'C:\\www\\15min\\static'
$ZIP_PATH = 'E:\\xicha gis 智能定位\\自选年份\\deploy_3d.zip'
$N_CHUNKS = 262

Write-Host "=== 3D Deploy ==="
Write-Host ("ZIP: " + $ZIP_PATH)
Write-Host ((Get-Item $ZIP_PATH).Length / 1MB).ToString('F1') + " MB"

Write-Host "[1] Connecting to " + $RHOST + "..."
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
    Write-Host "Ready"
} -ArgumentList $REMOTE_DIR, $STATIC_DIR

Write-Host "[3] Read local ZIP..."
$zipBytes = [IO.File]::ReadAllBytes($ZIP_PATH)
Write-Host ("ZIP bytes: " + ($zipBytes.Length / 1MB).ToString('F1') + " MB")

Write-Host "[4] Split ZIP locally..."
$CHUNK = 524288
$allParts = @()
for ($i = 0; $i -lt $N_CHUNKS; $i++) {
    $start = $i * $CHUNK
    $len = [math]::Min($CHUNK, $zipBytes.Length - $start)
    $part = $zipBytes[$start..($start+$len-1)]
    $tmpPath = Join-Path $env:TEMP ("dp3d_part_$i.bin")
    [IO.File]::WriteAllBytes($tmpPath, $part)
    $allParts += $tmpPath
    Write-Host ("  Part $i saved: " + $tmpPath)
}

Write-Host "[5] Upload " + $N_CHUNKS + " parts to remote..."
$t0 = Get-Date
for ($i = 0; $i -lt $N_CHUNKS; $i++) {
    $localPart = $allParts[$i]
    $remotePath = $REMOTE_DIR + "\part_$i.bin"
    Write-Host ("  Upload part $i (" + ((Get-Item $localPart).Length / 1KB).ToString('F0') + " KB)...") -NoNewline
    Copy-Item -Path $localPart -Destination $remotePath -ToSession $s
    Write-Host " done"
}
Write-Host ("Upload done in " + (((Get-Date) - $t0).TotalSeconds).ToString('F0') + "s")

Write-Host "[6] Combine parts into ZIP on remote..."
Invoke-Command -Session $s -ScriptBlock {
    param($rd, $n)
    $zipPath = Join-Path $rd "dp.zip"
    $fs = [IO.File]::Create($zipPath)
    for ($i = 0; $i -lt $n; $i++) {
        $partPath = Join-Path $rd ("part_$i.bin")
        $partBytes = [IO.File]::ReadAllBytes($partPath)
        $fs.Write($partBytes, 0, $partBytes.Length)
        Remove-Item $partPath -Force
    }
    $fs.Close()
    $z = (Get-Item $zipPath).Length / 1MB
    Write-Host ("  Combined ZIP: " + $z.ToString('F1') + " MB")
} -ArgumentList $REMOTE_DIR, $N_CHUNKS

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
    if ($c) { Stop-Process $c -Force; Start-Sleep 2; Write-Host "  Stopped old" }
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

# 清理本地临时文件
for ($i = 0; $i -lt $N_CHUNKS; $i++) {
    $tmpPath = Join-Path $env:TEMP ("dp3d_part_$i.bin")
    if (Test-Path $tmpPath) { Remove-Item $tmpPath -Force }
}

Remove-PSSession $s
$el = ((Get-Date)-$t0).TotalSeconds
Write-Host "=== DONE in " + $el.ToString('F0') + "s ==="
