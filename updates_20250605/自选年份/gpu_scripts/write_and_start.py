#!/usr/bin/env python3
"""直接写脚本到远程 + 启动"""
import paramiko, time

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
c.get_transport().set_keepalive(30)

def r(c, cmd, timeout=30):
    try:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        return stdout.read().decode("utf-8", errors="replace").strip()
    except Exception as e:
        return "ERR:" + str(e)[:100]

# 杀掉所有旧进程
r(c, "kill -9 $(ps aux | grep 'final_obstacle\|diag\|yolo_obstacle' | grep -v grep | awk '{print $2}') 2>/dev/null; echo killed")

# 直接写脚本内容到远程（避免上传编码问题）
script_body = [
    "#!/usr/bin/env python3",
    '"""障碍物检测 最终版 yolo11x COCO基线"""',
    "import os, sys, json, time, warnings",
    "os.environ['YOLO_VERBOSE'] = 'False'",
    "warnings.filterwarnings('ignore')",
    "import numpy as np",
    "import cv2",
    "import torch",
    "from ultralytics import YOLO",
    "REMOTE_DIR = '/root/autodl-tmp/streetview_analysis'",
    "IMG_DIR = REMOTE_DIR + '/images'",
    "OUT_DIR = REMOTE_DIR + '/yolo_obstacle_results'",
    "MODEL_PATH = REMOTE_DIR + '/yolo_models/yolo11x.pt'",
    "DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'",
    "CONF = 0.35",
    "IOU = 0.45",
    "COCO_MAP = {",
    " 0: ('person','行人/使用者',1.5),",
    " 1: ('bicycle','自行车占道',1.5),",
    " 2: ('car','汽车占道',2.0),",
    " 3: ('motorcycle','摩托车/电动车',1.5),",
    " 5: ('bus','公交车占道',2.0),",
    " 7: ('truck','货车占道',2.0),",
    " 11:('stop sign','停车标志',0.3),",
    " 13:('bench','长椅占道',1.5),",
    " 14:('backpack','背包',0.3),",
    " 24:('backpack','背包',0.3),",
    "}",
    "AREA_W = {'bottom':0.50,'middle':0.35,'top':0.15}",
    "def classify_view(p):",
    "    p = p.lower()",
    "    kw_ground = ['step','stairs','stair','ramp','盲道','台阶','楼梯']",
    "    if any(k in p for k in kw_ground): return 'ground_view'",
    "    fname = os.path.basename(p)",
    "    if '_U_' in fname: return 'ground_view'",
    "    return 'street_view'",
    "def get_zone(y1n):",
    "    if y1n > 0.65: return 'bottom'",
    "    if y1n > 0.35: return 'middle'",
    "    return 'top'",
    "def main():",
    "    t0 = time.time()",
    "    os.makedirs(OUT_DIR+'/viz', exist_ok=True)",
    "    print('Loading yolo11x on '+DEVICE+'...')",
    "    m = YOLO(MODEL_PATH)",
    "    m.to(DEVICE)",
    "    print('Model ready.')",
    "    skip = {'building','scatter','histogram','radar','urban_form','obstacle','heatmap','category_bar','score_dist','fcn'}",
    "    imgs = []",
    "    for r,ds,fs in os.walk(IMG_DIR):",
    "        for f in fs:",
    "            if f.endswith('.jpg') or f.endswith('.JPG'):",
    "                if not any(s in f for s in skip):",
    "                    imgs.append(os.path.join(r,f))",
    "    imgs = sorted(imgs)",
    "    print('Found '+str(len(imgs))+' images')",
    "    all_results = []",
    "    for i, img_path in enumerate(imgs):",
    "        fname = os.path.basename(img_path).rsplit('.',1)[0]",
    "        vp = OUT_DIR+'/viz/'+fname+'_det.jpg'",
    "        try:",
    "            img = cv2.imread(img_path)",
    "            if img is None: continue",
    "            h,w = img.shape[:2]",
    "            vt = classify_view(img_path)",
    "            rs = m.predict(img_path, conf=CONF, iou=IOU, verbose=False, device=DEVICE)",
    "            dets = []",
    "            if rs and rs[0].boxes is not None:",
    "                boxes = rs[0].boxes",
    "                for j in range(len(boxes)):",
    "                    cid = int(boxes.cls[j].item())",
    "                    if cid not in COCO_MAP: continue",
    "                    conf = float(boxes.conf[j].item())",
    "                    x1,y1,x2,y2 = boxes.xyxy[j].cpu().numpy()",
    "                    x1n,y1n,x2n,y2n = x1/w, y1/h, x2/w, y2/h",
    "                    cn,cn_label,wt = COCO_MAP[cid]",
    "                    zone = get_zone(y1n)",
    "                    comp = round(conf * wt * AREA_W[zone],4)",
    "                    bw,bh = x2-x1, y2-y1",
    "                    if bw<8 or bh<8 or bw>w*0.95 or bh>h*0.95: continue",
    "                    dets.append({'coco':cid,'coco_name':cn,'cn':cn_label,",
    "                                 'conf':round(conf,3),",
    "                                 'bbox':[float(x1),float(y1),float(x2),float(y2)],",
    "                                 'bbox_norm':[round(x1n,4),round(y1n,4),round(x2n,4),round(y2n,4)],",
    "                                 'zone':zone,'wt':wt,'comp':comp})",
    "            cats = {}",
    "            for d in dets:",
    "                cats[d['cn']] = cats.get(d['cn'],0)+1",
    "            score = min(100.0, sum(d['comp'] for d in dets)*10)",
    "            result = {'image':img_path,'view_type':vt,'dets':dets,",
    "                      'n_obs':len(dets),'score':round(score,2),'cats':cats}",
    "            all_results.append(result)",
    "            img2 = img.copy()",
    "            clrs = {'行人/使用者':(80,160,255),'汽车占道':(80,80,255),",
    "                    '自行车占道':(100,200,255),'公交车占道':(60,80,200),",
    "                    '货车占道':(60,80,200),'长椅占道':(200,100,150),",
    "                    '停车标志':(0,200,200),'摩托车/电动车':(120,180,255)}",
    "            for d in dets:",
    "                x1,y1,x2,y2 = [int(v) for v in d['bbox']]",
    "                color = clrs.get(d['cn'],(200,200,200))",
    "                cv2.rectangle(img2,(x1,y1),(x2,y2),color,2)",
    "                label = d['cn']+' %.2f'%d['conf']",
    "                (tw,th),_ = cv2.getTextSize(label,cv2.FONT_HERSHEY_SIMPLEX,0.45,1)",
    "                cv2.rectangle(img2,(x1,y1-th-3),(x1+tw+4,y1),color,-1)",
    "                cv2.putText(img2,label,(x1+2,y1-2),",
    "                            cv2.FONT_HERSHEY_SIMPLEX,0.45,(255,255,255),1)",
    "            vt_c = (100,255,100) if vt=='street_view' else (255,200,80)",
    "            cv2.putText(img2,vt,(8,22),cv2.FONT_HERSHEY_SIMPLEX,0.6,vt_c,2)",
    "            sc_c = (0,255,0) if score<30 else (0,255,255) if score<60 else (0,80,255)",
    "            cv2.putText(img2,'Score:%.1f Obs:%d'%(score,len(dets)),",
    "                        (8,h-10),cv2.FONT_HERSHEY_SIMPLEX,0.55,sc_c,2)",
    "            cv2.imwrite(vp, img2, [cv2.IMWRITE_JPEG_QUALITY,85])",
    "        except Exception as e:",
    "            print('ERR '+fname+': '+str(e))",
    "        if (i+1)%20==0 or i==len(imgs)-1:",
    "            el = time.time()-t0",
    "            rate = (i+1)/el if el>0 else 0",
    "            eta = (len(imgs)-i-1)/rate if rate>0 else 0",
    "            print('Progress: %d/%d Elapsed:%.0fs ETA:%.0fs'%(i+1,len(imgs),el,eta))",
    "    # 街道统计",
    "    streets = {}",
    "    for r in all_results:",
    "        parts = r['image'].split(os.sep)",
    "        st = parts[-4] if len(parts)>=4 else 'unknown'",
    "        if st not in streets:",
    "            streets[st]={'count':0,'scores':[],'n_obs':0,'vt':{'street_view':0,'ground_view':0},'cats':{}}",
    "        streets[st]['count']+=1",
    "        streets[st]['scores'].append(r['score'])",
    "        streets[st]['n_obs']+=r['n_obs']",
    "        streets[st]['vt'][r['view_type']]+=1",
    "        for k,v in r['cats'].items():",
    "            streets[st]['cats'][k]=streets[st]['cats'].get(k,0)+v",
    "    for st,data in streets.items():",
    "        sc=data['scores']",
    "        data['mean_score']=round(sum(sc)/len(sc),2) if sc else 0",
    "        data['max_score']=round(max(sc),2) if sc else 0",
    "        del data['scores']",
    "    # 全局类别统计",
    "    gcats = {}",
    "    for r in all_results:",
    "        for k,v in r['cats'].items():",
    "            gcats[k]=gcats.get(k,0)+v",
    "    # 保存",
    "    with open(OUT_DIR+'/all_results.json','w',encoding='utf-8') as f:",
    "        json.dump(all_results,f,ensure_ascii=False,indent=2)",
    "    with open(OUT_DIR+'/street_stats.json','w',encoding='utf-8') as f:",
    "        json.dump(streets,f,ensure_ascii=False,indent=2)",
    "    with open(OUT_DIR+'/global_cats.json','w',encoding='utf-8') as f:",
    "        json.dump(gcats,f,ensure_ascii=False,indent=2)",
    "    # 打印摘要",
    "    sv = sum(1 for r in all_results if r['view_type']=='street_view')",
    "    gv = len(all_results)-sv",
    "    tt = time.time()-t0",
    "    print()",
    "    print('='*60)",
    "    print('SUMMARY: %d images (%d street, %d ground) in %.0fs'%(len(all_results),sv,gv,tt))",
    "    print('Global cats:', json.dumps(gcats, ensure_ascii=False))",
    "    print('Streets:', json.dumps({k:{'score':v['mean_score'],'obs':v['n_obs']} for k,v in streets.items()}, ensure_ascii=False))",
    "    print('Output:', OUT_DIR)",
    "if __name__=='__main__': main()",
]

sftp = c.open_sftp()
sftp.file(f"{REMOTE_DIR}/detect_final.py", "wb").write("\n".join(script_body).encode("utf-8"))
sftp.close()
print("Script written to remote.")

# 启动
print("Starting detection...")
r(c, f"cd {REMOTE_DIR} && python3 -u detect_final.py >> yolo_obstacle_run.log 2>&1 & echo PID=$!")
print("Started. Waiting 90s...")
time.sleep(90)

# 检查
print("\n=== log ===")
print(r(c, "tail -30 /root/autodl-tmp/streetview_analysis/yolo_obstacle_run.log"))

print("\n=== GPU ===")
print(r(c, "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader"))

print("\n=== process ===")
print(r(c, "ps aux | grep detect_final | grep -v grep"))

print("\n=== processed ===")
print(r(c, "find /root/autodl-tmp/streetview_analysis/yolo_obstacle_results/viz -name '*.jpg' | wc -l"))

c.close()
print("done")
