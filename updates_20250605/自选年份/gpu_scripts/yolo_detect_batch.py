#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch YOLO detection + accessibility heatmaps (street_view / ground_view).

Runs two Ultralytics models:
- YOLO11 COCO baseline (e.g. yolo11x.pt)
- YOLOv8 OpenImages v7 (e.g. yolov8x-oiv7.pt)

Produces:
- per-image JSONL
- merged JSON
- heatmaps in 3 styles: count_only / blocked_only / mixed

This script is designed to run on the remote server.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import cv2
import numpy as np


# ----------------------------
# Configuration
# ----------------------------

DEFAULT_ROI = {
    "x0": 0.10,
    "x1": 0.90,
    "y0": 0.55,
    "y1": 1.00,
}

DEFAULT_NEAR_Y = 0.60  # bbox bottom y >= this * H counts as "near"


# Heatmap tag groups. Keep stable regardless of model class-name differences.
TAG_GROUPS = {
    # 临时/施工障碍
    "cone": {"traffic cone", "cone"},
    "road_barrier": {"barrier", "barricade", "road barrier", "road block", "water barrier", "plastic road barrier"},
    "fence": {"fence", "construction fence", "construction barrier", "guardrail", "railing"},
    "construction_sign": {"construction sign", "traffic sign", "sign"},

    # 固定硬障碍
    "bollard": {"bollard", "stone bollard", "road bollard", "delineator", "delineator post"},
    "pole": {"pole", "utility pole", "lamp post", "street light", "streetlight", "light pole"},
    "trash_can": {"trash can", "garbage bin", "waste container", "waste bin", "bin", "dustbin", "dumpster"},
    "bench": {"bench"},

    # 占道移动/设施
    "person": {"person", "pedestrian"},
    "bicycle": {"bicycle"},
    "motorcycle": {"motorcycle", "scooter", "e-scooter"},
    "car": {"car", "van"},
    "truck": {"truck"},
    "bus": {"bus"},

    # Ground-view targets (often missing in common datasets, but keep placeholders)
    "stairs": {"stairs", "stair", "staircase", "steps", "step"},
    "ramp": {"ramp", "wheelchair ramp", "curb ramp", "dropped curb", "sloped curb", "curb cut"},
    "curb": {"curb", "kerb"},
    "pothole": {"pothole"},
    "speed_bump": {"speed bump", "road hump", "hump"},
    "tactile_paving": {"tactile paving", "guiding block"},
    "broken_pavement": {"cracked pavement", "broken pavement"},
}

# Weights used in count-only score.
TAG_WEIGHTS_COUNT = {
    "cone": 1.2,
    "road_barrier": 1.4,
    "bollard": 1.3,
    "fence": 0.9,
    "pole": 0.7,
    "trash_can": 0.9,
    "bench": 0.6,
    "bicycle": 0.8,
    "motorcycle": 1.0,
    "car": 1.1,
    "truck": 1.1,
    "bus": 1.1,
    # ground-view (if any model detects them)
    "stairs": 1.6,
    "ramp": 1.3,
    "curb": 1.1,
    "pothole": 1.6,
    "speed_bump": 1.2,
    "tactile_paving": 1.0,
    "broken_pavement": 1.2,
}

# Tags contributing to blocked_ratio_bbox (exclude person by default)
BLOCKING_TAGS = {
    "cone",
    "road_barrier",
    "bollard",
    "fence",
    "pole",
    "trash_can",
    "bench",
    "bicycle",
    "motorcycle",
    "car",
    "truck",
    "bus",
    # ground-view tags could also block if detected
    "stairs",
    "ramp",
    "curb",
}


# ----------------------------
# Utilities
# ----------------------------


def now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def iter_images(img_root: Path) -> List[Path]:
    exts = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}
    out: List[Path] = []
    for p in img_root.rglob("*"):
        if p.is_file() and p.suffix in exts:
            out.append(p)
    out.sort()
    return out


