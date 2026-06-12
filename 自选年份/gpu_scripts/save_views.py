#!/usr/bin/env python3
"""Save a projected F view on server."""
import numpy as np
from pathlib import Path
from PIL import Image

def rot_y(a):
    c,s = np.cos(a),np.sin(a)
    return np.array([[c,0,-s],[0,1,0],[s,0,c]],dtype=np.float32)
def rot_x(a):
    c,s = np.cos(a),np.sin(a)
    return np.array([[1,0,0],[0,c,s],[0,-s,c]],dtype=np.float32)

def proj(img, yaw_deg, pitch_deg, W_out=512, H_out=512):
    W, H = img.size
    arr = np.array(img)
    f = (W_out/2)/np.tan(np.radians(45.0))
    us = np.arange(W_out, dtype=np.float32)
    vs = np.arange(H_out, dtype=np.float32)
    uu, vv = np.meshgrid(us, vs)
    rays_cam = np.stack([(uu-W_out/2)/f, (vv-H_out/2)/f, -np.ones_like(uu)], axis=-1)
    R = rot_y(np.radians(yaw_deg)) @ rot_x(np.radians(pitch_deg))
    rays_world = rays_cam @ R.T
    valid = rays_world[...,2] < 0
    x,y,z = rays_world[...,0], rays_world[...,1], rays_world[...,2]
    norm = np.sqrt(x*x+y*y+z*z)+1e-8
    lon = np.arctan2(x, -z)
    lat = np.arcsin(np.clip(y / norm, -1, 1))
    px = np.clip(((lon/(2*np.pi))+0.5)*W, 0, W-1).astype(np.int32)
    py = np.clip(((np.pi/2-lat)/np.pi)*H, 0, H-1).astype(np.int32)
    out = np.full((H_out,W_out,3),255,dtype=np.uint8)
    out[valid] = arr[py[valid], px[valid]]
    return Image.fromarray(out)

img_path = list(Path("/root/autodl-tmp/streetview_analysis/images").rglob("*.jpg"))[0]
img = Image.open(img_path).convert("RGB")
print(f"Image: {img_path.name}, size: {img.size}")

for yaw_deg, name in [(0,"F"), (90,"R"), (180,"B"), (-90,"L")]:
    v_img = proj(img, yaw_deg, 0)
    v_img.save(f"/root/autodl-tmp/view_{name}.png")
    arr = np.array(v_img)
    valid = np.sum(arr[:,:,0] != 255)
    print(f"  {name} view: valid={valid}/{512*512}")

# Also save original
img.save("/root/autodl-tmp/original.png")
print("Saved views.")
