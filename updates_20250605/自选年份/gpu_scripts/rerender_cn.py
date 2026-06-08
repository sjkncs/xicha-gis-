#!/usr/bin/env python3
"""
本地重标注脚本：从 GPU 下载的标注图 + sim_results_v2.json
用 PIL 中文字体（微软雅黑）重新叠加中文标注，
再用 VLM 补充识别，叠加双面板。
"""
import os, json, re, base64, time, glob
import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ===== 配置 =====
API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"
GPU_SAMPLES = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\samples_gpu"
JSON_FILE = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\sim_results_v2.json"
OUT_CN = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results\annotated_cn"
OUT_VLM = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results\vlm_full"

os.makedirs(OUT_CN, exist_ok=True)
os.makedirs(OUT_VLM, exist_ok=True)

# ===== 中文字典 =====
COCO_CN = {
    "car": "汽车", "truck": "卡车", "bus": "公交车",
    "motorcycle": "摩托车", "bicycle": "自行车", "person": "行人",
    "traffic light": "红绿灯", "stop sign": "停车标志",
    "fire hydrant": "消防栓", "bench": "长椅", "potted plant": "盆栽",
}

DIR_CN = {"N": "北", "E": "东", "S": "南", "W": "西"}
SEV_C = {"high": (220, 0, 0), "medium": (200, 120, 0), "low": (0, 160, 60)}
SEV_I = {"high": "!", "medium": "~", "low": "o"}

# ===== 字体 =====
def get_font(size):
    for fp in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttc", "C:/Windows/Fonts/simsun.ttc"]:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()

FCACHE = {s: get_font(s) for s in [9, 10, 11, 12, 13, 14, 16, 18, 20]}

# ===== VLM =====
VLM_PROMPT = (
    "You are an expert analyzing urban street view for pedestrian accessibility. "
    "Identify ALL obstacles: vehicles, street furniture, fences, walls, vegetation, pedestrians. "
    "Output ONLY valid JSON (no markdown): "
    '{"obstacles":[{"type":"car","position":"center-right","severity":"high","description":"white sedan"}],"passability_estimate":45,"top_blocking":["car"]}'
)

def call_vlm(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    models = ["meta/llama-3.2-90b-vision-instruct", "microsoft/phi-3-vision-128k-instruct"]
    for model in models:
        t0 = time.time()
        try:
            r = requests.post(
                f"{BASE_URL}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        {"type": "text", "text": VLM_PROMPT}
                    ]}],
                    "max_tokens": 512,
                    "temperature": 0.1,
                },
                timeout=120,
            )
            if r.status_code == 200:
                content = r.json()["choices"][0]["message"]["content"]
                return content, model, time.time() - t0
        except Exception as e:
            print(f"        VLM [{model}] error: {e}")
    return None, None, None

def parse_vlm(content):
    try:
        c = re.sub(r"```json\s*", "", content)
        c = re.sub(r"```\s*", "", c)
        return json.loads(c)
    except Exception:
        return {"obstacles": [], "passability_estimate": None, "top_blocking": []}

