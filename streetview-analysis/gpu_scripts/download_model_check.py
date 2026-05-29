# -*- coding: utf-8 -*-
"""GPU 服务器模型下载 + 数据检查"""
import paramiko
from pathlib import Path
import time

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"
REMOTE = "/root/gis_project"
VENV = "/root/venv"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20, allow_agent=False, look_for_keys=False)
    return c

def run(c, cmd, timeout=15):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace"), stderr.read().decode("utf-8", errors="replace")

def main():
    c = ssh()
    print("=" * 50)
    print("Step 1: Download SegFormer B3 model")
    print("=" * 50)

    # 先用 heredoc 写一个简洁的下载脚本
    dl_script = r"""#!/bin/bash
set -e
export HF_ENDPOINT="https://hf-mirror.com"
export HF_HUB_ENABLE_HF_TRANSFER=1
MODEL_DIR="/autodl-pub/data/models"
LOG="/root/gis_project/logs/download_models.log"
mkdir -p "$MODEL_DIR" "$LOG" /root/gis_project/logs

echo "$(date): 开始下载 SegFormer B3" >> "$LOG"
/root/venv/bin/python -c "
import warnings; warnings.filterwarnings('ignore')
from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation
print('下载 processor...')
processor = AutoImageProcessor.from_pretrained('nvidia/mit-b3', cache_dir='/autodl-pub/data/models')
print('下载 model...')
model = AutoModelForSemanticSegmentation.from_pretrained('nvidia/mit-b3', cache_dir='/autodl-pub/data/models')
print('SegFormer B3 下载完成!')
" 2>&1 | tee -a "$LOG"

echo "$(date): 下载完成" >> "$LOG"
touch /root/gis_project/gpu_scripts/MODELS_READY
"""
    print("Writing download script...")
    escaped = dl_script.replace("'", "'\"'\"'")
    cmd = f"cat > '{REMOTE}/gpu_scripts/download_segformer.sh' << 'ENDOFSCRIPT'\n{dl_script}\nENDOFSCRIPT"
    run(c, cmd, timeout=20)
    run(c, f"chmod +x {REMOTE}/gpu_scripts/download_segformer.sh")

    # 检查是否已有模型
    out, _ = run(c, f"find /autodl-pub/data/models -name 'config.json' -path '*mit-b3*' 2>/dev/null | head -3")
    if out.strip():
        print(f"Model already exists: {out.strip()}")
    else:
        print("Starting model download (background)...")
        out, _ = run(c, f"cd {REMOTE}/gpu_scripts && nohup bash download_segformer.sh > download_segformer.out 2>&1 &", timeout=10)
        print(f"Started. PID: {out.strip()}")
        print("Checking in 30 seconds...")

        time.sleep(30)
        out, _ = run(c, f"tail -10 {REMOTE}/logs/download_models.log 2>/dev/null")
        print(f"Progress:\n{out.strip()}")

        out, _ = run(c, f"ps aux | grep 'download_segformer' | grep -v grep | head -2")
        print(f"Process: {out.strip() or 'done or not found'}")

    # 检查全景图数量和大小
    print("\n" + "=" * 50)
    print("Step 2: Check panorama data")
    print("=" * 50)

    # 统计本地数据
    panorama_dir = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview")
    if panorama_dir.exists():
        all_jpg = list(panorama_dir.rglob("*.jpg")) + list(panorama_dir.rglob("*.png"))
        total_size = sum(f.stat().st_size for f in all_jpg if f.is_file())
        print(f"Local data: {len(all_jpg)} files, {total_size/1024**3:.2f} GB")
    else:
        print("Local panorama dir not found")
        all_jpg = []

    # 统计服务器数据
    out, _ = run(c, "find /autodl-pub/data -name '*.jpg' 2>/dev/null | wc -l")
    server_jpg = int(out.strip()) if out.strip().isdigit() else 0
    print(f"Server data: {server_jpg} JPG files")

    out, _ = run(c, "du -sh /autodl-pub/data/baidu_streetview 2>/dev/null || echo 'dir not found'")
    print(f"Server panorama dir size: {out.strip()}")

    # GPU 显存
    out, _ = run(c, "nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>&1")
    print(f"\nGPU: {out.strip()}")

    c.close()

    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    if all_jpg and server_jpg == 0:
        print(f"Action needed: Upload {len(all_jpg)} local files")
        print(f"  Total size: {total_size/1024**3:.2f} GB")
        print(f"  Target: root@connect.bjb1.seetacloud.com:/autodl-pub/data/baidu_streetview/")
    elif server_jpg > 0:
        print(f"Server has {server_jpg} files - ready for inference!")
    else:
        print("No local data found")

if __name__ == "__main__":
    main()
