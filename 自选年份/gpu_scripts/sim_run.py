#!/usr/bin/env python3
"""
南山区街景综合分析 - 同时运行YOLO目标检测 + DeepLabV3语义分割
生成带仿真参数的标注图（障碍物/绿化/行人/车辆）
"""
import os, sys, time, json, math
import numpy as np
import cv2

import torch
print(f"PyTorch: {torch.__version__}, CUDA: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")

# ===================== 依赖安装 =====================
def install_deps():
    import subprocess, sys
    pkgs = ["ultralytics", "Pillow"]
    for pkg in pkgs:
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", pkg], capture_output=True)
        print(f"Install {pkg}: {'OK' if r.returncode == 0 else r.stderr.decode()[-100:]}")
install_deps()

# ===================== 模型加载 =====================
from ultralytics import YOLO
print("Loading YOLO11x...")
yolo = YOLO("yolo11x.pt")
print("YOLO loaded OK")

from torchvision.models.segmentation import deeplabv3_mobilenet_v3_large, DeepLabV3_MobileNet_V3_Large_Weights
print("Loading DeepLabV3...")
fcn_model = deeplabv3_mobilenet_v3_large(weights=DeepLabV3_MobileNet_V3_Large_Weights.DEFAULT)
fcn_model.eval()
if torch.cuda.is_available():
    fcn_model = fcn_model.cuda()
    print("FCN -> GPU OK")

# ===================== Cityscapes类别映射 =====================
CITYSCAPES = {
    0:("背景",(0,0,0)),
    7:("道路",(128,64,128)),
    8:("人行道",(244,35,232)),
    11:("建筑",(70,70,70)),
    12:("墙体",(102,102,156)),
    13:("围栏",(190,153,153)),
    17:("立柱",(153,153,153)),
    19:("交通灯",(250,170,30)),
    20:("交通标志",(220,220,0)),
    21:("绿化",(107,142,35)),
    22:("地形",(122,160,102)),
    23:("行人",(220,20,60)),
    24:("骑行者",(255,0,0)),
    25:("汽车",(0,0,142)),
    26:("货车",(0,0,70)),
    27:("公交车",(0,60,100)),
    31:("摩托车",(119,11,32)),
    32:("自行车",(0,0,230)),
}

# 仿真参数权重
SIM_W = {
    "car":1.2,"truck":1.0,"bus":0.8,
    "motorcycle":0.9,"bicycle":0.5,"person":0.3,
}
ZONE_W = {"bottom":0.5,"middle":0.35,"top":0.15}

# ===================== 仿真参数计算 =====================
def road_ratio(mask, h, w):
    road = (mask==7).astype(float)
    if road.sum()==0: return w*0.4/float(w)
    bottom = road[int(h*0.75):,:]
    lc = np.argmax(bottom.any(axis=0))
    rc = w-1-np.argmax(bottom[::-1,:].any(axis=0))
    return max(rc-lc,1)/float(w)

def green_ratio(mask):
    return float(np.sum((mask==21)|(mask==22))) / float(mask.size)

def obstacle_score(dets, h):
    total = 0.0
    for d in dets:
        wt = SIM_W.get(d["coco_name"], 0.5)
        y2 = d["bbox"][3]
        zone = "bottom" if y2>h*0.75 else ("middle" if y2>h*0.4 else "top")
        zw = ZONE_W.get(zone, 0.2)
        total += d["conf"] * wt * zw
    return min(total*100, 100)

def passability(r_ratio, obs_score, g_ratio):
    base = min(r_ratio*2, 1.0)
    return base*(1-obs_score/100.0)*(1+g_ratio*0.1)