# ===== 中文标注面板叠加 =====
def overlay_chinese(gpu_annotated_path, sim_data, out_path):
    """从GPU下载的标注图读取，用PIL中文字体重新标注右侧面板。"""
    pil = Image.open(gpu_annotated_path).convert("RGB")
    a = np.array(pil)
    H, W = a.shape[:2]

    # 右侧中文面板
    pw = 300
    ph = min(340, H - 16)
    px = W - pw - 8
    py = 8
    panel = Image.new("RGBA", (pw, ph), (240, 248, 255, 235))
    pd = ImageDraw.Draw(panel)

    obs_score = sim_data.get("obstacle_score", 0)
    if obs_score >= 80:
        bc = (200, 30, 30)
    elif obs_score >= 50:
        bc = (220, 140, 0)
    elif obs_score >= 20:
        bc = (200, 180, 0)
    else:
        bc = (0, 160, 60)

    pd.rectangle([0, 0, pw - 1, ph - 1], outline=(*bc, 255), width=3)

    # 居左文字 helper
    class DrawCtx:
        def __init__(self, draw, font_cache, pw):
            self.draw = draw
            self.font_cache = font_cache
            self.pw = pw
            self.y = 8
        def put(self, txt, fs=12, fc=(30, 30, 30)):
            fnt = self.font_cache.get(fs, get_font(fs))
            self.draw.text((8, self.y), txt, font=fnt, fill=(*fc, 255))
            self.y += fs + 6
        def line(self, fs=9, fc=(180, 180, 180)):
            fnt = self.font_cache.get(fs, get_font(fs))
            self.draw.text((8, self.y), "-" * 28, font=fnt, fill=(*fc, 255))
            self.y += fs + 4

    ctx = DrawCtx(pd, FCACHE, pw)

    coord = sim_data.get("coords", "?")
    direction = sim_data.get("direction", "?")
    dir_label = DIR_CN.get(direction, direction)
    ctx.put(f"坐标: {coord} [{dir_label}向]", 11, (60, 60, 60))
    ctx.line()
    ctx.y += 3

    ctx.put(f"障碍分数: {obs_score:.1f}", 15, bc)
    ctx.put(f"道路比例: {sim_data.get('road_ratio', 0):.1%}", 11, (60, 60, 60))
    ctx.put(f"绿地比例: {sim_data.get('green_ratio', 0):.1%}", 11, (34, 139, 34))
    ctx.put(f"通行率: {sim_data.get('passability', 0):.1%}", 13, bc)
    ctx.line()
    ctx.y += 3

    dets = sim_data.get("detections", [])
    n_dets = sim_data.get("n_dets", len(dets))
    ctx.put(f"YOLOv11x检测: {n_dets} 个目标", 11, (20, 80, 180))
    ctx.line()

    cat_count = {}
    for d in dets:
        cn = d.get("coco_name", "?")
        cat_count[cn] = cat_count.get(cn, 0) + 1
    for cn, cnt in sorted(cat_count.items(), key=lambda x: -x[1])[:6]:
        cn_label = COCO_CN.get(cn, cn)
        ctx.put(f"  {cn_label} x{cnt}", 10, (80, 60, 20))

    ctx.y += 3
    ctx.put("图例:", 11, (80, 80, 80))
    ctx.put("  道路=灰  人行道=紫", 9, (128, 128, 128))
    ctx.put("  建筑=棕  植被=绿", 9, (34, 139, 34))
    ctx.put("  汽车=蓝  行人=红", 9, (0, 100, 200))

    # 合成
    pi = Image.fromarray(a).convert("RGBA")
    pi.paste(panel, (px, py), mask=panel)
    pi.convert("RGB").save(out_path, quality=92)


# ===== VLM 面板叠加 =====
def overlay_vlm_panel(cn_annotated_path, vlm_result, out_path):
    """在已有中文标注图上叠加 VLM 分析面板（左侧）。"""
    pil = Image.open(cn_annotated_path).convert("RGB")
    a = np.array(pil)
    H, W = a.shape[:2]

    pw = 280
    ph = min(340, H - 16)
    px = 8
    py = 8
    panel = Image.new("RGBA", (pw, ph), (245, 252, 245, 230))
    pd = ImageDraw.Draw(panel)

    pab = vlm_result.get("passability_estimate")
    if pab is not None and pab >= 70:
        bc = (0, 160, 60)
    elif pab is not None and pab >= 40:
        bc = (200, 140, 0)
    elif pab is not None:
        bc = (200, 0, 0)
    else:
        bc = (20, 100, 180)

    pd.rectangle([0, 0, pw - 1, ph - 1], outline=(*bc, 255), width=3)

    class DrawCtx:
        def __init__(self, draw, font_cache, pw):
            self.draw = draw
            self.font_cache = font_cache
            self.pw = pw
            self.y = 8
        def put(self, txt, fs=12, fc=(30, 30, 30)):
            fnt = self.font_cache.get(fs, get_font(fs))
            self.draw.text((8, self.y), txt, font=fnt, fill=(*fc, 255))
            self.y += fs + 6
        def line(self, fs=9, fc=(180, 180, 180)):
            fnt = self.font_cache.get(fs, get_font(fs))
            self.draw.text((8, self.y), "-" * 24, font=fnt, fill=(*fc, 255))
            self.y += fs + 4

    ctx = DrawCtx(pd, FCACHE, pw)
    ctx.put("[VLM] Llama-3.2-90B-Vision", 11, (20, 100, 180))
    ctx.put("辅助障碍物识别", 11, (20, 100, 180))
    ctx.line()
    ctx.y += 3

    if pab is not None:
        ctx.put(f"VLM通行率: {pab}%", 14, bc)
    else:
        ctx.put("VLM通行率: N/A", 11, (100, 100, 100))

    obstacles = vlm_result.get("obstacles", [])
    ctx.put(f"识别障碍物: {len(obstacles)} 个", 11, (80, 60, 20))
    ctx.line()

    for i, obs in enumerate(obstacles[:7]):
        obs_type = obs.get("type", "?")
        sev = obs.get("severity", "")
        pos = obs.get("position", "")
        desc = obs.get("description", "")[:22]
        sev_c = SEV_C.get(sev, (100, 100, 100))
        icon = SEV_I.get(sev, "-")
        ctx.put(f"#{i+1} {obs_type} [{icon}]", 11, sev_c)
        if desc:
            ctx.put(f"   {pos} | {desc}", 9, (80, 80, 80))

    top = vlm_result.get("top_blocking", [])
    if top:
        ctx.y += 3
        names = ", ".join(str(t)[:12] for t in top[:3])
        ctx.put(f"主要阻断: {names}", 10, (180, 60, 20))

    pi = Image.fromarray(a).convert("RGBA")
    pi.paste(panel, (px, py), mask=panel)
    pi.convert("RGB").save(out_path, quality=92)


