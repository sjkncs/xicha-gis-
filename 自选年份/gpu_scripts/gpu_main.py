# -*- coding: utf-8 -*-
"""GPU服务器 - 模型下载 + 数据上传 + 推理启动（稳定版）"""
import paramiko
from pathlib import Path
import time, sys, io

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"
REMOTE = "/root/gis_project"
VENV = "/root/venv"
LOCAL_PANO = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview")

def make_ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20, allow_agent=False, look_for_keys=False)
    return c

def quick_cmd(ssh_client, cmd, timeout=10):
    """执行命令，只返回stdout，stderr忽略，超时强制关闭通道"""
    try:
        chan = ssh_client.get_transport().open_session()
        chan.settimeout(timeout)
        chan.exec_command(cmd)
        out = b""
        try:
            while True:
                chunk = chan.recv(4096)
                if not chunk:
                    break
                out += chunk
        except socket.timeout:
            pass
        chan.close()
        return out.decode("utf-8", errors="replace")
    except Exception as e:
        return f"[ERROR] {e}"

import socket

def main():
    ssh_c = make_ssh()
    sftp = ssh_c.open_sftp()

    print("=" * 55)
    print("  GPU 云端推理部署工具")
    print("=" * 55)

    # ===== Step 1: 检查模型状态 =====
    print("\n[1/5] 检查 SegFormer B3 模型状态...")
    # 检查nvidia/mit-b3是否已下载
    out = quick_cmd(ssh_c, f"ls {REMOTE}/models/hub/models--nvidia--mit-b3/snapshots/ 2>/dev/null && echo FOUND || echo NOT_FOUND", timeout=8)
    model_ready = "FOUND" in out
    print(f"  SegFormer B3: {'READY' if model_ready else 'NOT READY'}")

    if not model_ready:
        print("\n[2/5] 上传下载脚本...")
        dl_py = Path(__file__).parent / "download_model.py"
        try:
            sftp.put(str(dl_py), f"{REMOTE}/gpu_scripts/download_model.py")
            print(f"  上传成功: {dl_py.name}")
        except Exception as e:
            print(f"  上传失败: {e}")
            ssh_c.close()
            return

        print("\n[3/5] 启动后台下载...")
        # 用 nohup 启动，不等待输出
        chan = ssh_c.get_transport().open_session()
        chan.settimeout(15)
        cmd = (
            f"mkdir -p {REMOTE}/logs && "
            f"{VENV}/bin/python -u {REMOTE}/gpu_scripts/download_model.py "
            f"> {REMOTE}/logs/model_download.log 2>&1 &"
        )
        chan.exec_command(cmd)
        import socket
        try:
            chan.recv(1024)
        except socket.timeout:
            pass
        chan.close()
        print(f"  下载已在后台启动!")
        print(f"  监控命令: tail -f {REMOTE}/logs/model_download.log")
        print(f"  预计耗时: 5-15分钟 (取决于网速)")
    else:
        print("\n[2/5] 模型已存在 - 跳过下载")

    # ===== Step 4: 上传全景图 =====
    print("\n[4/5] 上传全景图像...")
    all_panos = []
    for ext in ["*.jpg", "*.JPG", "*.png", "*.PNG"]:
        all_panos.extend(LOCAL_PANO.rglob(ext))
    all_panos.sort()
    total = len(all_panos)
    if not all_panos:
        print("  ERROR: 本地无全景图!")
        ssh_c.close()
        return

    total_mb = sum(f.stat().st_size for f in all_panos) / 1024**2
    print(f"  本地文件: {total} 张")
    print(f"  总大小: {total_mb:.1f} MB")

    # 创建目录（确保可写）
    for d in [f"{REMOTE}/data", f"{REMOTE}/data/baidu_streetview"]:
        try:
            sftp.stat(d)
        except:
            try:
                sftp.mkdir(d)
            except:
                pass

    # 上传前 N 个文件（测试 + 首批）
    batch = min(30, total)
    uploaded = 0
    failed = 0
    t0 = time.time()
    for i, f in enumerate(all_panos[:batch]):
        try:
            sftp.put(str(f), f"{REMOTE}/data/baidu_streetview/{f.name}")
            uploaded += 1
            if i % 5 == 0:
                print(f"  [{i+1}/{batch}] {f.name}")
        except Exception as e:
            failed += 1
            if failed <= 3:
                print(f"  FAIL: {f.name} -> {e}")

    elapsed = time.time() - t0
    rate = uploaded / elapsed * 60 if elapsed > 0 else 0
    speed_mb = uploaded * (total_mb / total) / elapsed if elapsed > 0 else 0
    print(f"  完成: {uploaded}/{batch} 成功, {failed} 失败")
    print(f"  速率: {rate:.0f} 张/分钟, {speed_mb:.1f} MB/分钟")
    if rate > 0:
        est = (total - uploaded) / rate
        print(f"  剩余上传: ~{est:.0f} 分钟")

    # ===== Step 5: 准备推理脚本 =====
    print("\n[5/5] 准备推理脚本...")
    out = quick_cmd(ssh_c,
        f"sed -i 's|/autodl-pub/data/models|{REMOTE}/models|g' {REMOTE}/gpu_scripts/seg_inference.py && "
        f"sed -i 's|/autodl-pub/data/baidu_streetview|{REMOTE}/data/baidu_streetview|g' {REMOTE}/gpu_scripts/seg_inference.py && "
        f"echo PATH_FIXED || echo PATH_FIX_FAILED",
        timeout=15
    )
    print(f"  路径修复: {'OK' if 'PATH_FIXED' in out else out.strip()}")

    # GPU状态
    gpu_out = quick_cmd(ssh_c, "nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader", timeout=8)
    print(f"\n  GPU: {gpu_out.strip()}")
    disk_out = quick_cmd(ssh_c, "df -h /root | tail -1", timeout=5)
    print(f"  磁盘: {disk_out.strip()}")

    sftp.close()
    ssh_c.close()

    print("\n" + "=" * 55)
    print("  部署计划")
    print("=" * 55)
    if not model_ready:
        print(f"\n  [A] 等待模型下载完成 (约5-15分钟)")
        print(f"      监控: ssh -p {PORT} {USER}@{HOST}")
        print(f"            tail -f {REMOTE}/logs/model_download.log")
        print(f"\n  [B] 模型下载完成后，上传剩余全景图:")
        print(f"      手动上传脚本: upload_rest.py (后续运行)")
        print(f"\n  [C] 启动推理:")
        print(f"      cd {REMOTE} && {VENV}/bin/python -u gpu_scripts/seg_inference.py")
    else:
        print(f"\n  模型已就绪!")
        print(f"\n  启动推理:")
        print(f"  ssh -p {PORT} {USER}@{HOST}")
        print(f"  cd {REMOTE} && {VENV}/bin/python -u gpu_scripts/seg_inference.py")
    print(f"\n  推理结果: {REMOTE}/data/baidu_streetview/segmentation_results/")
    print("=" * 55)

if __name__ == "__main__":
    main()
