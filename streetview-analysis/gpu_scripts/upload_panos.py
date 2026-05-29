# -*- coding: utf-8 -*-
"""GPU服务器 - 分步上传 + 验证 + 启动推理"""
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
    sftp = c.open_sftp()

    print("=" * 50)

    # ===== 1. 验证模型下载 =====
    print("[1] Model download check...")
    out, _ = run(c, f"find {REMOTE}/models -name '*.safetensors' -o -name '*.bin' 2>/dev/null | head -5")
    print(f"  Model files: {out.strip()[:200] or 'none'}")
    out, _ = run(c, f"du -sh {REMOTE}/models 2>/dev/null || echo 'empty'")
    print(f"  Model size: {out.strip()}")

    # ===== 2. 确认 SegFormer 存在 =====
    out, _ = run(c, f"ls {REMOTE}/models/hub/models--nvidia--mit-b3/snapshots/ 2>/dev/null | head -5")
    print(f"  SegFormer B3: {out.strip() or 'NOT FOUND'}")
    if not out.strip():
        print("  Model not downloaded! Need to download first.")
        c.close()
        return

    # ===== 3. 创建数据目录 =====
    print("\n[2] Create data directories...")
    for d in [f"{REMOTE}/data", f"{REMOTE}/data/baidu_streetview"]:
        try:
            sftp.stat(d)
            print(f"  exists: {d}")
        except:
            sftp.mkdir(d)
            print(f"  created: {d}")

    # ===== 4. 上传全景图 =====
    print("\n[3] Upload panoramas...")
    local_pano = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview")
    all_files = []
    for ext in ["*.jpg", "*.JPG", "*.png", "*.PNG"]:
        all_files.extend(local_pano.rglob(ext))

    print(f"  Local files: {len(all_files)}")
    if not all_files:
        print("  No files found!")
        c.close()
        return

    total_mb = sum(f.stat().st_size for f in all_files) / 1024**2
    print(f"  Total size: {total_mb:.1f} MB")

    # 上传前50个作为测试
    test_files = all_files[:50]
    uploaded = 0
    failed = 0
    t_start = time.time()

    for f in test_files:
        try:
            # 确保可读
            if not f.is_file():
                continue
            # 目标路径
            remote_file = f"{REMOTE}/data/baidu_streetview/{f.name}"
            # 上传
            sftp.put(str(f), remote_file)
            uploaded += 1
            if uploaded % 10 == 0:
                print(f"  Uploaded {uploaded}/{len(test_files)}")
        except Exception as e:
            failed += 1
            if failed <= 3:
                print(f"  Error: {f.name}: {e}")

    sftp.close()

    elapsed = time.time() - t_start
    print(f"\n  Upload: {uploaded} OK, {failed} failed in {elapsed:.1f}s")
    print(f"  Rate: {uploaded/elapsed*60:.0f} files/min")

    # 验证
    out, _ = run(c, f"find {REMOTE}/data/baidu_streetview -name '*.jpg' 2>/dev/null | wc -l")
    print(f"  Server count: {out.strip()}")

    # ===== 5. 启动推理 =====
    print("\n[4] Start inference...")

    # 确认数据存在
    out, _ = run(c, f"find {REMOTE}/data/baidu_streetview -name '*.jpg' 2>/dev/null | head -5")
    if not out.strip():
        print("  No data uploaded yet!")
        c.close()
        return

    # 启动
    cmd = (
        f"mkdir -p {REMOTE}/logs {REMOTE}/outputs/segmentation/viz && "
        f"nohup {VENV}/bin/python -u {REMOTE}/gpu_scripts/seg_inference.py "
        f"> {REMOTE}/logs/seg_inference.log 2>&1 &"
    )
    out, _ = run(c, cmd, timeout=20)
    print(f"  Started: {out.strip() or 'OK'}")

    time.sleep(5)

    # 验证进程
    out, _ = run(c, f"ps aux | grep 'seg_inference' | grep -v grep | head -2")
    print(f"  Process: {out.strip() or 'none'}")
    out, _ = run(c, f"tail -5 {REMOTE}/logs/seg_inference.log 2>/dev/null || echo 'no log'")
    print(f"  Log:\n  {out.strip()}")

    # GPU
    out, _ = run(c, "nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader")
    print(f"\n[GPU] {out.strip()}")

    c.close()
    print("\nDone!")

if __name__ == "__main__":
    main()
