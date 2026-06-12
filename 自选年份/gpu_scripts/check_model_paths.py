# -*- coding: utf-8 -*-
"""检查推理脚本中的模型路径 + 查找模型实际位置"""
import paramiko
from pathlib import Path
import socket

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
    print("=" * 60)

    # 1. 推理脚本中的路径
    print("\n[1] 推理脚本 MODEL_DIR:")
    out = quick_cmd(ssh_c, f"grep -n 'MODEL_DIR\\|MODEL_PATH\\|model_name\\|cache_dir' {REMOTE}/gpu_scripts/seg_inference.py | head -15", timeout=8)
    print(f"  {out.strip()}")

    # 2. 查找模型实际位置
    print("\n[2] 查找 SegFormer B3 模型实际位置:")
    out = quick_cmd(ssh_c, "find /root -name '*.safetensors' -o -name 'pytorch_model.bin' 2>/dev/null | grep -i mit-b3 | head -10", timeout=15)
    print(f"  {out.strip() or 'NOT FOUND via find'}")

    out = quick_cmd(ssh_c, "ls /root/gis_project/models/hub/ 2>/dev/null || echo 'No hub dir'", timeout=5)
    print(f"  hub/: {out.strip()}")

    out = quick_cmd(ssh_c, "ls /root/gis_project/models/hub/models--nvidia--mit-b3/snapshots/ 2>/dev/null || echo 'NOT FOUND'", timeout=5)
    print(f"  snapshots/: {out.strip()}")

    out = quick_cmd(ssh_c, "ls /root/gis_project/models/hub/models--nvidia--mit-b3/snapshots/*/  2>/dev/null | head -10", timeout=5)
    print(f"  model files: {out.strip() or 'EMPTY'}")

    # 3. Huggingface 缓存默认位置
    print("\n[3] HF 默认缓存:")
    out = quick_cmd(ssh_c, "ls ~/.cache/huggingface/hub/models--nvidia--mit-b3/snapshots/ 2>/dev/null || echo 'NOT IN DEFAULT CACHE'", timeout=5)
    print(f"  {out.strip() or 'NOT FOUND'}")

    # 4. 推理日志最后30行
    print("\n[4] 推理日志 (最后30行):")
    out = quick_cmd(ssh_c, f"tail -30 {REMOTE}/logs/seg_inference.log", timeout=10)
    print(f"  {out.strip()}")

    # 5. 已生成结果
    print("\n[5] 已生成结果:")
    out = quick_cmd(ssh_c, f"ls {REMOTE}/data/baidu_streetview/segmentation_results/ 2>/dev/null | wc -l", timeout=5)
    print(f"  结果数量: {out.strip()}")
    out = quick_cmd(ssh_c, f"ls {REMOTE}/data/baidu_streetview/segmentation_results/ 2>/dev/null | head -5", timeout=5)
    print(f"  样本: {out.strip()}")

    # 6. GPU内存
    print("\n[6] GPU内存:")
    out = quick_cmd(ssh_c, "nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader", timeout=5)
    print(f"  {out.strip()}")

    ssh_c.close()
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
