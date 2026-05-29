#!/usr/bin/env python3
"""下载服务器上的结果到本地"""
import paramiko, base64, os

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"
OUT_BASE = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results"

REMOTE_FILES = [
    (f"{REMOTE_DIR}/yolo_obstacle_results/all_results.json",       f"{OUT_BASE}/all_results.json"),
    (f"{REMOTE_DIR}/yolo_obstacle_results/street_stats.json",       f"{OUT_BASE}/street_stats.json"),
    (f"{REMOTE_DIR}/yolo_obstacle_results/global_categories.json", f"{OUT_BASE}/global_categories.json"),
    (f"{REMOTE_DIR}/yolo_obstacle_results/category_bar_street_view.png", f"{OUT_BASE}/category_bar_street_view.png"),
    (f"{REMOTE_DIR}/yolo_obstacle_results/score_dist_street_view.png", f"{OUT_BASE}/score_dist_street_view.png"),
    (f"{REMOTE_DIR}/diag_cuda.log",                                  f"{OUT_BASE}/diag_cuda.log"),
    (f"{REMOTE_DIR}/yolo_obstacle_run.log",                          f"{OUT_BASE}/yolo_obstacle_run.log"),
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=60)

sftp = c.open_sftp()

def download_file(remote_path, local_path):
    """通过base64编码下载大文件"""
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    try:
        sftp.stat(remote_path)
    except FileNotFoundError:
        print(f"  SKIP (not found): {remote_path}")
        return

    size = sftp.stat(remote_path).st_size
    print(f"  {remote_path} ({size//1024}KB)")

    # 用cat + base64读取二进制文件
    stdin, stdout, stderr = c.exec_command(f"base64 {remote_path}", timeout=120)
    b64_data = stdout.read()
    raw_data = base64.b64decode(b64_data)

    with open(local_path, "wb") as f:
        f.write(raw_data)
    print(f"  -> {local_path} ({len(raw_data)//1024}KB saved)")

print("Downloading result files...")
os.makedirs(OUT_BASE, exist_ok=True)
for remote, local in REMOTE_FILES:
    download_file(remote, local)

# 统计下载了多少viz图片
print("\nChecking viz images...")
stdin, stdout, stderr = c.exec_command(
    f"find {REMOTE_DIR}/yolo_obstacle_results/viz -name '*.jpg' | wc -l", timeout=30)
viz_count = int(stdout.read().strip())
print(f"Viz images on server: {viz_count}")

sftp.close()
c.close()
print(f"\nDownload complete. Output: {OUT_BASE}/")
