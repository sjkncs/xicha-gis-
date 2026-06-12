#!/usr/bin/env python3
"""Deploy 3D visualization package to remote Windows server."""
import subprocess
import os
import tempfile

HOST = "64.90.0.78"
PORT = 5985
USER = "Administrator"
PASS = "asR84SiRzqhbDvZF"
LOCAL_ZIP = r"E:\xicha gis 智能定位\自选年份\deploy_3d.zip"
REMOTE_DIR = r"C:\dp3d_work"
WWW_DIR = r"C:\www\15min\static"

TEMP_RESULT = r"C:\Users\Administrator\dp_result.txt"

def ps_block(block_name, commands):
    print(f"\n{'='*60}\n{block_name}\n{'='*60}")
    code = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", commands],
        capture_output=True, text=True, timeout=600,
        encoding="utf-8", errors="replace"
    )
    # Write to temp file for reading
    try:
        with open(TEMP_RESULT, "w", encoding="utf-8") as f:
            f.write("STDOUT:\n" + (code.stdout or "(empty)"))
            f.write("\nSTDERR:\n" + (code.stderr or "(empty)"))
            f.write(f"\nRC={code.returncode}")
        # Read and display with error handling
        try:
            content = open(TEMP_RESULT, "r", encoding="utf-8").read()
            for line in content.split("\n"):
                try:
                    print(line)
                except UnicodeEncodeError:
                    print(line.encode("gbk", errors="replace").decode("gbk"))
        except Exception as e:
            print(f"Result file: {content[:500]}")
    except Exception as e:
        print(f"Block error: {e}")
    return code.returncode

# Step 1: Test connection
ps_block("Step 1: 连接测试", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Write-Host "会话ID=$($s.Id)"
Write-Host "会话状态=$($s.State)"
Invoke-Command -Session $s -ScriptBlock {{ Write-Host "远程Echo=成功" }}
Remove-PSSession $s
""")

# Step 2: Setup directories
ps_block("Step 2: 初始化目录", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Invoke-Command -Session $s -ScriptBlock {{
    if (Test-Path '{REMOTE_DIR}') {{ Remove-Item '{REMOTE_DIR}' -Recurse -Force }}
    New-Item -ItemType Directory -Path '{REMOTE_DIR}' -Force | Out-Null
    Write-Host "目录={REMOTE_DIR}"
    if (!(Test-Path '{WWW_DIR}')) {{ New-Item -ItemType Directory -Path '{WWW_DIR}' -Force | Out-Null }}
    Remove-Item '{WWW_DIR}\\*' -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "WWW=已清空"
}}
Remove-PSSession $s
""")

# Step 3: Upload ZIP
ps_block("Step 3: 上传ZIP", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Write-Host "Copy-Item开始"
Copy-Item -Path '{LOCAL_ZIP}' -Destination '{REMOTE_DIR}\\dp.zip' -ToSession $s
Write-Host "Copy-Item完成"
Invoke-Command -Session $s -ScriptBlock {{
    $sz = [math]::Round((Get-Item '{REMOTE_DIR}\\dp.zip').Length / 1MB, 1)
    Write-Host "远程=$sz MB"
}}
Remove-PSSession $s
""")

# Step 4: Diagnose
ps_block("Step 4: 诊断环境", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Invoke-Command -Session $s -ScriptBlock {{
    Write-Host "Caddy进程"
    Get-Process caddy -ErrorAction SilentlyContinue | ForEach-Object {{ Write-Host "PID=$($_.Id) Path=$($_.Path)" }}
    Write-Host "Caddy服务"
    Get-Service caddy -ErrorAction SilentlyContinue | ForEach-Object {{ Write-Host "Status=$($_.Status) Type=$($_.StartType)" }}
    Write-Host "搜索Caddy"
    Get-ChildItem -Path 'C:\\' -Filter 'caddy.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 5 FullName | ForEach-Object {{ Write-Host "Found=$($_.FullName)" }}
    Write-Host "WWW内容"
    Get-ChildItem '{WWW_DIR}' -ErrorAction SilentlyContinue | ForEach-Object {{ Write-Host "File=$($_.Name) Size=$($_.Length)" }}
}}
Remove-PSSession $s
""")

# Step 5: Extract with Add-Type
ps_block("Step 5: 解压(Add-Type方式)", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Invoke-Command -Session $s -ScriptBlock {{
    Write-Host "加载System.IO.Compression.FileSystem"
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    Write-Host "解压开始"
    [System.IO.Compression.ZipFile]::ExtractToDirectory('{REMOTE_DIR}\\dp.zip', '{WWW_DIR}')
    Write-Host "解压完成"
    Get-ChildItem '{WWW_DIR}' | ForEach-Object {{
        Write-Host "File=$($_.Name) MB=$([math]::Round($_.Length/1MB,1))"
    }}
}}
Remove-PSSession $s
""")

# Step 6: Find and restart Caddy
ps_block("Step 6: 启动Caddy", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Invoke-Command -Session $s -ScriptBlock {{
    $caddyExe = $null
    Get-ChildItem -Path 'C:\\' -Filter 'caddy.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 | ForEach-Object {{ $caddyExe = $_.FullName }}
    if ($caddyExe) {{
        Write-Host "找到Caddy=$caddyExe"
        $existing = Get-Process caddy -ErrorAction SilentlyContinue
        if ($existing) {{ Stop-Process $existing -Force; Start-Sleep 2; Write-Host "Caddy已停止" }}
        Write-Host "启动Caddy..."
        Start-Process $caddyExe -ArgumentList 'run','--config','C:\\globalreviewops\\Caddyfile','--adapter','caddyfile' -NoNewWindow -PassThru | Out-Null
        Start-Sleep 3
        $new = Get-Process caddy -ErrorAction SilentlyContinue
        if ($new) {{ Write-Host "Caddy启动 PID=$($new.Id)" }} else {{ Write-Host "Caddy启动失败" }}
    }} else {{
        Write-Host "Caddy未找到，尝试默认路径"
        $paths = @('C:\\ProgramData\\caddy\\caddy.exe','C:\\Program Files\\Caddy\\caddy.exe','C:\\caddy\\caddy.exe')
        foreach ($p in $paths) {{
            if (Test-Path $p) {{ Write-Host "默认路径=$p"; $caddyExe = $p; break }}
        }}
        if ($caddyExe) {{
            $existing = Get-Process caddy -ErrorAction SilentlyContinue
            if ($existing) {{ Stop-Process $existing -Force; Start-Sleep 2 }}
            Start-Process $caddyExe -ArgumentList 'run','--config','C:\\globalreviewops\\Caddyfile','--adapter','caddyfile' -NoNewWindow -PassThru | Out-Null
            Start-Sleep 3
            $new = Get-Process caddy -ErrorAction SilentlyContinue
            Write-Host "Caddy PID=$($new.Id)"
        }}
    }}
}}
Remove-PSSession $s
""")

# Step 7: Cleanup
ps_block("Step 7: 清理", f"""
$s = New-PSSession -ComputerName {HOST} -Port {PORT} -Credential (New-Object PSCredential('{USER}',(ConvertTo-SecureString '{PASS}' -AsPlainText -Force))) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
Invoke-Command -Session $s -ScriptBlock {{
    Remove-Item '{REMOTE_DIR}' -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "临时目录已清理"
}}
Remove-PSSession $s
""")

print(f"\n{'='*60}")
print("部署完成!")
print(f"访问: http://{HOST}/city_visualization_3d.html")
print(f"="*60)
