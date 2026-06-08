#!/usr/bin/env python3
"""
全量下载 + YOLO 推理 + PIL 中文渲染
从 GPU 下载 294 张原图，在本地完成全部处理
"""
import os, sys, time, glob, json, re, shutil
import numpy as np
import cv2
import paramiko
from PIL import Image, ImageDraw, ImageFont

# ===== 配置 =====
HOST = "connect.bjb1.seetacloud.com"
PORT = 18073
USER = "root"
PASS = "roBbKv+ed3Vm"
GPU_IMG_ROOT = "/root/autodl-tmp/streetview_images"

LOCAL_RAW = r"e:\xicha gis 智能定位\自选年份\raw_streetview"
LOCAL_RESULTS = r"e:\xicha gis 智能定位\自选年份\annotated_streetview"
FONT_PATH = r"e:\xicha gis 智能定位\NotoSansCJK.otf"
YOLO_MODEL = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\yolo11x.pt"  # 需要先下载模型

os.makedirs(LOCAL_RAW, exist_ok=True)
os.makedirs(LOCAL_RESULTS, exist_ok=True)

# ===== SSH =====
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=60)
sftp = ssh.open_sftp()

# ===== 中文字典 =====
COCO_CN = {
    "car": "汽车", "truck": "卡车", "bus": "公交车",
    "motorcycle": "摩托车", "bicycle": "自行车", "person": "行人",
    "traffic light": "红绿灯", "stop sign": "停车标志",
    "fire hydrant": "消防栓", "bench": "长椅", "potted plant": "盆栽",
    "backpack": "背包", "umbrella": "雨伞",
}
DIR_CN = {"N": "北", "E": "东", "S": "南", "W": "西"}

# ===== 字体缓存 =====
FCACHE = {}
def get_font(size):
    if size not in FCACHE:
        try:
            FCACHE[size] = ImageFont.truetype(FONT_PATH, size)
        except:
            FCACHE[size] = ImageFont.load_default()
    return FCACHE[size]

# ===== 提取坐标和方向 =====
def parse_fname(fname):
    coord = re.sub(r"_[NESW]_\d{4}\.jpg$", "", fname.replace("_2022", ""))
    m = re.search(r"_([NESW])_\d{4}\.jpg$", fname)
    direction = m.group(1) if m else "?"
    return coord, direction

# ===== 障碍分数 =====
def calc_scores(dets):
    if not dets:
        return 0.0, 0.0, 0.0
    weights = {"car": 1.0, "truck": 1.2, "bus": 1.2, "motorcycle": 0.6,
               "bicycle": 0.4, "person": 0.3, "bench": 0.5, "fence": 0.4,
               "fire hydrant": 0.3, "traffic light": 0.2}
    total = sum(weights.get(d.get("coco_name","?"), 0.5)*d["conf"] for d in dets)
    obs = round(min(100.0, total * 30), 2)
    road_ratio = round(min(1.0, 0.8 - obs/200), 4)
    passab = round(max(0, 1.0 - obs/100), 4)
    return obs, road_ratio, passab

