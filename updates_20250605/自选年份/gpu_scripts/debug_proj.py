#!/usr/bin/env python3
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)

cmd = '''python3 << 'PYEOF'
import numpy as np
from pathlib import Path
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation

snap = "/root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default"
processor = AutoImageProcessor.from_pretrained(snap, local_files_only=True)
model = AutoModelForSemanticSegmentation.from_pretrained(snap, local_files_only=True)
device = torch.device("cuda")
model.to(device); model.eval()

# Test projection: does F view show road?
img_path = list(Path("/root/autodl-tmp/streetview_analysis/images").rglob("*.jpg"))[0]
img = Image.open(img_path).convert("RGB")
W, H = img.size
print(f"Image: {img_path.name}, size: {W}x{H}")

arr = np.array(img)

# Simple F projection using lon/lat formula
f = (512/2)/np.tan(np.radians(45.0))  # focal length
uu, vv = np.meshgrid(np.arange(512.0), np.arange(512.0))
rays_cam = np.stack([(uu-256)/f, (vv-256)/f, np.ones_like(uu)], axis=-1)

# rot_y(0) @ rot_x(0) = identity
valid = rays_cam[...,2] < 0
x,y,z = rays_cam[...,0], rays_cam[...,1], rays_cam[...,2]
lon = np.arctan2(x, -z)
norm = np.sqrt(x*x+y*y+z*z)+1e-8
lat = np.arcsin(np.clip(y/norm, -1, 1))
px = np.clip(((lon/(2*np.pi))+0.5)*W, 0, W-1).astype(np.int32)
py = np.clip((0.5-lat/np.pi)*H, 0, H-1).astype(np.int32)

proj_img = np.full((512,512,3),255,dtype=np.uint8)
proj_img[valid] = arr[py[valid], px[valid]]
print(f"Valid pixels: {np.sum(valid)}/{512*512}")

# Save projected image
Image.fromarray(proj_img).save("/root/autodl-tmp/proj_F.png")

# Segment it
inputs = processor(images=[Image.fromarray(proj_img)], return_tensors="pt").to(device)
with torch.no_grad():
    logits = model(**inputs).logits
seg = torch.argmax(logits[0], dim=0).cpu().numpy()
uniq, cnt = np.unique(seg, return_counts=True)
order = np.argsort(-cnt)
print("Top 15 classes in F view:")
for i in range(min(15, len(order))):
    idx = order[i]
    print(f"  class {uniq[idx]}: {cnt[idx]} ({cnt[idx]/seg.size*100:.1f}%)")
PYEOF'''

stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
out = stdout.read().decode()
err = stderr.read().decode()
print(out[:2000])
if err: print("ERR:", err[:500])

client.close()
