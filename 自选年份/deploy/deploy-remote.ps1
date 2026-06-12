# ================================================================
# deploy-remote.ps1 - Remote deployment script
# Run: powershell -File C:\Users\Administrator\Desktop\deploy-remote.ps1
# ================================================================

param(
    [string]$ServerIP = "64.90.0.78",
    [string]$Username = "Administrator",
    [string]$ApiDir = "C:\www\15min\api",
    [string]$StaticDir = "C:\www\15min\static",
    [string]$LogDir = "C:\www\15min\logs",
    [string]$ApiPort = "8765"
)

$ErrorActionPreference = "Stop"

# Auto-detect ZIP path
$ZipPath = $null
$searchPaths = @(
    "e:\xicha gis\self-year\deploy_package.zip",
    "e:\xicha gis 智能定位\自选年份\deploy_package.zip"
)
foreach ($p in $searchPaths) {
    if (Test-Path $p) { $ZipPath = $p; break }
}
if (-not $ZipPath) {
    Write-Host "[ERROR] deploy_package.zip not found" -ForegroundColor Red
    Write-Host "Searched:" -ForegroundColor Yellow
    foreach ($p in $searchPaths) { Write-Host "  $p" -ForegroundColor DarkGray }
    exit 1
}

# Auto-detect Nginx conf
$NginxConfPath = $null
$confSearch = @(
    "e:\xicha gis\self-year\15min-subdomain.conf",
    "e:\xicha gis 智能定位\自选年份\deploy\15min-subdomain.conf"
)
foreach ($p in $confSearch) {
    if (Test-Path $p) { $NginxConfPath = $p; break }
}
if (-not $NginxConfPath) {
    Write-Host "[ERROR] 15min-subdomain.conf not found" -ForegroundColor Red
    exit 1
}

$zipMB = [math]::Round((Get-Item $ZipPath).Length / 1MB, 1)

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " 15min Urban Accessibility - Remote Deployment" -ForegroundColor Cyan
Write-Host " Server: $ServerIP  |  ZIP: $zipMB MB" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Credentials
Write-Host "[INPUT] Enter server password for $Username@$ServerIP" -ForegroundColor Yellow
$pass = Read-Host -AsSecureString "Password"
$cred = New-Object System.Management.Automation.PSCredential("$Username@$ServerIP", $pass)

