#!/usr/bin/env python3
"""Upload YOLO batch script to remote and start it (nohup).

Outputs will be written to:
  /root/autodl-tmp/streetview_analysis/output/

Assumes models are present in:
  /root/autodl-tmp/streetview_analysis/yolo_models/

Run this from Windows locally.
"""

import time
from pathlib import Path

import paramiko

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"

LOCAL_SCRIPT = Path(r"e:\xicha gis 智能定位\自选年份\gpu_scripts\yolo_detect_batch.py")


def run(c, cmd, timeout=120):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    code = stdout.channel.recv_exit_status()
    return out, err, code


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    sftp = c.open_sftp()

    # ensure dirs
    run(c, f"mkdir -p {REMOTE_DIR}/output/yolo {REMOTE_DIR}/output/heatmaps")

    # upload script
    remote_script = f"{REMOTE_DIR}/yolo_detect_batch.py"
    sftp.put(str(LOCAL_SCRIPT), remote_script)
    run(c, f"chmod +x {remote_script}")

    # quick deps check
    out, err, ec = run(c, "python3 -c 'import cv2, numpy; import ultralytics; print(""deps ok"", ultralytics.__version__)'", timeout=60)
    print(f"deps: [{ec}] {out} {err[:120]}")

    # start nohup
    log_path = f"{REMOTE_DIR}/output/yolo/yolo_detect.log"
    cmd = (
        f"cd {REMOTE_DIR} && "
        f"nohup python3 {remote_script} "
        f"--img_root {REMOTE_DIR}/images "
        f"--out_root {REMOTE_DIR}/output "
        f"> {log_path} 2>&1 & echo $!"
    )

    out, err, ec = run(c, cmd, timeout=30)
    pid = out.strip().splitlines()[-1] if out.strip() else ""
    print(f"started pid={pid or 'unknown'}")

    time.sleep(3)
    tail, _, _ = run(c, f"tail -n 20 {log_path} 2>/dev/null || true", timeout=30)
    print("--- log tail ---")
    print(tail)

    sftp.close()
    c.close()


if __name__ == "__main__":
    main()
