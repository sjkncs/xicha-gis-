$r = Invoke-WebRequest -Uri "http://64.90.0.78/" -UseBasicParsing -TimeoutSec 10
Write-Host "Status: $($r.StatusCode)"
Write-Host "Length: $($r.Content.Length)"
Write-Host "Has city_twin_viewer: $($r.Content.Contains('city_twin_viewer'))"
Write-Host "Has 3D button: $($r.Content.Contains('3D') -or $r.Content.Contains('3d'))"
Write-Host "Has SVG: $($r.Content.Contains('<svg'))"

# Also check if the other static files are accessible
$r2 = Invoke-WebRequest -Uri "http://64.90.0.78/buildings_white_model.json" -UseBasicParsing -TimeoutSec 10
Write-Host ""
Write-Host "buildings_white_model.json: Status $($r2.StatusCode), Length $($r2.Content.Length)"

$r3 = Invoke-WebRequest -Uri "http://64.90.0.78/bev_voxel_3d.json" -UseBasicParsing -TimeoutSec 10
Write-Host "bev_voxel_3d.json: Status $($r3.StatusCode), Length $($r3.Content.Length)"