# ===== 渲染中文标注图 =====
def render(img_path, dets, coord, direction, obs, road_ratio, passab, out_path):
    img = cv2.imread(img_path)
    if img is None:
        print(f"  [ERR] 读取失败: {img_path}")
        return False
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    H, W = img_rgb.shape[:2]

    pil = Image.fromarray(img_rgb).convert("RGBA")
    draw = ImageDraw.Draw(pil)

    # YOLO BBox
    for d in dets:
        x1, y1, x2, y2 = [int(v) for v in d["bbox"]]
        cn = d["coco_name"]
        color = (255, 80, 80) if cn == "person" else (255, 180, 0)
        draw.rectangle([x1, y1, x2, y2], outline=(*color, 220), width=2)
        label = f"{COCO_CN.get(cn, cn)} {d['conf']:.0%}"
        fnt = get_font(10)
        lw, lh = draw.textsize(label, font=fnt)
        draw.rectangle([x1, y1 - lh - 4, x1 + lw + 4, y1], fill=(*color, 200))
        draw.text((x1 + 2, y1 - lh - 3), label, font=fnt, fill=(255, 255, 255))

    # 右侧面板
    if obs >= 80:
        bc = (200, 30, 30)
    elif obs >= 50:
        bc = (220, 140, 0)
    elif obs >= 20:
        bc = (200, 180, 0)
    else:
        bc = (0, 160, 60)

    pw = min(280, W - 20)
    ph = min(350, H - 16)
    px, py = W - pw - 8, 8
    panel = Image.new("RGBA", (pw, ph), (245, 248, 255, 230))
    pd = ImageDraw.Draw(panel)
    pd.rectangle([0, 0, pw - 1, ph - 1], outline=(*bc, 255), width=3)

    y = 12
    def put(txt, fs, fc):
        nonlocal y
        pd.text((10, y), txt, font=get_font(fs), fill=fc)
        y += fs + 7
    def sep():
        nonlocal y
        pd.text((10, y), "-" * 22, font=get_font(8), fill=(160, 160, 160))
        y += 13

    put(f"{coord} [{DIR_CN.get(direction, direction)}]", 11, (60, 60, 60))
    sep()
    put(f"障碍分数: {obs:.1f}", 15, bc)
    put(f"道路比例: {road_ratio:.1%}", 11, (60, 60, 60))
    put(f"通行率: {passab:.1%}", 13, bc)
    sep()
    put(f"YOLOv11x 检测: {len(dets)} 个目标", 11, (20, 80, 180))
    sep()
    cat_count = {}
    for d in dets:
        cn = d.get("coco_name", "?")
        cat_count[cn] = cat_count.get(cn, 0) + 1
    for cn, cnt in sorted(cat_count.items(), key=lambda x: -x[1])[:6]:
        put(f"  {COCO_CN.get(cn, cn)} x{cnt}", 10, (80, 60, 20))
    y += 5
    put("图例:", 11, (80, 80, 80))
    put("  道路=灰  人行道=紫", 9, (128, 128, 128))
    put("  建筑=棕  植被=绿", 9, (34, 139, 34))
    put("  汽车=蓝  行人=红", 9, (0, 100, 200))

    pil.paste(panel, (px, py), mask=panel)

    # 底部状态栏
    bar_h = 22
    bar_np = np.full((bar_h, W, 3), [int(bc[0]*0.5), int(bc[1]*0.5), int(bc[2]*0.5)], dtype=np.uint8)
    fill_w = int(W * passab)
    bar_np[:, :fill_w] = bc
    pil_bar = Image.fromarray(bar_np).convert("RGBA")
    pil.paste(pil_bar, (0, H - bar_h), mask=pil_bar)
    bd = ImageDraw.Draw(pil)
    status = f"YOLOv11x 障碍分数={obs:.1f} 通行率={passab:.1%}"
    bd.text((8, H - bar_h + 5), status, font=get_font(11), fill=(255, 255, 255))

    pil.convert("RGB").save(out_path, quality=92)
    return True