# ===================== 图像标注函数 =====================
def annotate(img_rgb, mask, dets, r_ratio, g_ratio, obs, passab, img_path):
    h, w = img_rgb.shape[:2]
    vis = img_rgb.copy()

    # 1. 分割叠加层
    overlay = np.zeros_like(img_rgb, dtype=np.uint8)
    for cid,(name,color) in CITYSCAPES.items():
        m = (mask==cid)
        if m.sum()>0:
            overlay[m] = color
    vis = cv2.addWeighted(vis, 0.55, overlay.astype(np.uint8), 0.45, 0)

    # 2. YOLO检测框
    COCO_CN = {
        "person":"行人","car":"汽车","motorcycle":"摩托车",
        "bicycle":"自行车","truck":"货车","bus":"公交车",
        "bench":"长椅","stop sign":"停车标志","fire hydrant":"消防栓",
        "traffic light":"交通灯","kite":"风筝","sports ball":"球",
    }
    BOX_COLORS = {
        "person":(60,220,60),"car":(60,60,220),"motorcycle":(20,150,250),
        "bicycle":(20,200,50),"truck":(60,20,20),"bus":(100,30,30),
    }
    for det in dets:
        if det["conf"]<0.35: continue
        x1,y1,x2,y2 = [int(v) for v in det["bbox"]]
        name = det["coco_name"]
        color = BOX_COLORS.get(name,(100,100,100))
        cv2.rectangle(vis,(x1,y1),(x2,y2),color,2)
        label = COCO_CN.get(name,name)+f" {det['conf']:.0%}"
        (tw,th),_ = cv2.getTextSize(label,cv2.FONT_HERSHEY_SIMPLEX,0.6,2)
        cv2.rectangle(vis,(x1,y1-th-10),(x1+tw+8,y1),color,-1)
        cv2.putText(vis,label,(x1+4,y1-5),cv2.FONT_HERSHEY_SIMPLEX,0.6,(255,255,255),2)

    # 3. 仿真参数面板（右侧）
    px = w-310
    ph = 300
    panel = np.full((ph,300,3),255,np.uint8)
    if obs>=60: pc=(0,0,220)
    elif obs>=40: pc=(0,120,220)
    elif obs>=20: pc=(0,180,220)
    else: pc=(0,200,80)
    cv2.rectangle(panel,(2,2),(297,ph-2),pc,3)
    y=28
    def put(txt,fs=0.7,c=(30,30,30),bold=2):
        nonlocal y
        cv2.putText(panel,txt,(10,y),cv2.FONT_HERSHEY_SIMPLEX,fs,c,bold)
        y+=int(28*fs)+6
    put("=== 仿真参数 ===",0.85,(20,80,180),2)
    put(f"道路占有率: {r_ratio:.1%}")
    put(f"绿化覆盖率: {g_ratio:.1%}")
    put(f"障碍评分:   {obs:.1f}")
    put(f"通行率:     {passab:.1%}")
    y+=5
    put("--- 障碍物统计 ---",0.7,(180,60,20),2)
    cc={}
    for d in dets:
        n=d["coco_name"]
        cc[n]=cc.get(n,0)+1
    for n,cnt in sorted(cc.items(),key=lambda x:-x[1]):
        put(f"  {COCO_CN.get(n,n)}({cnt})",0.65,(60,60,60),1)
    vis[0:ph, px:w] = panel

    # 4. 图例（左下角）
    legend=[
        ("汽车",(60,60,220)),("行人",(60,220,60)),
        ("摩托车",(20,150,250)),("货车",(60,20,20)),
        ("道路",(128,64,128)),("绿化",(107,142,35)),
        ("人行道",(244,35,232)),
    ]
    lh_val = len(legend)*24+12
    lw_val = 155
    lbg=np.full((lh_val,lw_val,3),220,np.uint8)
    for i,(lbl,col) in enumerate(legend):
        cv2.rectangle(lbg,(5,i*24+4),(22,i*24+18),col,-1)
        cv2.putText(lbg,lbl,(28,i*24+16),cv2.FONT_HERSHEY_SIMPLEX,0.5,(20,20,20),1)
    lx=5; ly=h-lh_val-5
    if ly>=0: vis[ly:ly+lh_val, lx:lx+lw_val] = lbg

    return cv2.cvtColor(vis, cv2.COLOR_RGB2BGR)

# ===================== 主处理 =====================
IMG_ROOT = "/root/autodl-tmp/streetview_images"
OUT_ROOT = "/root/autodl-tmp/streetview_sim"
os.makedirs(OUT_ROOT, exist_ok=True)
SAMPLES = os.path.join(OUT_ROOT, "samples")
os.makedirs(SAMPLES, exist_ok=True)

