#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GPU全景语义分割 - SegFormer B3 ADE20K 离线版 (无 torchvision)"""
from __future__ import print_function
import os, sys, json, time, csv, math, torch
from pathlib import Path
from PIL import Image
import numpy as np
import cv2

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HOME"] = "/root/gis_project/models"
os.environ["TRANSFORMERS_CACHE"] = "/root/gis_project/models"

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_LOCAL = "/root/gis_project/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default"
DATA_DIR = Path("/root/gis_project/data/baidu_streetview")
OUT_DIR = Path("/root/gis_project/outputs/segmentation")
VIZ_DIR = OUT_DIR / "viz"
CHECKPOINT = OUT_DIR / "checkpoint.json"
LOG_FILE = Path("/root/gis_project/logs/seg_inference_offline.log")

OUT_DIR.mkdir(parents=True, exist_ok=True)
VIZ_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

CITY_CLASSES = {
    "building": list(range(0, 12)),
    "road": [200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210],
    "sidewalk": [216, 217],
    "green": list(range(120, 160)),
    "sky": list(range(182, 192)),
    "vehicle": [193, 194, 195, 196, 197, 198, 199],
    "person": [12, 13, 14, 15, 16],
    "water": [180, 181],
}

COLOR_MAP = {}
_color_pairs = [
    (0,180,50),(1,180,50),(2,180,50),(3,180,50),(4,180,50),(5,180,50),(6,180,50),(7,180,50),
    (8,180,50),(9,180,50),(10,180,50),(11,180,50),
    (120,0,200),(121,0,180),(122,0,160),(123,0,140),(124,0,120),
    (150,0,140),(151,0,130),(152,0,120),
    (200,180,180),(201,180,180),(202,175,175),(203,170,170),
    (216,160,160),(217,160,160),
    (193,255,100),(194,255,100),(195,255,100),
    (12,0,0),(13,0,0),(14,0,255),(15,0,200),(16,0,150),
    (182,135,206),(183,135,220),(184,135,235),(185,150,240),(186,160,250),
    (180,0,100),(181,0,150),
]
for _cp in _color_pairs:
    COLOR_MAP[_cp[0]] = (_cp[1], _cp[2])

ADE20K_MEAN = [0.485, 0.456, 0.406]
ADE20K_STD  = [0.229, 0.224, 0.225]


def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = "[{}] {}".format(ts, msg)
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_checkpoint():
    if CHECKPOINT.exists():
        with open(CHECKPOINT) as f:
            return json.load(f)
    return {"done": [], "results": []}


