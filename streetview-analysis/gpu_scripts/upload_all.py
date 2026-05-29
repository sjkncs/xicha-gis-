# -*- coding: utf-8 -*-
"""上传全部全景图 + 启动推理"""
import paramiko
from pathlib import Path
import time, socket

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

    # 收集所有全景图（跳过 .png 可视化结果）
    all_panos = []
    for ext in ["*.jpg", "*.JPG"]:
        all_panos.extend(LOCAL_PANO.rglob(ext))
    all_panos.sort()
    total = len(all_panos)
    print(f"Total panoramas: {total}")

    # 检查已上传的
    try:
        remote_files = sftp.listdir(f"{REMOTE}/data/baidu_streetview")
        remote_set = set(f for f in remote_files if f.endswith(".jpg"))
    except:
        remote_set = set()

    print(f"Already uploaded: {len(remote_set)}")
    pending = [f for f in all_panos if f.name not in remote_set]
    print(f"Need to upload: {len(pending)}")

    if not pending:
        print("All files already uploaded!")
    else:
        total_mb = sum(f.stat().st_size for f in all_panos) / 1024**2
        pending_mb = sum(f.stat().st_size for f in pending) / 1024**2
        print(f"Pending size: {pending_mb:.1f} MB")

        t0 = time.time()
        ok, fail = 0, 0
        for i, f in enumerate(pending):
            try:
                sftp.put(str(f), f"{REMOTE}/data/baidu_streetview/{f.name}")
                ok += 1
                elapsed = time.time() - t0
                rate = ok / elapsed * 60 if elapsed > 0 else 0
                remain = len(pending) - ok
                eta = remain / rate if rate > 0 else 0
                if i % 20 == 0 or i == len(pending) - 1:
                    print(f"  [{ok}/{len(pending)}] {f.name}  rate={rate:.0f}/min  eta={eta:.0f}min")
            except Exception as e:
                fail += 1
                if fail <= 5:
                    print(f"  FAIL {f.name}: {e}")
        print(f"Upload done: {ok} OK, {fail} failed")

    # 确认文件数量
    final = sftp.listdir(f"{REMOTE}/data/baidu_streetview")
    final_jpg = [f for f in final if f.endswith(".jpg")]
    print(f"\nRemote total jpg files: {len(final_jpg)}")

    # 启动推理
    print("\nStarting inference...")
    cmd = (
        f"mkdir -p {REMOTE}/data/baidu_streetview/segmentation_results && "
        f"nohup {VENV}/bin/python -u {REMOTE}/gpu_scripts/seg_inference.py "
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
    print(f"Inference started!")
    print(f"Log: {REMOTE}/logs/seg_inference.log")
    print(f"Monitor: tail -f {REMOTE}/logs/seg_inference.log")

    sftp.close()
    ssh_c.close()
    print("Done!")

if __name__ == "__main__":
    main()
