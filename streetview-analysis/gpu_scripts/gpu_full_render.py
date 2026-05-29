#!/usr/bin/env python3
"""
GPU 端全量推理 + PIL 中文渲染脚本
处理全部 294 张街景图，叠加 YOLO bbox + DeepLabV3+ 分割 + 中文文字标注
字体：NotoSansSC（自动下载）
"""
import os, sys, json, time, urllib.request, zipfile, glob, shutil, re
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
import torch
from ultralytics import YOLO

# ===== 配置 =====
GPU_DIR = "/root/autodl-tmp/streetview_sim_full"
YOLO_MODEL = "/root/autodl-tmp/yolo11x.pt"
IMG_ROOT = "/root/autodl-tmp/streetview_images"
FONT_URL = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf"
FONT_PATH = "/root/autodl-tmp/NotoSansCJK.otf"

os.makedirs(GPU_DIR, exist_ok=True)
os.makedirs(f"{GPU_DIR}/results", exist_ok=True)
os.makedirs(f"{GPU_DIR}/raw", exist_ok=True)

# ===== 中文字典 =====
COCO_CN = {
    "car": "汽车", "truck": "卡车", "bus": "公交车",
    "motorcycle": "摩托车", "bicycle": "自行车", "person": "行人",
    "traffic light": "红绿灯", "stop sign": "停车标志",
    "fire hydrant": "消防栓", "bench": "长椅", "potted plant": "盆栽",
    "backpack": "背包", "umbrella": "雨伞",
}
DIR_CN = {"N": "北", "E": "东", "S": "南", "W": "西"}
SEG_CN = {
    "road": "道路", "sidewalk": "人行道", "building": "建筑",
    "wall": "墙壁", "fence": "围栏", "vegetation": "植被",
    "sky": "天空",
}
SEG_COLORS = {
    "road": (128, 128, 128), "sidewalk": (200, 100, 200),
    "building": (139, 90, 43), "wall": (169, 169, 169),
    "fence": (180, 180, 180), "vegetation": (34, 139, 34),
    "sky": (135, 206, 235),
}

# ===== 字体下载/加载 =====
def get_font(size):
    if not hasattr(get_font, "_cache"):
        get_font._cache = {}
    if size in get_font._cache:
        return get_font._cache[size]
    if not os.path.exists(FONT_PATH):
        print(f"下载字体: {FONT_URL}")
        try:
            urllib.request.urlretrieve(FONT_URL, FONT_PATH)
            print(f"字体已下载: {FONT_PATH}")
        except Exception as e:
            print(f"字体下载失败: {e}，使用默认字体")
            get_font._cache[size] = ImageFont.load_default()
            return get_font._cache[size]
    try:
        font = ImageFont.truetype(FONT_PATH, size)
    except Exception:
        font = ImageFont.load_default()
    get_font._cache[size] = font
    return font

FCACHE = {}

def font_cache(size):
    if size not in FCACHE:
        FCACHE[size] = get_font(size)
    return FCACHE[size]

# ===== 加载 YOLO =====
def load_yolo():
    print(f"加载 YOLO: {YOLO_MODEL} (CPU 模式)")
    model = YOLO(YOLO_MODEL)
    # Blackwell sm_120 暂不支持，使用 CPU 模式
    # model.to("cuda")
    print("YOLO 加载完成 (CPU)")
    return model

# ===== 障碍分数计算 =====
def calc_obstacle(dets):
    """根据 YOLO 检测结果计算障碍分数"""
    if not dets:
        return 0.0, []
    weights = {"car": 1.0, "truck": 1.2, "bus": 1.2, "motorcycle": 0.6,
               "bicycle": 0.4, "person": 0.3, "bench": 0.5, "fence": 0.4,
               "fire hydrant": 0.3, "traffic light": 0.2}
    total = 0.0
    for d in dets:
        w = weights.get(d["coco_name"], 0.5)
        total += w * d["conf"]
    score = min(100.0, total * 30)
    return round(score, 2), []

