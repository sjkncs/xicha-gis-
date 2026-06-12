#!/usr/bin/env python3
"""Simple debug: just test F view segmentation and check class distribution."""
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
    K = np.array([[f,0,W_out/2],[0,f,H_out/2],[0,0,1]],dtype=np.float32)
    R = rot_y(np.radians(yaw_deg)) @ rot_x(np.radians(pitch_deg))
    us = np.arange(W_out, dtype=np.float32)
    vs = np.arange(H_out, dtype=np.float32)
    uu, vv = np.meshgrid(us, vs)
    rays_cam = np.stack([(uu-W_out/2)/f, (vv-H_out/2)/f, np.ones_like(uu)], axis=-1)
    rays_world = rays_cam @ R.T
    valid = rays_world[...,2] < 0
    x,y,z = rays_world[...,0], rays_world[...,1], rays_world[...,2]
    lon = np.arctan2(x, -z)
    norm = np.sqrt(x*x+y*y+z*z)+1e-8
    lat = np.arcsin(np.clip(y/norm, -1, 1))
    px = np.clip(((lon/(2*np.pi))+0.5)*W, 0, W-1).astype(np.int32)
    py = np.clip(((0.5-lat/np.pi))*H, 0, H-1).astype(np.int32)
    out = np.full((H_out,W_out,3),255,dtype=np.uint8)
    out[valid] = arr[py[valid], px[valid]]
    return Image.fromarray(out)

# Test F view
img_path = list(Path("/root/autodl-tmp/streetview_analysis/images").rglob("*.jpg"))[0]
print(f"Image: {img_path.name}, size: {Image.open(img_path).size}")
img = Image.open(img_path).convert("RGB")

v_img = proj(img, yaw_deg=0, pitch_deg=0)
print(f"Proj F view: {np.array(v_img).shape}")

inputs = processor(images=[v_img], return_tensors="pt").to(device)
with torch.no_grad():
    logits = model(**inputs).logits
print(f"Logits: {logits.shape}")

seg = torch.argmax(logits[0], dim=0).cpu().numpy()
print(f"Seg shape: {seg.shape}, unique: {np.unique(seg)[:20]}")
print(f"Total valid (non-255) pixels: {np.sum(np.array(v_img) != 255)}")

# Distribution
uniq, cnt = np.unique(seg, return_counts=True)
order = np.argsort(-cnt)
for i in range(min(15, len(order))):
    idx = order[i]
    print(f"  class {uniq[idx]}: {cnt[idx]} ({cnt[idx]/seg.size*100:.1f}%)")
