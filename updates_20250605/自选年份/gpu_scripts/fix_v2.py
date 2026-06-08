# -*- coding: utf-8 -*-
"""修复推理脚本 - 正确的SegFormer模型 + 完整ADE20K类别"""
import paramiko
from pathlib import Path
import socket, time

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"
REMOTE = "/root/gis_project"
VENV = "/root/venv"

def make_ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20, allow_agent=False, look_for_keys=False)
    return c

def quick_cmd(ssh_c, cmd, timeout=8):
    try:
        chan = ssh_c.get_transport().open_session()
        chan.settimeout(timeout)
        chan.exec_command(cmd)
        out = b""
        try:
            while True:
                chunk = chan.recv(4096)
                if not chunk: break
                out += chunk
        except socket.timeout:
            pass
        chan.close()
        return out.decode("utf-8", errors="replace")
    except Exception as e:
        return f"[ERR] {e}"

def main():
    ssh_c = make_ssh()
    sftp = ssh_c.open_sftp()

    print("=" * 60)
    print("  推理修复工具 (v2)")
    print("=" * 60)

    # Step 1: 停止旧进程
    print("\n[1] 停止旧推理进程...")
    out = quick_cmd(ssh_c, "pkill -f seg_inference.py; sleep 1; echo STOPPED", timeout=5)
    print(f"  {out.strip()}")

    # Step 2: 上传新推理脚本
    print("\n[2] 上传新的 seg_inference_v2.py...")
    local_py = Path(__file__).parent / "seg_inference_v2.py"
    if not local_py.exists():
        print(f"  ERROR: {local_py} 不存在!")
        ssh_c.close()
        return
    sftp.put(str(local_py), f"{REMOTE}/gpu_scripts/seg_inference_v2.py")
    print(f"  上传成功: {local_py.name} ({local_py.stat().st_size} bytes)")

    # Step 3: 清理旧检查点（重新开始）
    print("\n[3] 清理旧检查点（重新开始）...")
    out = quick_cmd(ssh_c, f"rm -f {REMOTE}/outputs/segmentation/checkpoint_seg.json; echo CLEANED", timeout=5)
    print(f"  {out.strip()}")

    # Step 4: 检查数据
    print("\n[4] 检查全景数据...")
    out = quick_cmd(ssh_c, f"ls {REMOTE}/data/baidu_streetview/*.jpg 2>/dev/null | wc -l", timeout=5)
    print(f"  jpg文件数: {out.strip()}")

    # Step 5: 检查GPU
    print("\n[5] GPU状态...")
    out = quick_cmd(ssh_c, "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader", timeout=5)
    print(f"  {out.strip()}")

    # Step 6: 启动新推理
    print("\n[6] 启动新推理 (SegFormer B3 ADE20K)...")
    cmd = (
        f"mkdir -p {REMOTE}/logs && "
        f"cd {REMOTE} && "
        f"nohup {VENV}/bin/python -u {REMOTE}/gpu_scripts/seg_inference_v2.py "
        f"> {REMOTE}/logs/seg_inference_v2.log 2>&1 &"
    )
    chan = ssh_c.get_transport().open_session()
    chan.settimeout(15)
    chan.exec_command(cmd)
    try:
        chan.recv(512)
    except socket.timeout:
        pass
    chan.close()
    print(f"  推理已启动!")

    # 等待30秒让日志产生
    print("\n[7] 等待模型下载和初始化...")
    time.sleep(30)

    # Step 8: 查看日志
    print("\n[8] 推理日志 (最新20行):")
    out = quick_cmd(ssh_c, f"tail -20 {REMOTE}/logs/seg_inference_v2.log", timeout=10)
    print(f"  {out.strip()}")

    # Step 9: GPU显存
    print("\n[9] GPU显存使用...")
    out = quick_cmd(ssh_c, "nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader", timeout=5)
    print(f"  {out.strip()}")

    sftp.close()
    ssh_c.close()

    print("\n" + "=" * 60)
    print("  下一步:")
    print("  ssh -p 37625 root@connect.bjb1.seetacloud.com")
    print("  tail -f /root/gis_project/logs/seg_inference_v2.log")
    print("=" * 60)

if __name__ == "__main__":
    main()