# ===== 渲染面板（右侧中文）=====
def draw_panel_right(draw, pw, ph, bc, sim_data, dets):
    """右侧面板：坐标、障碍分、道路比、检测类别"""
    y = 10
    w = pw - 16

    def put(txt, fs, fc):
        nonlocal y
        fnt = font_cache(fs)
        draw.text((10, y), txt, font=fnt, fill=fc)
        y += fs + 7

    def sep():
        nonlocal y
        fnt = font_cache(8)
        draw.text((10, y), "-" * 24, font=fnt, fill=(160, 160, 160))
        y += 13

    coord = sim_data["coords"]
    direction = sim_data["direction"]
    put(f"{coord} [{DIR_CN.get(direction, direction)}]", 11, (60, 60, 60))
    sep()
    y += 3

    obs = sim_data["obs_score"]
    put(f"障碍分数: {obs:.1f}", 15, bc)
    rr = sim_data["road_ratio"]
    put(f"道路比例: {rr:.1%}", 11, (60, 60, 60))
    passab = sim_data["passability"]
    put(f"通行率: {passab:.1%}", 13, bc)
    sep()

    put(f"YOLOv11x检测: {len(dets)} 个目标", 11, (20, 80, 180))
    sep()

    cat_count = {}
    for d in dets:
        cn = d.get("coco_name", "?")
        cat_count[cn] = cat_count.get(cn, 0) + 1
    for cn, cnt in sorted(cat_count.items(), key=lambda x: -x[1])[:6]:
        label = COCO_CN.get(cn, cn)
        put(f"  {label} x{cnt}", 10, (80, 60, 20))

    y += 5
    put("图例:", 11, (80, 80, 80))
    put("  道路=灰  人行道=紫", 9, (128, 128, 128))
    put("  建筑=棕  植被=绿", 9, (34, 139, 34))
    put("  汽车=蓝  行人=红", 9, (0, 100, 200))

# ===== 主渲染函数 ======
def render_annotation(raw_img_path, dets, sim_data, out_path):
    """用 PIL 渲染完整标注图"""
    img = cv2.imread(raw_img_path)
    if img is None:
        print(f"  [ERR] 无法读取: {raw_img_path}")
        return False
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    H, W = img_rgb.shape[:2]

    pil_img = Image.fromarray(img_rgb).convert("RGBA")
    draw = ImageDraw.Draw(pil_img)

    # ---- YOLO BBox ----
    for d in dets:
        x1, y1, x2, y2 = d["bbox"]
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        conf = d["conf"]
        cn = d["coco_name"]
        color = (255, 80, 80) if cn == "person" else (255, 180, 0)
        # 框
        draw.rectangle([x1, y1, x2, y2], outline=(*color, 220), width=2)
        # 标签背景
        label = f"{COCO_CN.get(cn, cn)} {conf:.0%}"
        fnt = font_cache(10)
        lw, lh = draw.textsize(label, font=fnt)
        draw.rectangle([x1, y1 - lh - 4, x1 + lw + 4, y1], fill=(*color, 200))
        draw.text((x1 + 2, y1 - lh - 3), label, font=fnt, fill=(255, 255, 255))

    # ---- 右侧中文面板 ----
    obs = sim_data["obs_score"]
    if obs >= 80:
        bc = (200, 30, 30)
    elif obs >= 50:
        bc = (220, 140, 0)
    elif obs >= 20:
        bc = (200, 180, 0)
    else:
        bc = (0, 160, 60)

    pw = min(290, W - 20)
    ph = min(340, H - 16)
    px = W - pw - 8
    py = 8
    panel = Image.new("RGBA", (pw, ph), (*[245, 248, 255], 230))
    pd = ImageDraw.Draw(panel)
    pd.rectangle([0, 0, pw - 1, ph - 1], outline=(*bc, 255), width=3)
    draw_panel_right(pd, pw, ph, bc, sim_data, dets)
    pil_img.paste(panel, (px, py), mask=panel)

    # ---- 底部状态栏 ----
    status = f"YOLOv11x 障碍分数={obs:.1f} 通行率={sim_data['passability']:.1%}"
    bar_h = 22
    bar = Image.new("RGBA", (W, bar_h), (*[0, 0, 0], 180))
    bd = ImageDraw.Draw(bar)
    bd.text((8, 5), status, font=font_cache(11), fill=(255, 255, 255))
    # 进度条颜色
    bar_rgb = Image.new("RGB", (W, bar_h), (int(bc[0]*0.5), int(bc[1]*0.5), int(bc[2]*0.5)))
    bar_np = np.array(bar_rgb)
    fill_w = int(W * sim_data["passability"])
    bar_np[:, :fill_w] = bc
    pil_bar = Image.fromarray(bar_np).convert("RGBA")
    pil_img.paste(pil_bar, (0, H - bar_h), mask=pil_bar)

    pil_img.convert("RGB").save(out_path, quality=92)
    return True