def save_checkpoint(data):
    with open(CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_model():
    from transformers import AutoConfig, AutoModel
    log("Loading model from: {}".format(MODEL_LOCAL))
    t0 = time.time()

    config = AutoConfig.from_pretrained(MODEL_LOCAL, local_files_only=True)
    config.output_hidden_states = False

    state = {}
    bin_file = Path(MODEL_LOCAL) / "pytorch_model.bin"
    if bin_file.exists():
        state = torch.load(bin_file, map_location="cpu", weights_only=True)
    else:
        safetensors_file = Path(MODEL_LOCAL) / "model.safetensors"
        log("ERROR: No model file found: {} or {}".format(bin_file, safetensors_file))
        sys.exit(1)

    model = AutoModel.from_config(config)
    model.load_state_dict(state, strict=False)
    model = model.to(DEVICE)
    model.eval()
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A"
    log("Model loaded: {:.1f}s | GPU: {}".format(time.time()-t0, gpu_name))
    return model


def normalize_image(img_pil, target_size=512):
    img = img_pil.convert("RGB").resize((target_size, target_size), Image.LANCZOS)
    arr = np.array(img).astype(np.float32) / 255.0
    for i in range(3):
        arr[:,:,i] = (arr[:,:,i] - ADE20K_MEAN[i]) / ADE20K_STD[i]
    tensor = torch.from_numpy(arr.transpose(2, 0, 1)).float()
    return tensor


def predict_seg(logits):
    upscaled = torch.nn.functional.interpolate(
        logits, size=(512, 512), mode="bilinear", align_corners=False
    )
    return upscaled.argmax(dim=1).squeeze(0).cpu().numpy()


def equirectangular_to_perspective(equirect, yaw, pitch, fov_h, fov_v, out_w, out_h):
    w_img, h_img = equirect.size
    output = np.zeros((out_h, out_w, 3), dtype=np.uint8)
    yr = math.radians(yaw)
    pr = math.radians(pitch)
    fhr = math.radians(fov_h)
    fvr = math.radians(fov_v)
    fx = (out_w / 2.0) / math.tan(fhr / 2.0)
    fy = (out_h / 2.0) / math.tan(fvr / 2.0)
    arr = np.array(equirect)
    cp = math.cos(pr)
    sp = math.sin(pr)
    cy = math.cos(yr)
    sy = math.sin(yr)
    for v in range(out_h):
        dv = (v - out_h / 2.0) / fy
        for u in range(out_w):
            du = (u - out_w / 2.0) / fx
            rx = du * cp * cy - dv * sp * sy
            ry = du * sp + dv * cp
            rz = -du * cp * sy + dv * sp * cy + 1.0
            r = math.sqrt(rx*rx + ry*ry + rz*rz)
            if rz == 0:
                continue
            theta = math.acos(rz / r)
            phi = math.atan2(ry, rx)
            px = int((phi / (2*math.pi) + 0.5) * w_img) % w_img
            py = int((theta / math.pi) * h_img)
            if 0 <= py < h_img:
                output[v, u] = arr[py, px]
    return Image.fromarray(output)


def process_single(img_path, model):
    try:
        img = Image.open(img_path).convert("RGB")
        yaws = [-150, -90, -30, 30, 90, 150]
        weights = [0.08, 0.17, 0.25, 0.25, 0.17, 0.08]

        views = []
        for yaw in yaws:
            v = equirectangular_to_perspective(img, yaw, 0, 60, 50, 512, 512)
            views.append(v)

        seg_maps = []
        with torch.no_grad():
            for i in range(0, len(views), 4):
                batch_views = views[i:i+4]
                tensors = torch.stack([normalize_image(v) for v in batch_views]).to(DEVICE)
                outputs = model(tensors)
                logits = outputs.logits
                for j in range(logits.shape[0]):
                    pred = predict_seg(logits[j:j+1])
                    seg_maps.append(pred)

        h, w = seg_maps[0].shape
        counts = np.zeros((h, w, 150), dtype=np.float32)
        for seg_map, wgt in zip(seg_maps, weights):
            for cid in range(150):
                counts[:,:,cid] += (seg_map == cid).astype(np.float32) * wgt

        combined = counts.argmax(axis=2).astype(np.uint8)
        metrics = compute_metrics(combined)
        metrics["pano_name"] = img_path.name
        metrics["num_views"] = len(views)
        return metrics, combined
    except Exception as e:
        log("  FAIL {}: {}".format(img_path.name, e))
        import traceback
        traceback.print_exc()
        return None, None


def compute_metrics(pred):
    total = pred.size
    if total == 0:
        return {}
    m = {}
    for name, ids in CITY_CLASSES.items():
        count = np.isin(pred, ids).sum()
        m["pct_" + name] = round(float(count) / total * 100, 2)
    b = m.get("pct_building", 0)
    r = m.get("pct_road", 0)
    g = m.get("pct_green", 0)
    s = m.get("pct_sky", 0)
    m["openness"] = round((s + g + r) / max(b, 1) * 10, 2)
    m["building_density"] = round(b / 10, 2)
    m["walkability"] = round((g*0.3 + r*0.4 + s*0.2 + (100-b)*0.1) / 100 * 10, 2)
    return m


def create_overlay(img_path, mask):
    img = cv2.imread(str(img_path))
    h, w = mask.shape
    img = cv2.resize(img, (w, h), interpolation=cv2.INTER_LANCZOS4)
    color_mask = np.zeros((h, w, 3), dtype=np.uint8)
    for cls_id, rgb in COLOR_MAP.items():
        color_mask[mask == cls_id] = rgb
    overlay = cv2.addWeighted(img, 0.5, color_mask, 0.5, 0)
    return overlay


def main():
    log("=== GPU Semantic Segmentation ===")
    log("Output: {}".format(OUT_DIR))
    log("Device: {}".format(DEVICE))

    model = load_model()
    checkpoint = load_checkpoint()
    done = set(checkpoint["done"])

    image_files = sorted(DATA_DIR.glob("*.jpg")) + sorted(DATA_DIR.glob("*.JPG")) + \
                  sorted(DATA_DIR.glob("*.png")) + sorted(DATA_DIR.glob("*.PNG"))
    total = len(image_files)
    log("Found {} images in {}".format(total, DATA_DIR))

    results = list(checkpoint.get("results", []))
    processed = 0

    for idx, img_path in enumerate(image_files):
        if img_path.name in done:
            continue
        log("  [{}/{}] {}".format(idx+1, total, img_path.name))
        t0 = time.time()
        metrics, mask = process_single(img_path, model)
        elapsed = time.time() - t0

        if metrics is not None:
            metrics["elapsed_s"] = round(elapsed, 2)
            results.append(metrics)
            done.add(img_path.name)

            overlay = create_overlay(img_path, mask)
            out_path = VIZ_DIR / (img_path.stem + "_overlay.png")
            cv2.imwrite(str(out_path), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
            log("  OK: {}s | building={}% road={}% green={}% sky={}%".format(
                round(elapsed, 1),
                metrics.get("pct_building", 0),
                metrics.get("pct_road", 0),
                metrics.get("pct_green", 0),
                metrics.get("pct_sky", 0),
            ))

            checkpoint["done"] = list(done)
            checkpoint["results"] = results
            save_checkpoint(checkpoint)
            processed += 1

            if processed % 10 == 0:
                save_csv(results)

    save_csv(results)
    log("DONE! Processed {} images".format(processed))


def save_csv(results):
    if not results:
        return
    csv_path = OUT_DIR / "segmentation_metrics.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fields = ["pano_name","num_views","elapsed_s",
                  "pct_building","pct_road","pct_sidewalk","pct_green",
                  "pct_sky","pct_vehicle","pct_person","pct_water",
                  "openness","building_density","walkability"]
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)
    log("CSV saved: {}".format(csv_path))


if __name__ == "__main__":
    main()
