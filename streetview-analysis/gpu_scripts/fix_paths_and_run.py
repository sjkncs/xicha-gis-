# -*- coding: utf-8 -*-
"""继续：检查模型上传 + 修复路径 + 启动推理"""
import paramiko, socket, time
from pathlib import Path

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"
REMOTE = "/root/gis_project"
VENV = "/root/venv"
MODEL_HUB = "/root/gis_project/models/hub"
MODEL_ID = "models--nvidia--segformer-b3-finetuned-ade-512-512"
MODEL_PATH = f"{MODEL_HUB}/{MODEL_ID}/snapshots/default"

def make_ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20, allow_agent=False, look_for_keys=False)
    return c

def q(ssh_c, cmd, timeout=8):
    try:
        ch = ssh_c.get_transport().open_session()
        ch.settimeout(timeout)
        ch.exec_command(cmd)
        out = b""
        try:
            while True:
                chunk = ch.recv(4096)
                if not chunk: break
                out += chunk
        except socket.timeout: pass
        ch.close()
        return out.decode("utf-8", errors="replace")
    except Exception as e:
        return f"[ERR] {e}"

def main():
    ssh_c = make_ssh()
    sftp = ssh_c.open_sftp()

    print("=" * 60)
    print("  模型验证 + 路径修复 + 推理启动")
    print("=" * 60)

    # Step 1: 停止旧进程
    print("\n[1] 停止旧进程...")
    print(q(ssh_c, "pkill -f seg_inference; echo STOPPED"))

    # Step 2: 验证模型文件
    print("\n[2] 验证模型文件...")
    out = q(ssh_c, f"ls -lh {MODEL_PATH}/")
    print(out.strip())

    # Step 3: 直接修改推理脚本（sed替换）
    print("\n[3] 修改推理脚本路径...")

    # 用 Python heredoc 写入修复后的脚本头部
    patch_script = f'''
import re
with open("{REMOTE}/gpu_scripts/seg_inference_v2.py", "r") as f:
    content = f.read()

content = re.sub(r'MODEL_CACHE = Path\\([^)]+\\)', 'MODEL_CACHE = Path("{MODEL_HUB}")', content)
content = re.sub(r'os\\.environ\\["HF_HOME"\\] = [^\\n]+', f'os.environ["HF_HOME"] = "{MODEL_HUB}"', content)
content = re.sub(r'os\\.environ\\["TRANSFORMERS_CACHE"\\] = [^\\n]+', f'os.environ["TRANSFORMERS_CACHE"] = "{MODEL_HUB}"', content)
content = re.sub(r'MODEL_NAME = "[^"]+"', 'MODEL_NAME = "{MODEL_ID}"', content)

with open("{REMOTE}/gpu_scripts/seg_inference_v2.py", "w") as f:
    f.write(content)
print("PATCHED")
'''
    # 写入heredoc并执行
    cmd = f"python3 -c {repr(patch_script)}"
    out = q(ssh_c, cmd, timeout=15)
    print(f"  补丁结果: {out.strip()}")

    # 验证修改
    print("\n  验证修改后的配置:")
    print(q(ssh_c, f"grep -E 'MODEL_NAME|MODEL_CACHE|HF_HOME' {REMOTE}/gpu_scripts/seg_inference_v2.py | head -10"))

    # Step 4: 清理检查点
    print("\n[4] 清理检查点...")
    print(q(ssh_c, f"rm -f {REMOTE}/outputs/segmentation/checkpoint_seg.json; echo CLEANED"))

    # Step 5: 启动推理
    print("\n[5] 启动推理...")
    cmd = (
        f"mkdir -p {REMOTE}/logs && "
        f"cd {REMOTE} && "
        f"nohup {VENV}/bin/python -u {REMOTE}/gpu_scripts/seg_inference_v2.py "
        f"> {REMOTE}/logs/seg_inference_v2.log 2>&1 &"
    )
    chan = ssh_c.get_transport().open_session()
    chan.settimeout(15)
    chan.exec_command(cmd)
    try: chan.recv(512)
    except socket.timeout: pass
    chan.close()
    print("  已启动!")

    # 等待模型加载
    print("\n[6] 等待模型加载 (30s)...")
    time.sleep(30)

    # Step 7: 检查日志
    print("\n[7] 推理日志...")
    print(q(ssh_c, f"tail -20 {REMOTE}/logs/seg_inference_v2.log", t=15))

    # Step 8: GPU显存
    print("\n[8] GPU状态...")
    print(q(ssh_c, "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader"))

    # Step 9: 进程
    print("\n[9] 进程状态...")
    out = q(ssh_c, 'ps aux | grep seg_inference | grep -v grep')
    print(out.strip()[:200] if out.strip() else "NOT RUNNING")

    sftp.close()
    ssh_c.close()
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
