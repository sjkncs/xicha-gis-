#!/usr/bin/env python3
"""
本地全量 YOLO + PIL 中文渲染 (已下载图，修复 textsize 问题)
"""
import os, time, glob, json, re
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO

LOCAL_RAW = r"e:\xicha gis 智能定位\自选年份\raw_streetview"
LOCAL_RESULTS = r"e:\xicha gis 智能定位\自选年份\annotated_streetview"
FONT_PATH = r"e:\xicha gis 智能定位\自选年份\NotoSansCJK.otf"
YOLO_LOCAL = r"e:\xicha gis 智能定位\自选年份\yolo11x_local.pt"

os.makedirs(LOCAL_RESULTS, exist_ok=True)

COCO_CN = {
    "car":"汽车","truck":"卡车","bus":"公交车","motorcycle":"摩托车",
    "bicycle":"自行车","person":"行人","traffic light":"红绿灯",
    "stop sign":"停车标志","fire hydrant":"消防栓","bench":"长椅",
    "potted plant":"盆栽","backpack":"背包","umbrella":"雨伞",
}
DIR_CN = {"N":"北","E":"东","S":"南","W":"西"}

FCACHE = {}
def get_font(size):
    if size not in FCACHE:
        try: FCACHE[size] = ImageFont.truetype(FONT_PATH, size)
        except: FCACHE[size] = ImageFont.load_default()
    return FCACHE[size]

def text_size(draw, text, font):
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except:
        return font.getsize(text)

def parse_fname(fname):
    coord = re.sub(r"_[NESW]_\d{4}\.jpg$", "", fname.replace("_2022",""))
    m = re.search(r"_([NESW])_\d{4}\.jpg$", fname)
    return coord, m.group(1) if m else "?"

def calc_scores(dets):
    if not dets:
        return 0.0, 0.8, 1.0
    w = {"car":1.0,"truck":1.2,"bus":1.2,"motorcycle":0.6,"bicycle":0.4,
         "person":0.3,"bench":0.5,"fence":0.4,"fire hydrant":0.3,"traffic light":0.2}
    total = sum(w.get(d["coco_name"],0.5)*d["conf"] for d in dets)
    obs = round(min(100, total*30), 2)
    passab = round(max(0, 1-obs/100), 4)
    road_ratio = round(min(1, max(0, 0.8-obs/200)), 4)
    return obs, road_ratio, passab

def render(img_path, dets, coord, direction, obs, road_ratio, passab, out_path):
    img = cv2.imread(img_path)
    if img is None:
        return False
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    H, W = img_rgb.shape[:2]
    pil = Image.fromarray(img_rgb).convert("RGBA")
    draw = ImageDraw.Draw(pil)

    for d in dets:
        x1,y1,x2,y2 = [int(v) for v in d["bbox"]]
        cn = d["coco_name"]
        color = (255,80,80) if cn=="person" else (255,180,0)
        draw.rectangle([x1,y1,x2,y2], outline=(*color,220), width=2)
        label = f"{COCO_CN.get(cn,cn)} {d['conf']:.0%}"
        fnt = get_font(10)
        lw,lh = text_size(draw, label, fnt)
        draw.rectangle([x1,y1-lh-4,x1+lw+4,y1], fill=(*color,200))
        draw.text((x1+2,y1-lh-3), label, font=fnt, fill=(255,255,255))

    bc = (200,30,30) if obs>=80 else (220,140,0) if obs>=50 else (200,180,0) if obs>=20 else (0,160,60)
    pw,ph = min(280,W-20), min(350,H-16)
    px,py = W-pw-8, 8
    panel = Image.new("RGBA",(pw,ph),(245,248,255,230))
    pd = ImageDraw.Draw(panel)
    pd.rectangle([0,0,pw-1,ph-1], outline=(*bc,255), width=3)
    y=12
    def put(t,s,fc):
        nonlocal y; pd.text((10,y),t,font=get_font(s),fill=fc); y+=s+7
    def sep():
        nonlocal y; pd.text((10,y),"-"*22,font=get_font(8),fill=(160,160,160)); y+=13
    put(f"{coord} [{DIR_CN.get(direction,direction)}]",11,(60,60,60)); sep()
    put(f"障碍分数: {obs:.1f}",15,bc)
    put(f"道路比例: {road_ratio:.1%}",11,(60,60,60))
    put(f"通行率: {passab:.1%}",13,bc); sep()
    put(f"YOLOv11x 检测: {len(dets)} 个目标",11,(20,80,180)); sep()
    cc={}
    for d in dets:
        cc[d.get("coco_name","?")] = cc.get(d.get("coco_name","?"),0)+1
    for cn,cnt in sorted(cc.items(),key=lambda x:-x[1])[:6]:
        put(f"  {COCO_CN.get(cn,cn)} x{cnt}",10,(80,60,20))
    y+=5; put("图例:",11,(80,80,80))
    put("  道路=灰  人行道=紫",9,(128,128,128))
    put("  建筑=棕  植被=绿",9,(34,139,34))
    put("  汽车=蓝  行人=红",9,(0,100,200))
    pil.paste(panel,(px,py),mask=panel)
    bar_h=22
    bar_np=np.full((bar_h,W,3),[int(bc[0]*.5),int(bc[1]*.5),int(bc[2]*.5)],dtype=np.uint8)
    bar_np[:,:int(W*passab)]=bc
    bd=ImageDraw.Draw(pil)
    bd.text((8,H-bar_h+5),f"YOLOv11x 障碍分数={obs:.1f} 通行率={passab:.1%}",font=get_font(11),fill=(255,255,255))
    pil.convert("RGB").save(out_path,quality=92)
    return True

