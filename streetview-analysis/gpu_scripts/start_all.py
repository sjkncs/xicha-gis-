# -*- coding: utf-8 -*-
"""GPU 服务器一键启动脚本
1. 上传推理脚本
2. 下载模型
3. 启动批量推理"""
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

def put(c, local, remote):
    s = c.open_sftp()
    s.put(str(local), remote)
    s.close()
    print(f"  -> {Path(local).name}")

def put_script(c, content, remote):
    """通过 heredoc 写入远程文件"""
    escaped = content.replace("'", "'\"'\"'")
    cmd = f"cat > '{remote}' << 'ENDOFFILE'\n{content}\nENDOFFILE"
    run(c, cmd, timeout=15)

def main():
    scripts_dir = Path(__file__).parent
    print("=" * 55)
    print("GPU 服务器一键启动")
    print("=" * 55)

    c = ssh()
    print("Connected!")

    # ====== 1. 检查 GPU 状态 ======
    print("\n[1] 检查 GPU 状态...")
    out, _ = run(c, "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>&1")
    print(f"  {out.strip()}")

    # ====== 2. 上传脚本 ======
    print("\n[2] 上传脚本...")
    remote_scripts = f"{REMOTE}/gpu_scripts"
    run(c, f"mkdir -p {remote_scripts}/logs {REMOTE}/outputs/segmentation {REMOTE}/logs")

    scripts_to_upload = [
        ("download_models.sh", f"{remote_scripts}/download_models.sh"),
        ("run_segmentation.sh", f"{remote_scripts}/run_segmentation.sh"),
    ]
    for local_name, remote_path in scripts_to_upload:
        lp = scripts_dir / local_name
        if lp.exists():
            content = lp.read_text(encoding="utf-8")
            print(f"  写入 {remote_path}...")
            put_script(c, content, remote_path)
            run(c, f"chmod +x {remote_path}")
        else:
            print(f"  跳过(不存在): {local_name}")

    # ====== 3. 下载模型 (后台) ======
    print("\n[3] 检查模型状态...")
    out, _ = run(c, f"ls /autodl-pub/data/models/hub/models--nvidia--mit-b3/ 2>/dev/null | head -5 || echo '模型未下载'")
    print(f"  SegFormer B3: {'已存在' if 'config.json' in out else out.strip()}")

    # 如果模型不存在，启动下载
    if "config.json" not in out:
        print("  启动模型下载 (后台运行)...")
        run(c, f"cd {remote_scripts} && nohup bash download_models.sh > download_models.out 2>&1 &", timeout=10)
        print("  下载已在后台启动 (预计 10-30 分钟)")

        # 等待 2 分钟检查
        print("  等待 2 分钟后检查...")
        time.sleep(120)
        out, _ = run(c, f"cat {remote_scripts}/download_models.out 2>&1 | tail -20")
        print(f"  下载进度:\n{out.strip()}")
    else:
        print("  SegFormer B3 模型已存在!")

    # ====== 4. 检查全景图数据 ======
    print("\n[4] 检查数据...")
    out, _ = run(c, f"find /autodl-pub/data -name '*.jpg' 2>/dev/null | wc -l")
    print(f"  /autodl-pub/data 中的 JPG: {out.strip()}")

    # 如果没有数据，告知用户上传
    jpg_count = int(out.strip()) if out.strip().isdigit() else 0
    if jpg_count == 0:
        print("\n  ⚠️ 没有找到全景图!")
        print("  请上传全景图数据到 /autodl-pub/data/baidu_streetview/")
        print("  或在本地运行 upload_panoramas.py 进行上传")

    # ====== 5. 启动分割推理 ======
    print("\n[5] 启动分割推理...")
    out, _ = run(c, f"ps aux | grep 'seg_inference.py' | grep -v grep | head -2", timeout=10)
    if out.strip():
        print(f"  推理已在运行: {out.strip()[:100]}")
    else:
        print("  启动推理...")
        run(c,
            f"mkdir -p {REMOTE}/logs {REMOTE}/outputs/segmentation/viz && "
            f"cd {REMOTE} && "
            f"nohup {VENV}/bin/python -u {remote_scripts}/seg_inference.py > {REMOTE}/logs/seg_inference.log 2>&1 &",
            timeout=15)
        print("  推理已启动!")

    # ====== 6. 监控命令 ======
    print("\n[6] 监控命令:")
    print(f"  查看日志: tail -f {REMOTE}/logs/seg_inference.log")
    print(f"  查看进度: tail -5 {REMOTE}/outputs/segmentation/seg_results.csv")
    print(f"  GPU 状态: watch -n 1 nvidia-smi")
    print(f"  下载进度: tail -f {remote_scripts}/download_models.out")
    print(f"  查看CSV: cat {REMOTE}/outputs/segmentation/seg_results.csv")

    # ====== 7. 当前进度 ======
    print("\n[7] 当前推理进度...")
    out, _ = run(c, f"wc -l {REMOTE}/outputs/segmentation/seg_results.csv 2>/dev/null || echo '0'")
    print(f"  已处理行数: {out.strip()}")
    out, _ = run(c, f"cat {REMOTE}/logs/seg_inference.log 2>/dev/null | tail -10")
    print(f"  最新日志:\n{out.strip()}")

    c.close()
    print("\n==== 启动完成! ====")

if __name__ == "__main__":
    main()
