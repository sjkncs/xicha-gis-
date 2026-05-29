#!/usr/bin/env python3
"""批量上传街景图像到GPU服务器"""
import paramiko, time
from pathlib import Path

HOST = "connect.bjb1.seetacloud.com"; PORT = 37625
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE_BASE = "/root/autodl-tmp/streetview_images"
LOCAL_DIR = Path(r"E:\xicha gis 智能定位\自选年份\baidu_streetview")

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

def mkdirtree(sftp, path):
    dirs = path.strip("/").split("/")
    for i in range(len(dirs)):
        partial = "/" + "/".join(dirs[:i+1])
        try: sftp.stat(partial)
        except FileNotFoundError: sftp.mkdir(partial)

c = ssh()
sftp = c.open_sftp()
mkdirtree(sftp, REMOTE_BASE)
print(f"Base: {REMOTE_BASE}")

local_imgs = sorted(LOCAL_DIR.rglob("*.jpg"))
print(f"Files: {len(local_imgs)}, Size: {sum(f.stat().st_size for f in local_imgs)/1024/1024:.1f} MB")

start = time.time(); uploaded = 0
for i, img in enumerate(local_imgs):
    rel = img.relative_to(LOCAL_DIR)
    remote = f"{REMOTE_BASE}/{rel.as_posix()}"
    mkdirtree(sftp, remote.rsplit("/",1)[0])
    sftp.put(str(img), remote)
    uploaded += img.stat().st_size
    if (i+1) % 30 == 0:
        spd = uploaded/(time.time()-start)/1024/1024
        print(f"  [{i+1}/{len(local_imgs)}] {uploaded/1024/1024:.1f}MB @ {spd:.1f}MB/s")

sftp.close(); c.close()
print(f"Done! {len(local_imgs)} files in {time.time()-start:.0f}s")
