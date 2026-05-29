#!/usr/bin/env python3
"""Test full pipeline on server."""
import sys, numpy as np
from pathlib import Path
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation

snap = "/root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default"
processor = AutoImageProcessor.from_pretrained(snap, local_files_only=True)
model = AutoModelForSemanticSegmentation.from_pretrained(snap, local_files_only=True)
device = torch.device("cuda")
model.to(device); model.eval()

def rotation_matrix(angle_deg, axis="y"):
    a = np.radians(angle_deg)
    c, s = np.cos(a), np.sin(a)
    if axis == "y": return np.array([[c,0,s],[0,1,0],[-s,0,c]], dtype=np.float32)
    if axis == "x": return np.array([[1,0,0],[0,c,-s],[0,s,c]], dtype=np.float32)
    return np.eye(3)

def equirectangular_to_perspective(img, fov=90, yaw=0, pitch=0, W_out=512, H_out=512):
    W, H = img.size
    focal = W_out / (2 * np.tan(np.radians(fov / 2)))
    K = np.array([[focal,0,W_out/2],[0,focal,H_out/2],[0,0,1]], dtype=np.float32)
    R = np.linalg.multi_dot([rotation_matrix(pitch,axis="x"), rotation_matrix(yaw,axis="y")])
    R_h = np.array([[1,0,0,0],[0,-1,0,0],[0,0,-1,0]], dtype=np.float32)
    P = K @ R_h @ np.vstack([R,[0,0,0]])
    out = np.full((H_out,W_out,3),255,dtype=np.uint8)
    for v in range(H_out):
        for u in range(W_out):
            ray_local = np.linalg.inv(K) @ np.array([(u-W_out/2),(v-H_out/2),1.0])
            ray_global = R @ ray_local
            if ray_global[2] <= 1e-6: continue
            lat = np.arcsin(ray_global[1]/np.linalg.norm(ray_global))
            lon = np.arctan2(ray_global[0],ray_global[2])
            px = int((lon/(2*np.pi)+0.5)*W) % W
            py = int((0.5-lat/np.pi)*H)
            out[v,u] = img.getpixel((np.clip(px,0,W-1), np.clip(py,0,H-1)))
    return Image.fromarray(out)

VIEWS = [
    {"name":"F","fov":90,"yaw":0,"pitch":0},
    {"name":"B","fov":90,"yaw":180,"pitch":0},
    {"name":"L","fov":90,"yaw":-90,"pitch":0},
    {"name":"R","fov":90,"yaw":90,"pitch":0},
    {"name":"U","fov":90,"yaw":0,"pitch":-90},
    {"name":"D","fov":90,"yaw":0,"pitch":90},
]

@torch.no_grad()
def process_single(img_path):
    img = Image.open(img_path).convert("RGB")
    W_img, H_img = img.size
    OUT_SZ = 512

    fused = np.zeros((OUT_SZ, OUT_SZ), dtype=np.float32)
    for v in VIEWS:
        v_img = equirectangular_to_perspective(img, **{k:v[k] for k in ["fov","yaw","pitch"]}, W_out=OUT_SZ, H_out=OUT_SZ)
        inputs = processor(images=[v_img], return_tensors="pt").to(device)
        out = model(**inputs)
        logits = out.logits  # (1, 150, 128, 128)
        seg_flat = torch.argmax(logits[0], dim=0)  # (128, 128)
        seg_up = torch.nn.functional.interpolate(
            seg_flat.unsqueeze(0).unsqueeze(0).float(),
            size=(OUT_SZ, OUT_SZ), mode="nearest"
        )[0,0].cpu().numpy()
        uniq = np.unique(seg_up)
        print(f"  {v['name']}: unique={uniq[:10]}...")
        for idx in uniq:
            fused[seg_up == idx] = idx

    # Resize
    seg_full = Image.fromarray(fused.astype(np.uint8)).resize((W_img, H_img), Image.NEAREST)
    seg_np = np.array(seg_full)

    # Metrics
    CITY_CLASSES = {0:("road","road"),1:("sidewalk","road"),2:("building","building"),
        3:("wall","building"),5:("fence","other"),6:("pole","other"),7:("traffic_light","other"),
        8:("traffic_sign","other"),9:("vegetation","green"),10:("terrain","green"),
        11:("sky","sky"),12:("person","person"),13:("rider","person"),
        14:("car","car"),15:("truck","car"),16:("bus","car"),
        17:("train","car"),18:("motorcycle","car"),19:("bicycle","car")}
    CITY_KEYS = ["building","road","green","sky","person","car","other"]
    total = seg_np.size
    metrics = {}
    for k in CITY_KEYS:
        count = sum(np.sum(seg_np == v) for v, n in CITY_CLASSES.items() if n[1] == k)
        metrics[k] = float(count)/total*100

    # Show unique values in seg_full
    uniq_full = np.unique(seg_np)
    print(f"  seg_full unique classes: {uniq_full[:20]}")
    print(f"  seg_full shape: {seg_np.shape}, dtype: {seg_np.dtype}")
    print(f"  seg_full value range: {seg_np.min()}-{seg_np.max()}")
    print(f"  metrics: {metrics}")
    return metrics

# Test first 2 images
imgs = list(Path("/root/autodl-tmp/streetview_analysis/images").rglob("*.jpg"))[:2]
for img_path in imgs:
    print(f"\n=== {img_path.name} ===")
    process_single(img_path)