def rel_under(root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(root)).replace("\\", "/")
    except Exception:
        return p.name


def sigmoid_like(x: float, k: float) -> float:
    # 1 - exp(-x/k) maps [0,inf) -> [0,1)
    if k <= 0:
        return 0.0
    return float(1.0 - math.exp(-max(0.0, x) / k))


# ----------------------------
# view_type heuristic (no segmentation dependency)
# ----------------------------


def compute_view_type(img_bgr: np.ndarray) -> str:
    """Heuristic view type classifier.

    ground_view: ground texture dominates lower part
    street_view: otherwise
    """
    h, w = img_bgr.shape[:2]
    if h < 10 or w < 10:
        return "street_view"

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # Canny edges
    edges = cv2.Canny(gray, 80, 160)

    y_split = int(h * 0.55)
    bottom = edges[y_split:, :]
    top = edges[:y_split, :]

    bottom_density = float(np.mean(bottom > 0))
    top_density = float(np.mean(top > 0))

    # bottom contrast (texture)
    bottom_gray = gray[y_split:, :]
    contrast = float(np.std(bottom_gray) / 255.0)

    # groundness score
    groundness = bottom_density * 1.3 + contrast * 0.7
    verticalness = top_density * 1.2

    return "ground_view" if groundness > verticalness + 0.02 else "street_view"


# ----------------------------
# Mapping: model class name -> tag
# ----------------------------


def norm_name(name: str) -> str:
    return " ".join(name.strip().lower().replace("_", " ").split())


def build_name_to_tag(names: Iterable[str]) -> Dict[str, str]:
    """Map normalized class names to a stable tag key (TAG_GROUPS keys)."""
    out: Dict[str, str] = {}
    for raw in names:
        n = norm_name(str(raw))
        for tag, aliases in TAG_GROUPS.items():
            if n in {norm_name(a) for a in aliases}:
                out[n] = tag
                break
    return out


# ----------------------------
# Heatmap rendering from bboxes
# ----------------------------


def roi_rect(w: int, h: int, roi: Dict[str, float]) -> Tuple[int, int, int, int]:
    x0 = int(max(0, min(w - 1, roi["x0"] * w)))
    x1 = int(max(0, min(w, roi["x1"] * w)))
    y0 = int(max(0, min(h - 1, roi["y0"] * h)))
    y1 = int(max(0, min(h, roi["y1"] * h)))
    if x1 <= x0:
        x1 = min(w, x0 + 1)
    if y1 <= y0:
        y1 = min(h, y0 + 1)
    return x0, y0, x1, y1


def union_area_ratio(bboxes_xyxy: List[Tuple[float, float, float, float]], w: int, h: int, roi: Dict[str, float]) -> float:
    if not bboxes_xyxy:
        return 0.0

    x0, y0, x1, y1 = roi_rect(w, h, roi)
    roi_w = max(1, x1 - x0)
    roi_h = max(1, y1 - y0)

    mask = np.zeros((roi_h, roi_w), dtype=np.uint8)
    for (bx0, by0, bx1, by1) in bboxes_xyxy:
        ix0 = int(max(x0, min(x1, bx0)))
        ix1 = int(max(x0, min(x1, bx1)))
        iy0 = int(max(y0, min(y1, by0)))
        iy1 = int(max(y0, min(y1, by1)))
        if ix1 <= ix0 or iy1 <= iy0:
            continue
        mask[iy0 - y0 : iy1 - y0, ix0 - x0 : ix1 - x0] = 1

    return float(mask.mean())