def main():
    t0=time.time()
    print(f"{'='*60}")
    print("全量推理 + PIL 中文标注渲染 (v2)")
    print(f"{'='*60}")

    # 加载 YOLO
    print("\n加载 YOLO 模型...")
    model=YOLO(YOLO_LOCAL)
    print("YOLO 加载完成")

    local_imgs=glob.glob(os.path.join(LOCAL_RAW,"**","*.jpg"),recursive=True)
    print(f"本地 {len(local_imgs)} 张图片待处理")

    results=[]
    t2=time.time()
    for i,img_path in enumerate(sorted(local_imgs),1):
        fname=os.path.basename(img_path)
        coord,direction=parse_fname(fname)
        yr=model(img_path,verbose=False,conf=0.25,iou=0.4)
        dets=[]
        for r in yr:
            if r.boxes is None: continue
            for box in r.boxes:
                xyxy=box.xyxy[0].cpu().numpy()
                conf=float(box.conf[0])
                cls_id=int(box.cls[0])
                cn=model.names[cls_id]
                dets.append({"coco_name":cn,"conf":round(conf,4),"bbox":xyxy.tolist()})
        obs,road_ratio,passab=calc_scores(dets)
        out_fname=fname.replace(".jpg","_annot.jpg")
        out_path=os.path.join(LOCAL_RESULTS,out_fname)
        render(img_path,dets,coord,direction,obs,road_ratio,passab,out_path)
        results.append({"image":img_path,"annotated":out_path,"coords":coord,"direction":direction,
                        "obs_score":obs,"road_ratio":road_ratio,"passability":passab,
                        "n_dets":len(dets),"detections":dets})
        if i%30==0:
            print(f"  {i}/{len(local_imgs)} {time.time()-t2:.0f}s")

    json_path=r"e:\xicha gis 智能定位\自选年份\all_sim_results.json"
    with open(json_path,"w",encoding="utf-8") as f:
        json.dump(results,f,ensure_ascii=False,indent=2)

    obs_l=[r["obs_score"] for r in results]
    pas_l=[r["passability"] for r in results]
    det_l=[r["n_dets"] for r in results]
    et=time.time()-t0
    print(f"\n{'='*60}")
    print(f"完成! {len(results)}张 耗时{et:.0f}s({et/60:.1f}min)")
    print(f"标注图: {LOCAL_RESULTS}")
    print(f"障碍: mean={np.mean(obs_l):.1f} med={np.median(obs_l):.1f}")
    print(f"通行率: mean={np.mean(pas_l):.1%} med={np.median(pas_l):.1%}")
    print(f"检测数: mean={np.mean(det_l):.1f}")
    print(f"{'='*60}")

if __name__=="__main__":
    main()
