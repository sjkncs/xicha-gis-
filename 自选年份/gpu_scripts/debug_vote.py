#!/usr/bin/env python3
"""Debug vote fusion on server."""
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
    c, s = np.cos(a), np.sin(a)
    return np.array([[c,0,-s],[0,1,0],[s,0,c]], dtype=np.float32)
def rot_x(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1,0,0],[0,c,s],[0,-s,c]], dtype=np.float32)

def equirectangular_to_perspective(img, yaw_deg, pitch_deg, W_out=512, H_out=512):
    W, H = img.size
    arr = np.array(img)
    fov, f = 90.0, (W_out/2)/np.tan(np.radians(45.0))
    K = np.array([[f,0,W_out/2],[0,f,H_out/2],[0,0,1]], dtype=np.float32)
    R = rot_y(np.radians(yaw_deg)) @ rot_x(np.radians(pitch_deg))
    us = np.arange(W_out, dtype=np.float32)
    vs = np.arange(H_out, dtype=np.float32)
    uu, vv = np.meshgrid(us, vs)
    rays_cam = np.stack([(uu-W_out/2)/f, (vv-H_out/2)/f, np.ones_like(uu)], axis=-1)
    rays_world = rays_cam @ R.T
    valid = rays_world[..., 2] < 0
    x, y, z = rays_world[..., 0], rays_world[..., 1], rays_world[..., 2]
    lon = np.arctan2(x, -z)
    lat = np.arcsin(np.clip(y / (np.sqrt(x**2+y**2+z**2)+1e-8), -1, 1))
    px_f = np.clip(((lon/(2*np.pi)+0.5)*W, 0, W-1)).astype(np.int32)
    py_f = np.clip(((0.5-lat/np.pi)*H, 0, H-1)).astype(np.int32)
    out = np.full((H_out,W_out,3),255,dtype=np.uint8)
    out[valid] = arr[py_f[valid], px_f[valid]]
    return Image.fromarray(out)

VIEWS = [
    {"name":"F","yaw":0},{"name":"R","yaw":90},
    {"name":"B","yaw":180},{"name":"L","yaw":-90},
]

img_path = list(Path("/root/autodl-tmp/streetview_analysis/images").rglob("*.jpg"))[0]
print(f"Test: {img_path.name}")
img = Image.open(img_path).convert("RGB")

vote_maps = {}
for v in VIEWS:
    v_img = equirectangular_to_perspective(img, yaw_deg=v["yaw"], pitch_deg=0)
    inputs = processor(images=[v_img], return_tensors="pt").to(device)
    with torch.no_grad():
        logits = model(**inputs).logits
    seg_up = torch.nn.functional.interpolate(logits.float(), size=(512,512), mode="nearest")[0,0].cpu().numpy()
    uniq = np.unique(seg_up)
    print(f"  {v['name']}: unique={uniq[:15]}, shape={seg_up.shape}")
    for cls_id in uniq:
        cid = int(cls_id)
        mask = (seg_up == cls_id)
        if cid not in vote_maps:
            vote_maps[cid] = np.zeros((512,512), dtype=np.float32)
        vote_maps[cid] += mask.astype(np.float32)

print(f"\nVote map keys: {sorted(vote_maps.keys())}")
seg_fused = np.full((512,512), 0, dtype=np.int32)
seg_votes = np.zeros((512,512), dtype=np.float32)
for cls_id, accum in sorted(vote_maps.items()):
    mask = accum > seg_votes
    seg_fused[mask] = cls_id
    seg_votes[mask] = accum[mask]

uniq_fused = np.unique(seg_fused)
print(f"Fused unique: {uniq_fused}")
print(f"Fused dtype: {seg_fused.dtype}")

# Check class 11 (sky)
sky_mask = seg_fused == 11
print(f"Class 11 (sky) pixels: {np.sum(sky_mask)}")

# Check what percentage of the FOV has valid segmentation
for cls_id in [0, 1, 2, 9, 10, 11]:
    cnt = np.sum(seg_fused == cls_id)
    print(f"  Class {cls_id}: {cnt} pixels ({cnt/262144*100:.1f}%)")