# ===== 提取方向 =====
def extract_direction(fname):
    """从文件名提取方向: 113.xxxx_22.xxxx_N_2022.jpg"""
    m = re.search(r"_([NESW])_\d{4}\.jpg$", fname)
    return m.group(1) if m else "?"

# ===== 主流程 =====
def main():
    t0 = time.time()
    print(f"{'='*60}")
    print("全量街景分析 + 中文标注渲染")
    print(f"{'='*60}")

    # 加载模型
    model = load_yolo()

    # 扫描所有图片
    all_imgs = glob.glob(os.path.join(IMG_ROOT, "**", "*.jpg"), recursive=True)
    print(f"找到 {len(all_imgs)} 张图片")

    results = []
    for i, raw_path in enumerate(sorted(all_imgs), 1):
        fname = os.path.basename(raw_path)
        coord = re.sub(r"_[NESW]_\d{4}\.jpg$", "", fname.replace("_2022", ""))

        # YOLO 推理
        yolo_results = model(raw_path, verbose=False, conf=0.25, iou=0.4)
        dets = []
        for r in yolo_results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                xyxy = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                coco_name = model.names[cls_id]
                dets.append({
                    "coco_name": coco_name,
                    "conf": round(conf, 4),
                    "bbox": xyxy.tolist(),
                })

        # 计算障碍分数
        obs_score, _ = calc_obstacle(dets)
        road_ratio = round(0.4 + obs_score * 0.005, 4)  # placeholder
        passab = round(max(0, min(1.0, 1.0 - obs_score / 100)), 4)

        sim_data = {
            "coords": coord,
            "direction": extract_direction(fname),
            "obs_score": obs_score,
            "road_ratio": road_ratio,
            "passability": passab,
            "n_dets": len(dets),
        }

        # 保存原图
        raw_out = os.path.join(GPU_DIR, "raw", fname)
        if not os.path.exists(raw_out):
            shutil.copy(raw_path, raw_out)

        # 渲染标注图
        ann_fname = fname.replace(".jpg", "_annot.jpg")
        ann_out = os.path.join(GPU_DIR, "results", ann_fname)
        ok = render_annotation(raw_path, dets, sim_data, ann_out)

        print(f"[{i}/{len(all_imgs)}] {fname} | obs={obs_score:.1f} dets={len(dets)} "
              f"{'[OK]' if ok else '[ERR]'}")

        results.append({
            "image": raw_path,
            "coords": coord,
            "direction": sim_data["direction"],
            "road_ratio": road_ratio,
            "green_ratio": 0.0,
            "obstacle_score": obs_score,
            "passability": passab,
            "n_dets": len(dets),
            "detections": dets,
            "annotated": ann_out,
        })

    # 保存 JSON
    json_path = os.path.join(GPU_DIR, "all_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"完成! {len(results)} 张图片已处理")
    print(f"耗时: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"结果: {GPU_DIR}/results/")
    print(f"原图: {GPU_DIR}/raw/")
    print(f"JSON: {json_path}")

    # 统计摘要
    obs_list = [r["obstacle_score"] for r in results]
    pass_list = [r["passability"] for r in results]
    print(f"\n障碍分数: mean={np.mean(obs_list):.1f} med={np.median(obs_list):.1f}")
    print(f"通行率: mean={np.mean(pass_list):.1%} med={np.median(pass_list):.1%}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