# 南山区所有图片
nanshan_dir = os.path.join(IMG_ROOT, "南山区")
imgs = []
for root,dirs,files in os.walk(nanshan_dir):
    for fn in files:
        if fn.endswith(".jpg") and not fn.startswith("."):
            imgs.append(os.path.join(root,fn))

print(f"Nanshan images: {len(imgs)}")
if not imgs: sys.exit(1)

# 处理前50张
imgs = imgs[:50]
results = []

for i, img_path in enumerate(imgs, 1):
    rel = os.path.relpath(img_path, IMG_ROOT).replace(os.sep,"_")
    coords = os.path.basename(os.path.dirname(img_path))
    print(f"[{i}/{len(imgs)}] {coords[:20]}...", end=" ", flush=True)
    t0 = time.time()

    img_bgr = cv2.imread(img_path)
    if img_bgr is None:
        print("READ FAIL"); continue
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    ih, iw = img_rgb.shape[:2]

    # YOLO
    dets = []
    for box in yolo.predict(img_path, conf=0.35, verbose=False)[0].boxes:
        cid = int(box.cls.item())
        name = yolo.names[cid]
        conf = float(box.conf.item())
        x1,y1,x2,y2 = [float(v) for v in box.xyxy[0].tolist()]
        dets.append({"coco_name":name,"conf":conf,"bbox":[x1,y1,x2,y2]})

    # FCN
    inp = torch.from_numpy(img_rgb.transpose(2,0,1)).float()/255.0
    inp = inp.unsqueeze(0)
    if torch.cuda.is_available(): inp = inp.cuda()
    with torch.no_grad():
        seg = fcn_model(inp)["out"][0].argmax(dim=0).cpu().numpy().astype(np.uint8)

    # 仿真参数
    rr = road_ratio(seg, ih, iw)
    gr = green_ratio(seg)
    obs = obstacle_score(dets, ih)
    pas = passability(rr, obs, gr)

    # 标注图
    ann = annotate(img_rgb, seg, dets, rr, gr, obs, pas, img_path)
    out_fn = rel+".jpg"
    cv2.imwrite(os.path.join(SAMPLES, out_fn), ann, [cv2.IMWRITE_JPEG_QUALITY, 92])

    results.append({
        "image": img_path, "coords": coords,
        "road_ratio": round(rr,4), "green_ratio": round(gr,4),
        "obstacle_score": round(float(obs),2), "passability": round(float(pas),4),
        "n_dets": len(dets), "detections": dets,
        "annotated": os.path.join(SAMPLES, out_fn),
    })
    print(f"障碍{obs:.1f} 通行{pas:.1%} ({time.time()-t0:.1f}s)")

print(f"\nDone! {len(results)} images processed")
print(f"Samples: {SAMPLES}")

# 保存JSON
json_out = os.path.join(OUT_ROOT, "sim_results.json")
with open(json_out, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# 汇总
scores = [r["obstacle_score"] for r in results]
roads = [r["road_ratio"] for r in results]
greens = [r["green_ratio"] for r in results]
passes = [r["passability"] for r in results]
print(f"\n===== Sim Summary =====")
print(f"Images: {len(results)}")
print(f"Obstacle Score: mean={np.mean(scores):.1f} med={np.median(scores):.1f} range=[{np.min(scores):.1f},{np.max(scores):.1f}]")
print(f"Road Ratio: {np.mean(roads):.1%}")
print(f"Green Ratio: {np.mean(greens):.1%}")
print(f"Passability: {np.mean(passes):.1%}")

# 街道级
by_street = {}
for r in results:
    parts = r["image"].split("/")
    if "南山区" in parts:
        idx = parts.index("南山区")
        if idx+1<len(parts): st=parts[idx+1]; by_street.setdefault(st,[]).append(r)
print(f"\n===== By Street =====")
for st,recs in sorted(by_street.items(), key=lambda x:-np.mean([r['obstacle_score'] for r in x[1]])):
    s=[r['obstacle_score'] for r in recs]
    p=[r['passability'] for r in recs]
    print(f"  {st}: n={len(recs)} obs={np.mean(s):.1f} pass={np.mean(p):.1%}")
