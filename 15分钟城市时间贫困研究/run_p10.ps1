$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONLEGACYWINDOWSSTDIO = 'utf-8'

$script = Join-Path $PSScriptRoot "v2_real_data\p10_fig11_building_aoi.py"
& python $script 2>&1 | Out-File -Encoding UTF8 (Join-Path $PSScriptRoot "p10_output.log")
