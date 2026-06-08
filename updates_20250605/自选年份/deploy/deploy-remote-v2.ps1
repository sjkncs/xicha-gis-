# ================================================================
# deploy-remote-v2.ps1
# Deploy the 15-minute GIS site to an isolated Windows subdomain stack.
#
# Run:
#   powershell -ExecutionPolicy Bypass -File "E:\xicha gis 智能定位\自选年份\deploy\deploy-remote-v2.ps1"
#
# Notes:
#   - Requires WinRM access to the target server.
#   - Does not store passwords. You will be prompted for the server password.
#   - Does not touch the mother review app on 127.0.0.1:8080.
# ================================================================

param(
    [string]$ServerIP = "64.90.0.18",
    [string]$Username = "Administrator",
    [string]$Subdomain = "15min.globalreviewops.xyz",
    [string]$BaseDir = "C:\www\15min",
    [string]$CaddyRoot = "C:\globalreviewops",
    [string]$ApiPort = "8765",
    [pscredential]$Credential,
    [switch]$SkipCaddyRestart
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ScriptDir = if ($PSScriptRoot) {
    (Resolve-Path -LiteralPath $PSScriptRoot).Path
} else {
    (Resolve-Path -LiteralPath (Split-Path -Parent $MyInvocation.MyCommand.Path)).Path
}
$ProjectDir = (Resolve-Path -LiteralPath (Join-Path $ScriptDir "..")).Path

function Resolve-FirstExistingPath {
    param([string[]]$Candidates, [string]$Label)
    foreach ($candidate in $Candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    Write-Host "[ERROR] $Label not found" -ForegroundColor Red
    Write-Host "ScriptDir:  $ScriptDir" -ForegroundColor Yellow
    Write-Host "ProjectDir: $ProjectDir" -ForegroundColor Yellow
    Write-Host "Searched:" -ForegroundColor Yellow
    foreach ($candidate in $Candidates) {
        Write-Host "  $candidate" -ForegroundColor DarkGray
    }
    exit 1
}

$ZipPath = Resolve-FirstExistingPath @(
    (Join-Path $ProjectDir "deploy_package.zip"),
    (Join-Path $ScriptDir "deploy_package.zip"),
    (Join-Path (Get-Location).Path "deploy_package.zip")
) "deploy_package.zip"

$zipMB = [math]::Round((Get-Item -LiteralPath $ZipPath).Length / 1MB, 1)

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " 15min GIS subdomain deployment" -ForegroundColor Cyan
Write-Host " Server:    $ServerIP" -ForegroundColor White
Write-Host " Subdomain: $Subdomain" -ForegroundColor White
Write-Host " Package:   $ZipPath ($zipMB MB)" -ForegroundColor DarkGray
Write-Host " BaseDir:   $BaseDir" -ForegroundColor DarkGray
Write-Host " API Port:  $ApiPort" -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[0/7] Checking WinRM..." -ForegroundColor Yellow
Test-WSMan -ComputerName $ServerIP | Out-Null
Write-Host "[OK] WinRM is reachable" -ForegroundColor Green

if (-not $Credential) {
    $Credential = Get-Credential -UserName $Username -Message "Enter Windows server password for $Username@$ServerIP"
}

$Session = New-PSSession -ComputerName $ServerIP -Credential $Credential
try {
    $RemoteZip = "C:\Users\$Username\Desktop\deploy_package_15min.zip"
    $ApiDir = Join-Path $BaseDir "api"
    $StaticDir = Join-Path $BaseDir "static"
    $LogDir = Join-Path $BaseDir "logs"

    Write-Host ""
    Write-Host "[1/7] Preparing isolated directories..." -ForegroundColor Yellow
    Invoke-Command -Session $Session -ScriptBlock {
        param($BaseDir, $ApiDir, $StaticDir, $LogDir)
        New-Item -ItemType Directory -Force -Path $BaseDir, $ApiDir, $StaticDir, $LogDir, (Join-Path $ApiDir "network_output") | Out-Null
    } -ArgumentList $BaseDir, $ApiDir, $StaticDir, $LogDir
    Write-Host "[OK] Directories ready" -ForegroundColor Green

    Write-Host ""
    Write-Host "[2/7] Uploading deployment package..." -ForegroundColor Yellow
    Invoke-Command -Session $Session -ScriptBlock {
        param($RemoteZip)
        Remove-Item -LiteralPath $RemoteZip -Force -ErrorAction SilentlyContinue
    } -ArgumentList $RemoteZip
    Copy-Item -LiteralPath $ZipPath -Destination $RemoteZip -ToSession $Session -Force
    Write-Host "[OK] Package uploaded" -ForegroundColor Green

    Write-Host ""
    Write-Host "[3/7] Extracting and laying out files..." -ForegroundColor Yellow
    Invoke-Command -Session $Session -ScriptBlock {
        param($RemoteZip, $BaseDir, $ApiDir, $StaticDir)
        Add-Type -AssemblyName System.IO.Compression.FileSystem

        $ExtractDir = Join-Path $BaseDir "_incoming"
        if (Test-Path -LiteralPath $ExtractDir) { Remove-Item -LiteralPath $ExtractDir -Recurse -Force }
        New-Item -ItemType Directory -Force -Path $ExtractDir | Out-Null
        [System.IO.Compression.ZipFile]::ExtractToDirectory($RemoteZip, $ExtractDir)

        $routing = Get-ChildItem -LiteralPath $ExtractDir -Recurse -File -Filter "routing_api.py" | Select-Object -First 1
        if (-not $routing) { throw "routing_api.py not found in package" }
        Copy-Item -LiteralPath $routing.FullName -Destination (Join-Path $ApiDir "routing_api.py") -Force

        $networkOut = Join-Path $ApiDir "network_output"
        New-Item -ItemType Directory -Force -Path $networkOut | Out-Null
        $networkNames = @(
            "network_graph.pkl",
            "network_nodes.json",
            "network_edges.json",
            "facility_locations.json"
        )
        foreach ($name in $networkNames) {
            $f = Get-ChildItem -LiteralPath $ExtractDir -Recurse -File -Filter $name | Select-Object -First 1
            if ($f) { Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $networkOut $name) -Force }
        }

        Get-ChildItem -LiteralPath $ExtractDir -Recurse -File |
            Where-Object {
                $_.Name -ne "routing_api.py" -and
                $_.Name -notin $networkNames -and
                $_.Extension -ne ".pkl"
            } |
            ForEach-Object {
                Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $StaticDir $_.Name) -Force
            }

        $viewer = Join-Path $StaticDir "city_twin_viewer.html"
        if (Test-Path -LiteralPath $viewer) {
            Copy-Item -LiteralPath $viewer -Destination (Join-Path $StaticDir "index.html") -Force
        }

        Remove-Item -LiteralPath $ExtractDir -Recurse -Force
        Remove-Item -LiteralPath $RemoteZip -Force -ErrorAction SilentlyContinue

        $required = @(
            (Join-Path $ApiDir "routing_api.py"),
            (Join-Path $networkOut "network_graph.pkl"),
            (Join-Path $networkOut "network_nodes.json"),
            (Join-Path $networkOut "network_edges.json"),
            (Join-Path $networkOut "facility_locations.json"),
            (Join-Path $StaticDir "city_twin_viewer.html"),
            (Join-Path $StaticDir "index.html")
        )
        foreach ($path in $required) {
            if (-not (Test-Path -LiteralPath $path)) { throw "Missing deployed file: $path" }
        }
    } -ArgumentList $RemoteZip, $BaseDir, $ApiDir, $StaticDir
    Write-Host "[OK] Files deployed" -ForegroundColor Green

    Write-Host ""
    Write-Host "[4/7] Installing isolated Python runtime dependencies..." -ForegroundColor Yellow
    Invoke-Command -Session $Session -ScriptBlock {
        param($BaseDir)
        $VenvDir = Join-Path $BaseDir ".venv"
        $Python = Join-Path $VenvDir "Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $Python)) {
            python -m venv $VenvDir
        }
        & $Python -m pip install --upgrade pip --quiet
        & $Python -m pip install fastapi uvicorn networkx numpy scipy pandas --quiet
    } -ArgumentList $BaseDir
    Write-Host "[OK] Dependencies ready" -ForegroundColor Green

    Write-Host ""
    Write-Host "[5/7] Starting isolated FastAPI watchdog..." -ForegroundColor Yellow
    Invoke-Command -Session $Session -ScriptBlock {
        param($BaseDir, $ApiDir, $LogDir, $ApiPort)
        $WatchdogPath = Join-Path $BaseDir "run_15min_api_watchdog.ps1"
        $Python = Join-Path $BaseDir ".venv\Scripts\python.exe"
        $ApiOutLog = Join-Path $LogDir "api.out.log"
        $ApiErrLog = Join-Path $LogDir "api.err.log"
        $WatchdogLog = Join-Path $LogDir "watchdog.log"

        $script = @"
`$ErrorActionPreference = "Continue"
`$existing = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $ApiPort -State Listen -ErrorAction SilentlyContinue
if (`$existing) {
    "`${(Get-Date).ToString('s')} API already listening on $ApiPort" | Add-Content -LiteralPath "$WatchdogLog"
    exit 0
}
Set-Location -LiteralPath "$ApiDir"
Start-Process -FilePath "$Python" -ArgumentList @("-m","uvicorn","routing_api:app","--host","127.0.0.1","--port","$ApiPort") -WorkingDirectory "$ApiDir" -WindowStyle Hidden -RedirectStandardOutput "$ApiOutLog" -RedirectStandardError "$ApiErrLog"
"`${(Get-Date).ToString('s')} API start requested on $ApiPort" | Add-Content -LiteralPath "$WatchdogLog"
"@
        Set-Content -LiteralPath $WatchdogPath -Value $script -Encoding UTF8

        $taskName = "GlobalReviewOps15minApi"
        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$WatchdogPath`""
        $triggerStartup = New-ScheduledTaskTrigger -AtStartup
        $triggerWatchdog = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
        $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($triggerStartup, $triggerWatchdog) -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null

        Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $ApiPort -State Listen -ErrorAction SilentlyContinue |
            ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
        Start-ScheduledTask -TaskName $taskName
        Start-Sleep -Seconds 8

        $code = & curl.exe -s -o NUL -w '%{http_code}' --max-time 10 "http://127.0.0.1:$ApiPort/api/stats"
        if ($code -ne "200") {
            throw "GIS API health check failed on port $ApiPort, status=$code"
        }
    } -ArgumentList $BaseDir, $ApiDir, $LogDir, $ApiPort
    Write-Host "[OK] GIS API is healthy on 127.0.0.1:$ApiPort" -ForegroundColor Green

    Write-Host ""
    Write-Host "[6/7] Ensuring Caddy subdomain route..." -ForegroundColor Yellow
    Invoke-Command -Session $Session -ScriptBlock {
        param($Subdomain, $StaticDir, $ApiPort, $CaddyRoot, $SkipCaddyRestart)
        $Caddy = Join-Path $CaddyRoot "caddy\caddy.exe"
        $Caddyfile = Join-Path $CaddyRoot "Caddyfile"
        if (-not (Test-Path -LiteralPath $Caddy)) { throw "Caddy executable not found: $Caddy" }
        if (-not (Test-Path -LiteralPath $Caddyfile)) { throw "Caddyfile not found: $Caddyfile" }

        $block = @"

# BEGIN 15MIN_SUBDOMAIN_MANAGED
$Subdomain {
    encode gzip zstd
    root * $($StaticDir -replace '\\','/')

    handle /api/* {
        reverse_proxy 127.0.0.1:$ApiPort
    }

    handle {
        try_files {path} /index.html
        file_server
    }
}
# END 15MIN_SUBDOMAIN_MANAGED
"@

        $current = Get-Content -LiteralPath $Caddyfile -Raw
        if ($current -notmatch [regex]::Escape($Subdomain)) {
            Add-Content -LiteralPath $Caddyfile -Value $block -Encoding UTF8
        }

        $validation = & $Caddy validate --config $Caddyfile 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0 -and $validation -notmatch "Valid configuration") {
            throw "Caddy validation failed: $validation"
        }

        if (-not $SkipCaddyRestart) {
            Get-Process caddy -ErrorAction SilentlyContinue | Stop-Process -Force
            Start-Process -FilePath $Caddy -ArgumentList "run --config `"$Caddyfile`"" -WorkingDirectory $CaddyRoot -WindowStyle Hidden
            Start-Sleep -Seconds 5
        }
    } -ArgumentList $Subdomain, $StaticDir, $ApiPort, $CaddyRoot, [bool]$SkipCaddyRestart
    Write-Host "[OK] Caddy subdomain route is configured" -ForegroundColor Green

    Write-Host ""
    Write-Host "[7/7] Final non-invasive checks..." -ForegroundColor Yellow
    $Final = Invoke-Command -Session $Session -ScriptBlock {
        param($ApiPort)
        [pscustomobject]@{
            GisApi = (& curl.exe -s -o NUL -w '%{http_code}' --max-time 10 "http://127.0.0.1:$ApiPort/api/stats")
            MotherApp = (& curl.exe -s -o NUL -w '%{http_code}' --max-time 10 "http://127.0.0.1:8080/api/unified/status?compact=true")
            CsAgent = (& curl.exe -s -o NUL -w '%{http_code}' --max-time 10 "http://127.0.0.1:8091/api/health")
            Listeners = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
                Where-Object { $_.LocalPort -in @(80,443,8080,8091,[int]$ApiPort) } |
                Sort-Object LocalPort |
                Select-Object LocalAddress,LocalPort,OwningProcess
        }
    } -ArgumentList $ApiPort

    $Final | Format-List
    if ($Final.GisApi -ne "200") { throw "GIS API final check failed" }
    if ($Final.MotherApp -ne "200") { throw "Mother app final check failed" }
    if ($Final.CsAgent -ne "200") { throw "CS agent final check failed" }

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " DEPLOYMENT COMPLETE" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "Origin is ready. Add DNS before public access:" -ForegroundColor White
    Write-Host "  Type: A" -ForegroundColor Cyan
    Write-Host "  Name: 15min" -ForegroundColor Cyan
    Write-Host "  Value: $ServerIP" -ForegroundColor Cyan
    Write-Host "Then open:" -ForegroundColor White
    Write-Host "  https://$Subdomain/" -ForegroundColor Cyan
    Write-Host "  https://$Subdomain/api/stats" -ForegroundColor Cyan
}
finally {
    if ($Session) {
        Remove-PSSession $Session
    }
}
