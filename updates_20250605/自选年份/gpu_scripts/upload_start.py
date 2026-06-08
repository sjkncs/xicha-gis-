# -*- coding: utf-8 -*-
"""GPU 服务器一键部署: 上传脚本 + 启动推理"""
import paramiko
from pathlib import Path
import time

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"
REMOTE = "/root/gis_project"
VENV = "/root/venv"
SCRIPTS_DIR = Path(__file__).parent

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20, allow_agent=False, look_for_keys=False)
    return c

def run(c, cmd, timeout=15):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace"), stderr.read().decode("utf-8", errors="replace")

def put_sftp(c, local_path, remote_path):
    """用 SFTP 上传文件"""
    s = c.open_sftp()
    s.put(str(local_path), remote_path)
    s.close()

def put_heredoc(c, content, remote_path):
    """通过 heredoc 写入远程文件（适合短脚本）"""
    escaped = content.replace("'", "'\"'\"'")
    cmd = f"cat > '{remote_path}' << 'ENDOFFILE'\n{content}\nENDOFFILE"
    run(c, cmd, timeout=20)

def main():
    print("=" * 55)
    print("GPU 服务器一键部署")
    print("=" * 55)

    c = ssh()
    print("Connected!")

    # 1. 创建目录
    print("\n[1] 创建远程目录...")
    run(c, f"mkdir -p {REMOTE}/gpu_scripts {REMOTE}/outputs/segmentation/viz {REMOTE}/logs")
    print("  目录创建完成")

    # 2. 上传 seg_inference.py (通过 SFTP，因为太长)
    print("\n[2] 上传 seg_inference.py (SFTP)...")
    seg_py = SCRIPTS_DIR / "seg_inference.py"
    remote_seg = f"{REMOTE}/gpu_scripts/seg_inference.py"
    put_sftp(c, seg_py, remote_seg)
    print(f"  已上传: {seg_py.stat().st_size / 1024:.1f} KB")

    # 3. 上传 run_segmentation.sh (heredoc)
    print("\n[3] 上传 run_segmentation.sh...")
    run_sh = SCRIPTS_DIR / "run_segmentation.sh"
    if run_sh.exists():
        content = run_sh.read_text(encoding="utf-8")
        put_heredoc(c, content, f"{REMOTE}/gpu_scripts/run_segmentation.sh")
        run(c, f"chmod +x {REMOTE}/gpu_scripts/run_segmentation.sh")
        print("  已上传")

    # 4. 上传 download_models.sh (heredoc)
    print("\n[4] 上传 download_models.sh...")
    dl_sh = SCRIPTS_DIR / "download_models.sh"
    if dl_sh.exists():
        content = dl_sh.read_text(encoding="utf-8")
        put_heredoc(c, content, f"{REMOTE}/gpu_scripts/download_models.sh")
        run(c, f"chmod +x {REMOTE}/gpu_scripts/download_models.sh")
        print("  已上传")

    # 5. 检查模型是否已下载
    print("\n[5] 检查模型状态...")
    out, _ = run(c, f"ls /autodl-pub/data/models/hub/models--nvidia--mit-b3/snapshots/ 2>/dev/null | head -3 || echo 'NOT_FOUND'")
    model_ready = "NOT_FOUND" not in out
    print(f"  SegFormer B3: {'已存在' if model_ready else '需要下载'}")

    # 6. 检查全景图数据
    print("\n[6] 检查全景图数据...")
    out, _ = run(c, "find /autodl-pub/data -name '*.jpg' 2>/dev/null | wc -l")
    jpg_count = int(out.strip()) if out.strip().isdigit() else 0
    print(f"  全景图数量: {jpg_count}")

    if jpg_count == 0:
        print("\n  ⚠️ 未找到全景图!")
        print("  数据应上传到: /autodl-pub/data/baidu_streetview/")
    else:
        print(f"  数据路径: /autodl-pub/data")

    # 7. 启动模型下载(如果需要)
    if not model_ready:
        print("\n[7] 启动模型下载 (后台)...")
        # 下载脚本用 heredoc 写入
        dl_content = r"""#!/bin/bash
set -e
export HF_ENDPOINT="https://hf-mirror.com"
MODEL_DIR="/autodl-pub/data/models"
LOG="/root/gis_project/logs/download_models.log"
exec > $LOG 2>&1
echo "开始下载模型 $(date)"
/root/venv/bin/python -c "
from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation
print('下载 SegFormer B3...')
processor = AutoImageProcessor.from_pretrained('nvidia/mit-b3', cache_dir='/autodl-pub/data/models')
model = AutoModelForSemanticSegmentation.from_pretrained('nvidia/mit-b3', cache_dir='/autodl-pub/data/models')
print('SegFormer B3 下载完成!')
"
echo "模型下载完成 $(date)"
touch /root/gis_project/gpu_scripts/MODELS_READY
"""
        put_heredoc(c, dl_content, f"{REMOTE}/gpu_scripts/download_models.sh")
        run(c, f"chmod +x {REMOTE}/gpu_scripts/download_models.sh")
        out, _ = run(c, f"cd {REMOTE}/gpu_scripts && nohup bash download_models.sh > download_models.out 2>&1 &")
        print("  下载已后台启动")

    # 8. 启动分割推理
    print("\n[8] 启动分割推理...")
    out, _ = run(c, f"ps aux | grep 'seg_inference.py' | grep -v grep | head -2")
    if out.strip():
        print(f"  已在运行: {out.strip()[:80]}")
    else:
        # 启动推理
        cmd = (
            f"cd {REMOTE} && "
            f"mkdir -p {REMOTE}/logs {REMOTE}/outputs/segmentation/viz && "
            f"nohup {VENV}/bin/python -u {REMOTE}/gpu_scripts/seg_inference.py "
            f"> {REMOTE}/logs/seg_inference.log 2>&1 &"
        )
        out, _ = run(c, cmd, timeout=15)
        print("  推理已启动!")

    # 9. 检查启动结果
    print("\n[9] 检查启动结果...")
    time.sleep(3)
    out, _ = run(c, f"ps aux | grep 'seg_inference.py' | grep -v grep | head -2")
    print(f"  进程: {out.strip() or '未找到进程'}")
    out, _ = run(c, f"tail -5 {REMOTE}/logs/seg_inference.log 2>/dev/null || echo '日志暂无'")
    print(f"  日志:\n  {out.strip()}")

    # 10. GPU 状态
    print("\n[10] GPU 状态...")
    out, _ = run(c, "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader")
    print(f"  {out.strip()}")

    c.close()

    print("\n" + "=" * 55)
    print("部署完成!")
    print("=" * 55)
    print(f"\n监控命令:")
    print(f"  tail -f {REMOTE}/logs/seg_inference.log")
    print(f"  tail -f {REMOTE}/logs/download_models.log")
    print(f"  cat {REMOTE}/outputs/segmentation/seg_results.csv | head -20")
    print(f"  nvidia-smi -l 1")
    print(f"  watch -n 5 'tail -3 {REMOTE}/logs/seg_inference.log'")

if __name__ == "__main__":
    main()