# ===== 主流程 =====
def main():
    t0 = time.time()
    print(f"{'='*60}")
    print("全量下载 + 本地 YOLO 推理 + PIL 中文渲染")
    print(f"{'='*60}")

    # 1. 获取 GPU 上的图片列表
    print("\n[1/4] 扫描 GPU 图片...")
    _, stdout, _ = ssh.exec_command(
        f'find {GPU_IMG_ROOT} -name "*.jpg" | sort', timeout=60)
    gpu_files = [f.strip() for f in stdout.read().decode().strip().split("\n") if f.strip()]
    print(f"  GPU 上共 {len(gpu_files)} 张图片")

    if not gpu_files:
        print("ERROR: GPU 上无图片!")
        return

    # 2. 下载全部图片
    print(f"\n[2/4] 下载 {len(gpu_files)} 张图片...")
    downloaded = 0
    skipped = 0
    dl_start = time.time()

    for i, gpu_path in enumerate(gpu_files, 1):
        fname = os.path.basename(gpu_path)
        rel_dir = os.path.relpath(os.path.dirname(gpu_path), GPU_IMG_ROOT)
        local_dir = os.path.join(LOCAL_RAW, rel_dir)
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, fname)

        if os.path.exists(local_path) and os.path.getsize(local_path) > 50000:
            skipped += 1
            continue

        try:
            sftp.get(gpu_path, local_path)
            downloaded += 1
        except Exception as e:
            print(f"  [ERR] {fname}: {e}")

        if downloaded % 20 == 0:
            elapsed = time.time() - dl_start
            print(f"  已下载 {downloaded}/{len(gpu_files)} (跳过{skipped})... "
                  f"耗时 {elapsed:.0f}s  速度 {downloaded/elapsed:.1f} 张/秒")

    print(f"\n  下载完成: {downloaded} 新增, {skipped} 跳过")
    print(f"  下载耗时: {time.time() - dl_start:.0f}s")

    sftp.close()
    ssh.close()

    # 3. 本地 YOLO 推理
    print(f"\n[3/4] 本地 YOLO 推理...")
    from ultralytics import YOLO

    if not os.path.exists(YOLO_MODEL):
        print(f"  [WARN] YOLO 模型不存在: {YOLO_MODEL}")
        print(f"  跳过 YOLO 推理，仅处理已下载图片")
        yolo_model = None
    else:
        yolo_model = YOLO(YOLO_MODEL)
        print(f"  YOLO 加载完成")

    local_imgs = glob.glob(os.path.join(LOCAL_RAW, "**", "*.jpg"), recursive=True)
    print(f"  本地 {len(local_imgs)} 张图片待处理")

    results = []
    det_start = time.time()

    for i, img_path in enumerate(sorted(local_imgs), 1):
        fname = os.path.basename(img_path)
        coord, direction = parse_fname(fname)

        if yolo_model:
            yolo_results = yolo_model(img_path, verbose=False, conf=0.25, iou=0.4)
            dets = []
            for r in yolo_results:
                if r.boxes is None:
                    continue
                for box in r.boxes:
                    xyxy = box.xyxy[0].cpu().numpy()
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    coco_name = yolo_model.names[cls_id]
                    dets.append({
                        "coco_name": coco_name, "conf": round(conf, 4),
                        "bbox": xyxy.tolist(),
                    })
        else:
            dets = []

        obs, road_ratio, passab = calc_scores(dets)
        sim_data = {
            "coords": coord, "direction": direction,
            "obs_score": obs, "road_ratio": road_ratio,
            "passability": passab, "n_dets": len(dets),
            "detections": dets,
        }

        # 保存标注图
        out_fname = fname.replace(".jpg", "_annot.jpg")
        out_path = os.path.join(LOCAL_RESULTS, out_fname)
        render(img_path, dets, coord, direction, obs, road_ratio, passab, out_path)

        results.append({
            "image": img_path, "annotated": out_path,
            **sim_data,
        })

        if i % 30 == 0:
            elapsed = time.time() - det_start
            print(f"  处理中: {i}/{len(local_imgs)}... "
                  f"耗时 {elapsed:.0f}s  速度 {i/elapsed:.1f} 张/秒")

    # 保存 JSON
    json_path = r"e:\xicha gis 智能定位\自选年份\all_sim_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 统计
    obs_list = [r["obs_score"] for r in results]
    pas_list = [r["passability"] for r in results]
    det_counts = [r["n_dets"] for r in results]

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"全量处理完成!")
    print(f"  图片: {len(results)} 张")
    print(f"  总耗时: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"  原图: {LOCAL_RAW}/")
    print(f"  标注图: {LOCAL_RESULTS}/")
    print(f"  JSON: {json_path}")
    print(f"\n障碍分数: mean={np.mean(obs_list):.1f} med={np.median(obs_list):.1f}")
    print(f"通行率: mean={np.mean(pas_list):.1%} med={np.median(pas_list):.1%}")
    print(f"检测数: mean={np.mean(det_counts):.1f} med={np.median(det_counts):.1f}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
