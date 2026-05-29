#!/usr/bin/env python3
"""Verify projection on server."""
import numpy as np
from pathlib import Path
from PIL import Image

img_path = list(Path("/root/autodl-tmp/streetview_analysis/images").rglob("*.jpg"))[0]
img = Image.open(img_path).convert("RGB")
W, H = img.size
arr = np.array(img)

f = (512/2)/np.tan(np.radians(45.0))
uu, vv = np.meshgrid(np.arange(512.0), np.arange(512.0))

# Camera rays pointing at z=-1 (forward hemisphere)
rays_cam = np.stack([(uu-256)/f, (vv-256)/f, -np.ones_like(uu)], axis=-1)
R = np.eye(3)
rays_world = rays_cam @ R.T

valid = rays_world[..., 2] < 0
x, y, z = rays_world[..., 0], rays_world[..., 1], rays_world[..., 2]
print(f"Valid: {np.sum(valid)}/{512*512}")

lon = np.arctan2(x, -z)
norm = np.sqrt(x*x+y*y+z*z)+1e-8
lat = np.arcsin(np.clip(y/norm, -1, 1))

# Old formula (wrong for top=py=0):
py_old = ((0.5 - lat/np.pi) * H).astype(np.int32)
# Fixed formula:
py_new = ((np.pi/2 - lat) / np.pi * H).astype(np.int32)

px = np.clip(((lon/(2*np.pi))+0.5)*W, 0, W-1).astype(np.int32)

proj_old = np.full((512,512,3),255,dtype=np.uint8)
proj_old[valid] = arr[np.clip(py_old[valid],0,H-1), np.clip(px[valid],0,W-1)]

proj_new = np.full((512,512,3),255,dtype=np.uint8)
proj_new[valid] = arr[np.clip(py_new[valid],0,H-1), np.clip(px[valid],0,W-1)]

Image.fromarray(proj_old).save("/root/autodl-tmp/proj_old.png")
Image.fromarray(proj_new).save("/root/autodl-tmp/proj_new.png")

# Check what each version produces
print(f"proj_old: sky pixels (blue check) = {np.sum(np.all(proj_old[:,:,2]>200, axis=-1) & np.all(proj_old[:,:,0]<50, axis=-1))}")
print(f"proj_new: sky pixels (blue check) = {np.sum(np.all(proj_new[:,:,2]>200, axis=-1) & np.all(proj_new[:,:,0]<50, axis=-1))}")
print("Saved to /root/autodl-tmp/proj_old.png and proj_new.png")
