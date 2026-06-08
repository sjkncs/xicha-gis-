$base = "e:\xicha gis 智能定位\自选年份\baidu_streetview"
Write-Output "=== 归档结构 ==="
Get-ChildItem $base -Directory | ForEach-Object {
    $d = $_
    $cnt = (Get-ChildItem $d.FullName -File -Recurse | Measure-Object).Count
    Write-Output "$($d.Name) -> $cnt files"
}
Write-Output ""
Write-Output "=== 南山区各街道 ==="
$ns = Join-Path $base "南山区"
if (Test-Path $ns) {
    Get-ChildItem $ns -Directory | ForEach-Object {
        $t = $_
        $cnt2 = (Get-ChildItem $t.FullName -Directory | Measure-Object).Count
        Write-Output "  $($t.Name) -> $cnt2 社区"
    }
}
Write-Output ""
Write-Output "=== manifest.csv 统计 ==="
$m = Join-Path $base "manifest.csv"
if (Test-Path $m) {
    $rows = Import-Csv $m
    Write-Output "总行数: $($rows.Count)"
    $districts = $rows | Group-Object district | ForEach-Object { "$($_.Name)=$($_.Count)" }
    Write-Output "各区: $($districts -join ', ')"
}
