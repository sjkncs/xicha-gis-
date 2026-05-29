#!/usr/bin/env python3
"""Download yolov8x-oiv7.pt using Python urllib and upload to remote."""
import os, ssl, urllib.request, paramiko

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
MODEL_DIR = "/root/autodl-tmp/streetview_analysis/yolo_models"
URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8x-oiv7.pt"
LOCAL_TMP = "C:/temp_yolov8x_oiv7.pt"

print("=== Downloading yolov8x-oiv7.pt ===")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
urllib.request.urlretrieve(URL, LOCAL_TMP)
local_size = os.path.getsize(LOCAL_TMP)
print(f"Downloaded locally: {local_size // 1024 // 1024}MB")

print("=== Uploading to remote ===")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
sftp = c.open_sftp()
remote_path = f"{MODEL_DIR}/yolov8x-oiv7.pt"
sftp.put(LOCAL_TMP, remote_path)
size = sftp.stat(remote_path).st_size
print(f"Remote size: {size // 1024 // 1024}MB")
os.remove(LOCAL_TMP)
sftp.close(); c.close()
print("Done!")
