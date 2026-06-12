$ErrorActionPreference = "Continue"
$srv = "64.90.0.78"
$prt = 5985
$usr = "Administrator"
$pwd = "asR84SiRzqhbDvZF"
$lclZip = "E:\xicha gis 智能定位\自选年份\deploy_3d.zip"
$rbtDir = "C:\dp3d_work"

Write-Host "[1] 建立会话..."
$sec = ConvertTo-SecureString $pwd -AsPlainText -Force
$crd = New-Object PSCredential($usr, $sec)
$s = New-PSSession -ComputerName $srv -Port $prt -Credential $crd -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Write-Host "会话 ID: $($s.Id)"

Write-Host "[2] 创建远程目录..."
Invoke-Command -Session $s -ScriptBlock {
    if (Test-Path $using:rbtDir) { Remove-Item $using:rbtDir -Recurse -Force }
    New-Item -ItemType Directory -Path $using:rbtDir -Force | Out-Null
    if (!(Test-Path "C:\www\15min\static")) {
        New-Item -ItemType Directory -Path "C:\www\15min\static" -Force | Out-Null
    }
    Remove-Item "C:\www\15min\static\*" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "目录就绪"
}

Write-Host "[3] 上传 ZIP (Copy-Item)..."
$t0 = Get-Date
Copy-Item -Path $lclZip -Destination "$rbtDir\dp.zip" -ToSession $s
$elapsed = ((Get-Date) - $t0).TotalSeconds
$sz = Invoke-Command -Session $s -ScriptBlock { (Get-Item "$using:rbtDir\dp.zip").Length / 1MB }
Write-Host "上传完成: ${sz} MB, 耗时 ${elapsed}s"

Write-Host "[4] 解压..."
Invoke-Command -Session $s -ScriptBlock {
    Write-Host "  解码中..."
    [IO.Compression.ZipFile]::ExtractToDirectory("$using:rbtDir\dp.zip", "C:\www\15min\static")
    Write-Host "  解压完成"
    Get-ChildItem "C:\www\15min\static" | ForEach-Object {
        Write-Host ("  " + $_.Name + " (" + [math]::Round($_.Length/1MB,1) + " MB)")
    }
}

Write-Host "[5] 重启 Caddy..."
Invoke-Command -Session $s -ScriptBlock {
    $c = Get-Process caddy -ErrorAction SilentlyContinue
    if ($c) { Stop-Process $c -Force; Start-Sleep 2; Write-Host "Caddy stopped" }
    Start-Process "C:\ProgramData\caddy\caddy.exe" -ArgumentList "run","--config","C:\globalreviewops\Caddyfile","--adapter","caddyfile" -NoNewWindow -PassThru | Out-Null
    Start-Sleep 3
    $n = Get-Process caddy -ErrorAction SilentlyContinue
    Write-Host ("Caddy PID: " + $n.Id)
}

Write-Host "[6] 清理..."
Invoke-Command -Session $s -ScriptBlock {
    Remove-Item $using:rbtDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "清理完成"
}

Remove-PSSession $s
Write-Host "=== 部署完成 ==="
