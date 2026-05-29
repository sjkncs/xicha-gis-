# -*- coding: utf-8 -*-
"""GPU推理 - 离线修复版（上传processor_config.json + 启动推理）"""
import paramiko
from pathlib import Path
import socket, time, os

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
    print("  离线推理修复工具")
    print("=" * 60)

    # Step 1: 杀掉旧进程
    print("\n[1] 停止旧推理进程...")
    out = quick_cmd(ssh_c, "pkill -f seg_inference.py; echo STOPPED", timeout=5)
    print(f"  {out.strip()}")

    # Step 2: 查找实际的模型路径
    print("\n[2] 查找实际模型snapshot路径...")
    out = quick_cmd(ssh_c, "find /root/gis_project/models -name 'pytorch_model.bin' 2>/dev/null", timeout=10)
    model_weights = out.strip()
    print(f"  模型权重: {model_weights}")

    out = quick_cmd(ssh_c, "find /root/gis_project/models -name 'model.safetensors' 2>/dev/null", timeout=10)
    safetensors = out.strip()
    print(f"  safetensors: {safetensors}")

    # 找到snapshot目录
    out = quick_cmd(ssh_c, "find /root/gis_project/models -name '*.safetensors' 2>/dev/null | head -3", timeout=10)
    print(f"  safetensors路径: {out.strip()}")

    # Step 3: 在本地下载 processor_config.json
    print("\n[3] 下载 processor_config.json...")
    import requests
    config_url = "https://huggingface.co/nvidia/mit-b3/resolve/main/processor_config.json"
    try:
        r = requests.get(config_url, timeout=30)
        if r.status_code == 200:
            local_config = Path(__file__).parent / "processor_config.json"
            local_config.write_bytes(r.content)
            print(f"  下载成功: {local_config} ({len(r.content)} bytes)")

            # 上传到服务器的模型snapshot目录
            # 找到snapshot目录
            out = quick_cmd(ssh_c, "ls /root/gis_project/models/models--nvidia--mit-b3/snapshots/ 2>/dev/null | head -3", timeout=5)
            snapshot_id = out.strip().split('\n')[0] if out.strip() else None
            if snapshot_id:
                remote_config = f"/root/gis_project/models/models--nvidia--mit-b3/snapshots/{snapshot_id}/processor_config.json"
                sftp.put(str(local_config), remote_config)
                print(f"  上传到: {remote_config}")

                # 同时上传到HF默认缓存路径
                sftp.put(str(local_config), "/root/.cache/huggingface/hub/models--nvidia--mit-b3/processor_config.json")
                print(f"  同时复制到HF缓存: /root/.cache/huggingface/hub/models--nvidia--mit-b3/")
        else:
            print(f"  下载失败: HTTP {r.status_code}")
    except Exception as e:
        print(f"  下载失败: {e}")
        print("  尝试从本地上传（如果存在）...")
        local_config = Path(__file__).parent / "processor_config.json"
        if local_config.exists():
            print(f"  找到本地文件: {local_config} ({local_config.stat().st_size} bytes)")
        else:
            print("  本地也没有processor_config.json")

    # Step 4: 查看当前推理脚本
    print("\n[4] 当前推理脚本配置:")
    out = quick_cmd(ssh_c, f"head -30 {REMOTE}/gpu_scripts/seg_inference.py", timeout=8)
    print(f"  {out.strip()[:500]}")

    # Step 5: 检查推理输出目录
    print("\n[5] 推理输出目录:")
    out = quick_cmd(ssh_c, f"ls {REMOTE}/data/baidu_streetview/segmentation_results/ 2>/dev/null | wc -l", timeout=5)
    print(f"  已生成结果: {out.strip()} 张")

    # Step 6: 重新启动推理
    print("\n[6] 重新启动推理...")
    # 先上传修复版的推理脚本（设置HF_OFFLINE=1）
    infer_py = Path(__file__).parent / "seg_inference_offline.py"
    if infer_py.exists():
        print(f"  上传离线推理脚本...")
        sftp.put(str(infer_py), f"{REMOTE}/gpu_scripts/seg_inference_offline.py")

    cmd = (
        f"mkdir -p {REMOTE}/logs && "
        f"cd {REMOTE} && "
        f"export HF_HUB_ENABLE_HF_TRANSFER=0 && "
        f"export TRANSFORMERS_OFFLINE=0 && "
        f"nohup {VENV}/bin/python -u {REMOTE}/gpu_scripts/seg_inference_offline.py "
        f"> {REMOTE}/logs/seg_inference.log 2>&1 &"
    )
    chan = ssh_c.get_transport().open_session()
    chan.settimeout(15)
    chan.exec_command(cmd)
    try:
        chan.recv(512)
    except socket.timeout:
        pass
    chan.close()
    print(f"  推理已重新启动!")
    print(f"  日志: {REMOTE}/logs/seg_inference.log")

    # 等待几秒再检查
    time.sleep(5)

    print("\n[7] 推理日志 (最新):")
    out = quick_cmd(ssh_c, f"tail -15 {REMOTE}/logs/seg_inference.log", timeout=10)
    print(f"  {out.strip()}")

    print("\n[8] GPU状态:")
    out = quick_cmd(ssh_c, "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader", timeout=5)
    print(f"  {out.strip()}")

    sftp.close()
    ssh_c.close()
    print("\n" + "=" * 60)
    print("  下一步:")
    print("  tail -f /root/gis_project/logs/seg_inference.log")
    print("=" * 60)

if __name__ == "__main__":
    main()
