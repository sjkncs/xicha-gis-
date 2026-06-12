$ErrorActionPreference = "Stop"
$REMOTE_HOST = "64.90.0.78"
$PORT = 5985
$USER = "Administrator"
$PASS = "asR84SiRzqhbDvZF"
$ZIP_PATH = "E:\xicha gis 智能定位\自选年份\deploy_3d.zip"
$CHUNK_KB = 2048
$REMOTE_B64_DIR = "C:\dp3d_work"

Write-Host "=== 3D 可视化部署脚本 ==="
Write-Host "ZIP: $ZIP_PATH"
Write-Host "文件大小: $([math]::Round((Get-Item $ZIP_PATH).Length / 1MB, 1)) MB"

# 建立 WinRM 会话
Write-Host "[1] 建立 WinRM 会话..."
$secPass = ConvertTo-SecureString $PASS -AsPlainText -Force
$cred = New-Object PSCredential($USER, $secPass)
$s = New-PSSession -ComputerName $REMOTE_HOST -Port $PORT -Credential $cred -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Write-Host "会话建立成功: $($s.Id)"

# 在远程执行所有操作
Invoke-Command -Session $s -ScriptBlock {
    param($CHUNK_KB, $REMOTE_B64_DIR)

    $ErrorActionPreference = "Stop"
    Write-Host "[2] 创建工作目录..."
    if (Test-Path $REMOTE_B64_DIR) { Remove-Item $REMOTE_B64_DIR -Recurse -Force }
    New-Item -ItemType Directory -Path $REMOTE_B64_DIR -Force | Out-Null

    Write-Host "[3] 清空旧静态文件..."
    if (Test-Path "C:\www\15min\static") {
        Remove-Item "C:\www\15min\static\*" -Recurse -Force
    } else {
        New-Item -ItemType Directory -Path "C:\www\15min\static" -Force | Out-Null
    }

    Write-Host "初始化完成"
} -ArgumentList $CHUNK_KB, $REMOTE_B64_DIR

Write-Host "[4] 读取本地 ZIP 并 Base64 编码..."
$rawBytes = [IO.File]::ReadAllBytes($ZIP_PATH)
$b64String = [Convert]::ToBase64String($rawBytes)
Write-Host "Base64 长度: $([math]::Round($b64String.Length / 1MB, 1)) MB"

# 分块传输
$nChunks = [math]::Ceiling($b64String.Length / ($CHUNK_KB * 1024))
Write-Host "[5] 分块传输 ($nChunks 块, 每块 $CHUNK_KB KB)..."
$t0 = Get-Date

Invoke-Command -Session $s -ScriptBlock {
    param($b64String, $nChunks, $CHUNK_KB, $REMOTE_B64_DIR)
    $ErrorActionPreference = "Stop"

    $chunkSize = $CHUNK_KB * 1024
    $tmpFile = Join-Path $REMOTE_B64_DIR "all.b64"

    for ($i = 0; $i -lt $nChunks; $i++) {
        $start = $i * $chunkSize
        $len = [math]::Min($chunkSize, $b64String.Length - $start)
        $chunk = $b64String.Substring($start, $len)

        $encoded = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($chunk))
        $partFile = Join-Path $REMOTE_B64_DIR "part_$('{0:D3}' -f $i).b64"
        [IO.File]::WriteAllText($partFile, $encoded, [Text.Encoding]::ASCII)

        $pct = ($i + 1) / $nChunks * 100
        Write-Host ("  [{0}/{1}] {2:F0}%   " -f ($i+1), $nChunks, $pct)
    }

    Write-Host "[6] 合并分块并解码为 ZIP..."
    $allEncoded = ""
    for ($i = 0; $i -lt $nChunks; $i++) {
        $partFile = Join-Path $REMOTE_B64_DIR "part_$('{0:D3}' -f $i).b64"
        $allEncoded += [IO.File]::ReadAllText($partFile, [Text.Encoding]::ASCII)
    }

    $zipBytes = [Convert]::FromBase64String($allEncoded)
    $zipPath = Join-Path $REMOTE_B64_DIR "deploy.zip"
    [IO.File]::WriteAllBytes($zipPath, $zipBytes)
    Write-Host "ZIP 大小: $([math]::Round(([IO.File]::ReadAllBytes($zipPath).Length / 1MB), 1)) MB"

    Write-Host "[7] 解压到 C:\www\15min\static..."
    [IO.Compression.ZipFile]::ExtractToDirectory($zipPath, "C:\www\15min\static")
    Write-Host "解压完成"

    Write-Host "[8] 验证文件..."
    Get-ChildItem "C:\www\15min\static" | ForEach-Object {
        Write-Host ("  {0,-35} {1:N1} MB" -f $_.Name, ($_.Length / 1MB))
    }

    Write-Host "[9] 重启 Caddy..."
    $caddyProc = Get-Process caddy -ErrorAction SilentlyContinue
    if ($caddyProc) {
        Stop-Process $caddyProc -Force
        Start-Sleep 2
        Write-Host "Caddy 已停止"
    }
    Start-Process "C:\ProgramData\caddy\caddy.exe" -ArgumentList "run","--config","C:\globalreviewops\Caddyfile","--adapter","caddyfile" -NoNewWindow -PassThru | Out-Null
    Start-Sleep 3
    $newCaddy = Get-Process caddy -ErrorAction SilentlyContinue
    if ($newCaddy) { Write-Host "Caddy 已启动 (PID: $($newCaddy.Id))" }

    Write-Host "[10] 清理临时文件..."
    Remove-Item $REMOTE_B64_DIR -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "清理完成"

    $elapsed = ((Get-Date) - $t0).TotalSeconds
    Write-Host "=== 部署完成! 耗时: $([math]::Round($elapsed, 0))s ==="

} -ArgumentList $b64String, $nChunks, $CHUNK_KB, $REMOTE_B64_DIR

# 关闭会话
Remove-PSSession $s
Write-Host "会话已关闭"