def render_bbox_heat(img_bgr: np.ndarray, bboxes: List[Tuple[float, float, float, float]], intensity: float = 1.0) -> np.ndarray:
    """Render soft heat from bboxes onto image-sized grayscale heatmap."""
    h, w = img_bgr.shape[:2]
    heat = np.zeros((h, w), dtype=np.float32)

    for (x0, y0, x1, y1) in bboxes:
        x0i = int(max(0, min(w - 1, x0)))
        y0i = int(max(0, min(h - 1, y0)))
        x1i = int(max(0, min(w, x1)))
        y1i = int(max(0, min(h, y1)))
        if x1i <= x0i or y1i <= y0i:
            continue

        heat[y0i:y1i, x0i:x1i] += intensity

    # normalize and blur for nicer look
    if heat.max() > 0:
        heat = heat / heat.max()
    heat = cv2.GaussianBlur(heat, (0, 0), sigmaX=15, sigmaY=15)
    if heat.max() > 0:
        heat = heat / heat.max()

    heat_u8 = np.clip(heat * 255, 0, 255).astype(np.uint8)
    return heat_u8


def blend_heatmap(img_bgr: np.ndarray, heat_u8: np.ndarray, alpha_img: float = 0.60, alpha_heat: float = 0.40) -> np.ndarray:
    color = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
    blended = cv2.addWeighted(img_bgr, alpha_img, color, alpha_heat, 0)
    return blended


# ----------------------------
# YOLO inference wrapper
# ----------------------------


def load_ultralytics_model(model_path: str):
    from ultralytics import YOLO  # lazy import

    return YOLO(model_path)


def infer_yolo(model, img_bgr: np.ndarray, conf: float, iou: float, imgsz: int, device: str):
    # Ultralytics expects RGB or path; we pass numpy RGB
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    results = model.predict(
        source=img_rgb,
        conf=conf,
        iou=iou,
        imgsz=imgsz,
        device=device,
        verbose=False,
    )
    return results[0]


def extract_dets(result, name_to_tag: Dict[str, str]) -> List[Dict[str, Any]]:
    dets: List[Dict[str, Any]] = []
    names = result.names  # id -> name

    if result.boxes is None or len(result.boxes) == 0:
        return dets

    boxes = result.boxes
    xyxy = boxes.xyxy.cpu().numpy()
    conf = boxes.conf.cpu().numpy()
    cls = boxes.cls.cpu().numpy().astype(int)

    for (x0, y0, x1, y1), c, cid in zip(xyxy, conf, cls):
        raw_name = str(names.get(int(cid), str(cid)))
        n = norm_name(raw_name)
        tag = name_to_tag.get(n)

        dets.append(
            {
                "cls_id": int(cid),
                "name": raw_name,
                "name_norm": n,
                "tag": tag,  # may be None
                "conf": float(c),
                "xyxy": [float(x0), float(y0), float(x1), float(y1)],
            }
        )

    return dets


# ----------------------------
# Scoring & aggregation
# ----------------------------


def counts_by_tag(dets: List[Dict[str, Any]], h: int, near_y: float) -> Dict[str, int]:
    out: Dict[str, int] = {}
    y_thr = near_y * h

    for d in dets:
        tag = d.get("tag")
        if not tag:
            continue
        x0, y0, x1, y1 = d["xyxy"]
        if y1 < y_thr:
            continue
        out[tag] = out.get(tag, 0) + 1

    return out


def score_count_only(counts_near: Dict[str, int], k: float = 8.0) -> Tuple[float, float]:
    raw = 0.0
    for tag, cnt in counts_near.items():
        w = float(TAG_WEIGHTS_COUNT.get(tag, 0.0))
        raw += w * float(cnt)
    return raw, sigmoid_like(raw, k)


def bboxes_for_blocking(dets: List[Dict[str, Any]]) -> List[Tuple[float, float, float, float]]:
    out: List[Tuple[float, float, float, float]] = []
    for d in dets:
        tag = d.get("tag")
        if not tag or tag not in BLOCKING_TAGS:
            continue
        x0, y0, x1, y1 = d["xyxy"]
        out.append((x0, y0, x1, y1))
    return out