# ===== 主流程 =====
def main():
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        results = json.load(f)
    print(f"加载 {len(results)} 条记录")

    # 建立 filename -> sim_data 映射
    data_map = {}
    for item in results:
        ann = item.get("annotated", "")
        fname = os.path.basename(ann)
        local_path = os.path.join(GPU_SAMPLES, fname)
        data_map[fname] = {"local_path": local_path, "sim_data": item}

    local_files = glob.glob(os.path.join(GPU_SAMPLES, "*.jpg"))
    print(f"本地图片: {len(local_files)} 张")

    done_cn = 0
    done_vlm = 0

    for fp in sorted(local_files):
        fname = os.path.basename(fp)
        if fname not in data_map:
            print(f"[SKIP] {fname} 无JSON")
            continue

        sim_data = data_map[fname]["sim_data"]
        coord = sim_data.get("coords", "?")
        direction = sim_data.get("direction", "?")
        obs = sim_data.get("obstacle_score", 0)
        n_dets = sim_data.get("n_dets", 0)

        print(f"\n[{fname}] coord={coord} dir={direction} obs={obs:.1f} dets={n_dets}")

        # Step 1: 叠加中文右侧面板
        out_cn = os.path.join(OUT_CN, fname.replace("_annotated.jpg", "_cn.jpg"))
        try:
            overlay_chinese(fp, sim_data, out_cn)
            sz = os.path.getsize(out_cn) // 1024
            print(f"  [CN OK] {os.path.basename(out_cn)} ({sz}KB)")
            done_cn += 1
        except Exception as e:
            print(f"  [CN ERR] {e}")
            continue

        # Step 2: VLM 识别
        # 尝试用原图（从JSON路径构建），fallback用GPU标注图
        orig_img = sim_data.get("image", "")
        if orig_img and os.path.exists(orig_img):
            vlm_src = orig_img
        else:
            vlm_src = fp
        print(f"  [VLM] 调用... src={os.path.basename(vlm_src)}")
        content, model, elapsed = call_vlm(vlm_src)

        if content:
            vlm_result = parse_vlm(content)
            pab = vlm_result.get("passability_estimate")
            n_obs = len(vlm_result.get("obstacles", []))
            print(f"  [VLM OK] {model} ({elapsed:.1f}s) obs={n_obs} pass={pab}%")
            for o in vlm_result.get("obstacles", [])[:3]:
                print(f"    - {o.get('type','?')} [{o.get('severity','?')}] {o.get('description','')[:35]}")

            # 叠加 VLM 左侧面板
            out_vlm = os.path.join(OUT_VLM, fname.replace("_annotated.jpg", "_vlm.jpg"))
            try:
                overlay_vlm_panel(out_cn, vlm_result, out_vlm)
                sz = os.path.getsize(out_vlm) // 1024
                print(f"  [VLM+CN OK] {os.path.basename(out_vlm)} ({sz}KB)")
                done_vlm += 1
            except Exception as e:
                print(f"  [VLM overlay ERR] {e}")
        else:
            print(f"  [VLM FAIL] 跳过")

    print(f"\n{'='*60}")
    print(f"完成! 中文标注: {done_cn}/{len(local_files)} | VLM增强: {done_vlm}/{done_cn}")
    print(f"中文标注: {OUT_CN}")
    print(f"VLM增强: {OUT_VLM}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
