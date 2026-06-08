#!/usr/bin/env python3
"""Download YOLO results from remote to local."""
from pathlib import Path
import paramiko

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE = "/root/autodl-tmp/streetview_analysis/output"
LOCAL = Path(r"e:\xicha gis 智能定位\自选年份")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
sftp = c.open_sftp()

files = [
    "yolo/results_per_image.jsonl",
    "yolo/results_merged.json",
    "yolo/yolo_detect.log",
]

for f in files:
    try:
        local_path = LOCAL / f.replace("/", "_")
        sftp.get(f"{REMOTE}/{f}", str(local_path))
        print(f"OK  {f} -> {local_path.name}")
    except Exception as e:
        print(f"FAIL {f}: {e}")

# heatmaps - download 30 per type
for sub in ["yolo_count_only", "yolo_blocked_only", "yolo_mixed"]:
    for vt in ["street_view", "ground_view"]:
        remote_dir = f"{REMOTE}/heatmaps/{sub}/{vt}"
        local_dir = LOCAL / "heatmaps" / sub / vt
        local_dir.mkdir(parents=True, exist_ok=True)
        try:
            items = sftp.listdir(remote_dir)
            downloaded = 0
            for item in items:
                if item.endswith(".jpg") and downloaded < 30:
                    try:
                        sftp.get(f"{remote_dir}/{item}", str(local_dir / item))
                        downloaded += 1
                    except:
                        pass
            print(f"heatmaps {sub}/{vt}: {downloaded} downloaded")
        except Exception as e:
            print(f"heatmaps {sub}/{vt}: {e}")

sftp.close(); c.close()
print("Done!")