def merged_dets(d1: List[Dict[str, Any]], d2: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # For now, just concatenate; later we can do NMS across models if needed.
    return list(d1) + list(d2)


# ----------------------------
# Main
# ----------------------------


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument("--img_root", type=str, default="/root/autodl-tmp/streetview_analysis/images")
    ap.add_argument("--out_root", type=str, default="/root/autodl-tmp/streetview_analysis/output")
    ap.add_argument("--model_coco", type=str, default="/root/autodl-tmp/streetview_analysis/yolo_models/yolo11x.pt")
    ap.add_argument("--model_oiv7", type=str, default="/root/autodl-tmp/streetview_analysis/yolo_models/yolov8x-oiv7.pt")

    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--device", type=str, default="0")  # Ultralytics uses '0' for CUDA:0

    ap.add_argument("--near_y", type=float, default=DEFAULT_NEAR_Y)

    ap.add_argument("--roi_x0", type=float, default=DEFAULT_ROI["x0"])
    ap.add_argument("--roi_x1", type=float, default=DEFAULT_ROI["x1"])
    ap.add_argument("--roi_y0", type=float, default=DEFAULT_ROI["y0"])
    ap.add_argument("--roi_y1", type=float, default=DEFAULT_ROI["y1"])

    ap.add_argument("--limit", type=int, default=0, help="for quick tests, 0 = no limit")

    args = ap.parse_args()

    img_root = Path(args.img_root)
    out_root = Path(args.out_root)

    roi = {"x0": args.roi_x0, "x1": args.roi_x1, "y0": args.roi_y0, "y1": args.roi_y1}

    # output dirs
    yolo_out = out_root / "yolo"
    hm_root = out_root / "heatmaps"

    hm_count = hm_root / "yolo_count_only"
    hm_blocked = hm_root / "yolo_blocked_only"
    hm_mixed = hm_root / "yolo_mixed"

    for p in [yolo_out, hm_count, hm_blocked, hm_mixed]:
        safe_mkdir(p)
        safe_mkdir(p / "street_view")
        safe_mkdir(p / "ground_view")

    jsonl_path = yolo_out / "results_per_image.jsonl"
    merged_json_path = yolo_out / "results_merged.json"

    imgs = iter_images(img_root)
    if args.limit and args.limit > 0:
        imgs = imgs[: args.limit]

    print(f"[{now_ts()}] Found images: {len(imgs)} | root={img_root}")
    print(f"[{now_ts()}] Loading models...")

    model_coco = load_ultralytics_model(args.model_coco)
    model_oiv7 = load_ultralytics_model(args.model_oiv7)

    # Build name->tag maps using model.names
    coco_names = [str(v) for v in getattr(model_coco, "names", {}).values()] if hasattr(model_coco, "names") else []
    oiv7_names = [str(v) for v in getattr(model_oiv7, "names", {}).values()] if hasattr(model_oiv7, "names") else []

    name_to_tag_coco = build_name_to_tag(coco_names)
    name_to_tag_oiv7 = build_name_to_tag(oiv7_names)

    # Warmup: run on first image (optional)
    if imgs:
        img0 = cv2.imread(str(imgs[0]))
        if img0 is not None:
            _ = infer_yolo(model_coco, img0, args.conf, args.iou, args.imgsz, args.device)
            _ = infer_yolo(model_oiv7, img0, args.conf, args.iou, args.imgsz, args.device)

    all_rows: List[Dict[str, Any]] = []
    t_start = time.time()

    # append mode jsonl
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    with open(jsonl_path, "a", encoding="utf-8") as jf:
        for idx, img_path in enumerate(imgs, start=1):
            t0 = time.time()
            img = cv2.imread(str(img_path))
            if img is None:
                print(f"[{now_ts()}] WARN: failed to read: {img_path}")
                continue

            h, w = img.shape[:2]
            vt = compute_view_type(img)

            r_coco = infer_yolo(model_coco, img, args.conf, args.iou, args.imgsz, args.device)
            r_oiv7 = infer_yolo(model_oiv7, img, args.conf, args.iou, args.imgsz, args.device)

            dets_coco = extract_dets(r_coco, name_to_tag_coco)
            dets_oiv7 = extract_dets(r_oiv7, name_to_tag_oiv7)
            dets = merged_dets(dets_coco, dets_oiv7)

            counts_near = counts_by_tag(dets, h=h, near_y=args.near_y)
            score_count_raw, score_count_norm = score_count_only(counts_near)

            block_bboxes = bboxes_for_blocking(dets)
            blocked_ratio = union_area_ratio(block_bboxes, w=w, h=h, roi=roi)

            score_mixed = 0.6 * blocked_ratio + 0.4 * score_count_norm

            # heatmaps (bbox-based)
            heat_count = render_bbox_heat(img, block_bboxes, intensity=1.0)  # same bboxes; intensity controlled by score
            # for blocked/mixed we can reuse the same heat base; different filenames reflect scoring layer
            out_rel = rel_under(img_root, img_path)
            stem_safe = out_rel.replace("/", "_").replace("\\", "_")
            stem_safe = stem_safe.rsplit(".", 1)[0]

            out_count_path = hm_count / vt / f"{stem_safe}_yolo_count.jpg"
            out_blocked_path = hm_blocked / vt / f"{stem_safe}_yolo_blocked.jpg"
            out_mixed_path = hm_mixed / vt / f"{stem_safe}_yolo_mixed.jpg"

            # scale heat based on corresponding score
            def scaled_heat(base: np.ndarray, s: float) -> np.ndarray:
                # s in [0,1] -> scale intensity
                f = 0.2 + 0.8 * float(np.clip(s, 0.0, 1.0))
                out = np.clip(base.astype(np.float32) * f, 0, 255).astype(np.uint8)
                return out

            vis_count = blend_heatmap(img, scaled_heat(heat_count, score_count_norm))
            vis_blocked = blend_heatmap(img, scaled_heat(heat_count, blocked_ratio))
            vis_mixed = blend_heatmap(img, scaled_heat(heat_count, score_mixed))

            cv2.imwrite(str(out_count_path), vis_count)
            cv2.imwrite(str(out_blocked_path), vis_blocked)
            cv2.imwrite(str(out_mixed_path), vis_mixed)

            row = {
                "ts": now_ts(),
                "file": out_rel,
                "filename": img_path.name,
                "w": int(w),
                "h": int(h),
                "view_type": vt,
                "roi": roi,
                "scores": {
                    "count_only_raw": round(score_count_raw, 4),
                    "count_only": round(score_count_norm, 6),
                    "blocked_only": round(blocked_ratio, 6),
                    "mixed": round(score_mixed, 6),
                },
                "counts_near": counts_near,
                "models": {
                    "coco": os.path.basename(args.model_coco),
                    "oiv7": os.path.basename(args.model_oiv7),
                },
                "detections": {
                    "coco": dets_coco,
                    "oiv7": dets_oiv7,
                },
                "elapsed_s": round(time.time() - t0, 3),
            }

            jf.write(json.dumps(row, ensure_ascii=False) + "\n")
            all_rows.append(row)

            if idx % 10 == 0:
                elapsed = time.time() - t_start
                ips = len(all_rows) / max(elapsed, 0.001)
                print(f"[{now_ts()}] {idx}/{len(imgs)} | view={vt} | mixed={row['scores']['mixed']:.3f} | blocked={row['scores']['blocked_only']:.3f} | count={row['scores']['count_only']:.3f} | {ips:.2f} img/s")

    # write merged json
    with open(merged_json_path, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, ensure_ascii=False, indent=2)

    print(f"[{now_ts()}] DONE | wrote {len(all_rows)} rows")
    print(f"  jsonl: {jsonl_path}")
    print(f"  merged: {merged_json_path}")
    print(f"  heatmaps: {hm_root}")


if __name__ == "__main__":
    main()