# Connect
Write-Host "[CONNECT] Establishing session..." -ForegroundColor Yellow
try {
    $session = New-PSSession -ComputerName $ServerIP -Credential $cred `
        -Port 5986 -Authentication Negotiate -ErrorAction Stop
    Write-Host "[OK] Session established (ID=$($session.Id))" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Cannot connect: $_" -ForegroundColor Red
    exit 1
}

# Step 1: Create dirs
Write-Host ""
Write-Host "[1/5] Creating directories on server..." -ForegroundColor Yellow
Invoke-Command -Session $session -ScriptBlock {
    param($ApiDir, $StaticDir, $LogDir)
    $dirs = @($ApiDir, $StaticDir, $LogDir, "$ApiDir\network_output")
    foreach ($d in $dirs) {
        if (-not (Test-Path $d)) {
            New-Item -ItemType Directory -Path $d -Force | Out-Null
        }
    }
} -ArgumentList $ApiDir, $StaticDir, $LogDir
Write-Host "[OK] Directories ready" -ForegroundColor Green

# Step 2: Upload ZIP via SMB (more reliable)
Write-Host ""
Write-Host "[2/5] Uploading deploy_package.zip ($zipMB MB)..." -ForegroundColor Yellow
$localZipName = Split-Path $ZipPath -Leaf
$destPath = "\\$ServerIP\c$\Users\Administrator\Desktop\$localZipName"
try {
    Copy-Item -Path $ZipPath -Destination $destPath -Force -ErrorAction Stop
    Write-Host "[OK] ZIP uploaded via SMB" -ForegroundColor Green
} catch {
    Write-Host "[WARN] SMB copy failed, trying via session..." -ForegroundColor Yellow
    $bytes = [System.IO.File]::ReadAllBytes($ZipPath)
    Invoke-Command -Session $session -ScriptBlock {
        param($bytes, $dest)
        [System.IO.File]::WriteAllBytes($dest, $bytes)
    } -ArgumentList $bytes, "$env:TEMP\deploy.zip"
    Write-Host "[OK] ZIP uploaded via session" -ForegroundColor Green
}

# Step 3: Upload Nginx config via SMB
Write-Host ""
Write-Host "[3/5] Uploading Nginx config..." -ForegroundColor Yellow
$localConfName = Split-Path $NginxConfPath -Leaf
$destConfPath = "\\$ServerIP\c$\Users\Administrator\Desktop\$localConfName"
try {
    Copy-Item -Path $NginxConfPath -Destination $destConfPath -Force -ErrorAction Stop
    Write-Host "[OK] Config uploaded via SMB" -ForegroundColor Green
} catch {
    Write-Host "[WARN] SMB copy failed, trying via session..." -ForegroundColor Yellow
    $confBytes = [System.IO.File]::ReadAllBytes($NginxConfPath)
    Invoke-Command -Session $session -ScriptBlock {
        param($bytes, $dest)
        [System.IO.File]::WriteAllBytes($dest, $bytes)
    } -ArgumentList $confBytes, "$env:TEMP\subdomain.conf"
    Write-Host "[OK] Config uploaded via session" -ForegroundColor Green
}

# Step 4: Server-side extraction and setup
Write-Host ""
Write-Host "[4/5] Server-side: extract + configure + start..." -ForegroundColor Yellow
Invoke-Command -Session $session -ScriptBlock {
    param($ApiDir, $StaticDir, $LogDir, $ApiPort, $NginxConfPath)

    # Extract ZIP
    Write-Host "  Extracting ZIP..." -ForegroundColor DarkGray
    Expand-Archive -Path "$env:TEMP\deploy.zip" -DestinationPath "C:\" -Force -ErrorAction Stop

    # Move files to correct locations
    if (Test-Path "C:\www\15min\network_output") {
        Copy-Item -Path "C:\www\15min\network_output\*" -Destination "$ApiDir\" -Force
    }
    if (Test-Path "C:\www\15min\city_twin_output") {
        Copy-Item -Path "C:\www\15min\city_twin_output\*" -Destination "$StaticDir\" -Force
    }
    if (Test-Path "C:\www\15min\routing_api.py") {
        Copy-Item -Path "C:\www\15min\routing_api.py" -Destination "$ApiDir\" -Force
    }

    # Verify files
    Write-Host "  Verifying files..." -ForegroundColor DarkGray
    $checks = @(
        "$ApiDir\routing_api.py",
        "$ApiDir\network_output\network_graph.pkl",
        "$ApiDir\network_output\facility_locations.json",
        "$StaticDir\city_twin_viewer.html",
        "$StaticDir\base_data.json"
    )
    foreach ($f in $checks) {
        $ok = Test-Path $f
        if ($ok) {
            Write-Host "    OK      $f" -ForegroundColor Green
        } else {
            Write-Host "    MISSING $f" -ForegroundColor Red
        }
    }

    # Nginx setup
    Write-Host "  Setting up Nginx..." -ForegroundColor DarkGray
    $nginxDirs = @("C:\nginx", "C:\tools\nginx", "C:\Program Files\nginx", "C:\Server\nginx")
    $nginxDir = $null
    foreach ($nd in $nginxDirs) {
        if (Test-Path "$nd\conf\nginx.conf") { $nginxDir = $nd; break }
    }

    if ($nginxDir) {
        Write-Host "    Found Nginx: $nginxDir" -ForegroundColor DarkGray
        $mainConf = "$nginxDir\conf\nginx.conf"
        $content = Get-Content $mainConf -Raw
        if ($content -notmatch "15min-subdomain.conf") {
            Add-Content -Path $mainConf -Value "`ninclude conf/sites-available/15min-subdomain.conf;"
        }
        $destConf = "$nginxDir\conf\sites-available\15min-subdomain.conf"
        $sitesAvail = "$nginxDir\conf\sites-available"
        $sitesEnabled = "$nginxDir\conf\sites-enabled"
        if (-not (Test-Path $sitesAvail)) { New-Item -ItemType Directory -Path $sitesAvail -Force | Out-Null }
        if (-not (Test-Path $sitesEnabled)) { New-Item -ItemType Directory -Path $sitesEnabled -Force | Out-Null }
        Copy-Item -Path $NginxConfPath -Destination $destConf -Force
        $t = & "$nginxDir\nginx.exe" -t 2>&1
        Write-Host "    nginx -t: $t" -ForegroundColor DarkGray
        & "$nginxDir\nginx.exe" -s reload 2>$null
        Write-Host "    Nginx reloaded" -ForegroundColor Green
    } else {
        Write-Host "    [SKIP] Nginx not found" -ForegroundColor DarkGray
    }

    # Kill old FastAPI
    Write-Host "  Stopping old FastAPI..." -ForegroundColor DarkGray
    Get-NetTCPConnection -LocalPort $ApiPort -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Start-Sleep 2

    # Install Python deps
    Write-Host "  Checking Python deps..." -ForegroundColor DarkGray
    python -c "import fastapi,uvicorn,networkx" 2>$null
    if ($LASTEXITCODE -ne 0) {
        python -m pip install fastapi "uvicorn[standard]" networkx --quiet 2>$null
        Write-Host "    Deps installed" -ForegroundColor Green
    } else {
        Write-Host "    Deps ready" -ForegroundColor Green
    }

    # Start FastAPI
    Write-Host "  Starting FastAPI (port $ApiPort)..." -ForegroundColor DarkGray
    $logFile = "$LogDir\api.log"
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
    Start-Process -WindowStyle Hidden python `
        -ArgumentList "-m uvicorn routing_api:app --host 127.0.0.1 --port $ApiPort" `
        -WorkingDirectory $ApiDir -RedirectStandardOutput $logFile

    Start-Sleep 6

    # Verify API
    Write-Host "  Verifying API..." -ForegroundColor DarkGray
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$ApiPort/" -UseBasicParsing -TimeoutSec 8
        Write-Host "    /         HTTP $($r.StatusCode)" -ForegroundColor Green
    } catch {
        Write-Host "    /         no response (still starting)" -ForegroundColor Yellow
    }
    try {
        $r2 = Invoke-WebRequest -Uri "http://127.0.0.1:$ApiPort/api/stats" -UseBasicParsing -TimeoutSec 8
        Write-Host "    /api/stats HTTP $($r2.StatusCode)" -ForegroundColor Green
    } catch {
        Write-Host "    /api/stats no response" -ForegroundColor Yellow
    }

} -ArgumentList $ApiDir, $StaticDir, $LogDir, $ApiPort, $NginxConfPath

# Step 5: Cleanup
Write-Host ""
Write-Host "[5/5] Cleanup..." -ForegroundColor Yellow
Invoke-Command -Session $session -ScriptBlock {
    Remove-Item "$env:TEMP\deploy.zip" -Force -ErrorAction SilentlyContinue
    Remove-Item "$env:TEMP\subdomain.conf" -Force -ErrorAction SilentlyContinue
}
Remove-PSSession $session
Write-Host "[OK] Session closed" -ForegroundColor Green

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Test now:" -ForegroundColor White
Write-Host "  http://64.90.0.78/" -ForegroundColor Cyan
Write-Host "  http://64.90.0.78/api/stats" -ForegroundColor Cyan
Write-Host ""
Write-Host "After DNS propagates:" -ForegroundColor Yellow
Write-Host "  https://15min.globalreviewops.xyz/" -ForegroundColor Cyan
Write-Host "  https://15min.globalreviewops.xyz/api/stats" -ForegroundColor Cyan
Write-Host ""
Write-Host "SSL cert:" -ForegroundColor Yellow
Write-Host "  certbot --nginx -d 15min.globalreviewops.xyz" -ForegroundColor DarkGray
Write-Host ""
