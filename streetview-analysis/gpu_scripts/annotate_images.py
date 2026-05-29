#!/usr/bin/env python3
"""
南山区街景障碍标注图 - 带中文标签
"""
import json, os, sys, glob
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import matplotlib.font_manager as fm
import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

# ===================== 中文字体配置 =====================
CHINESE_FONT = None
# 优先使用下载的 NotoSansCJK 字体
LOCAL_FONT = r"e:\xicha gis 智能定位\自选年份\NotoSansCJK.otf"
if os.path.exists(LOCAL_FONT):
    try:
        fm.fontManager.addfont(LOCAL_FONT)
        CHINESE_FONT = fm.FontProperties(fname=LOCAL_FONT).get_name()
        print(f"本地字体: {LOCAL_FONT} -> {CHINESE_FONT}")
    except Exception as ex:
        print(f"加载本地字体失败: {ex}")
# 按优先级查找系统字体作为后备
FONT_CANDS = ["SimHei", "Microsoft YaHei", "SimSun", "WenQuanYi Micro Hei", "Noto Sans CJK SC"]
for cand in FONT_CANDS:
    matches = [fp for fp in fm.findSystemFonts() if cand.lower() in fp.lower()]
    if matches and CHINESE_FONT is None:
        try:
            fm.fontManager.addfont(matches[0])
            CHINESE_FONT = fm.FontProperties(fname=matches[0]).get_name()
            print(f"系统字体: {matches[0]} -> {CHINESE_FONT}")
            break
        except Exception:
            pass

if CHINESE_FONT is None:
    # 找任何CJK字体
    for fp in fm.findSystemFonts():
        fn = os.path.basename(fp).lower()
        if any(k in fn for k in ["cjk", "chinese", "hei", "song", "yuan", "ming"]):
            try:
                fm.fontManager.addfont(fp)
                CHINESE_FONT = fm.FontProperties(fname=fp).get_name()
                print(f"退而求其次: {fp} -> {CHINESE_FONT}")
                break
            except Exception:
                pass

if CHINESE_FONT:
    plt.rcParams["font.family"] = CHINESE_FONT
    plt.rcParams["axes.unicode_minus"] = False
    print(f"matplotlib字体已设置为: {CHINESE_FONT}")
else:
    print("警告: 未找到中文字体，中文可能显示为方块")

# ===================== 配置 =====================
LOCAL_STREETVIEW = r"e:\xicha gis 智能定位\自选年份\baidu_streetview\南山区"
JSON_FILE = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results\all_results_fixed.json"
OUTPUT_DIR = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results\annotated_images"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ===================== 类别映射 =====================
COCO_CN = {
    "person":        "行人",
    "bicycle":       "自行车",
    "car":           "汽车",
    "motorcycle":    "摩托车",
    "bus":           "公交车",
    "truck":         "货车",
    "bench":         "长椅",
    "stop sign":     "停车标志",
    "traffic light": "交通灯",
    "fire hydrant":  "消防栓",
    "chair":         "椅子",
    "table":         "桌子",
    "potted plant":  "盆栽",
    "stroller":      "婴儿车",
}

CAT_COLORS = {
    "person":        "#E74C3C",
    "bicycle":       "#2ECC71",
    "car":           "#E74C3C",
    "motorcycle":     "#F39C12",
    "bus":            "#9B59B6",
    "truck":          "#C0392B",
    "bench":          "#1ABC9C",
    "stop sign":      "#7F8C8D",
    "traffic light":  "#F1C40F",
    "fire hydrant":   "#3498DB",
    "chair":          "#1ABC9C",
    "table":          "#1ABC9C",
    "potted plant":  "#27AE60",
}

def coco_cn(name):
    return COCO_CN.get(name, name)

def cat_color(name):
    return CAT_COLORS.get(name, "#3498DB")

# ===================== 加载数据 =====================
with open(JSON_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

nanshan = [r for r in data if "/南山区/" in r["image"]]
print(f"南山区: {len(nanshan)} 张图片")

def remote_to_local(path):
    parts = path.split("/")
    if len(parts) >= 10 and parts[4] == "images" and parts[5] == "南山区":
        street    = parts[6]
        community = parts[7]
        category  = parts[8]
        coords    = parts[9]
        filename  = parts[10]
        return os.path.join(LOCAL_STREETVIEW, street, community, category, coords, filename)
    return None

def get_street(path):
    parts = path.split("/")
    return parts[6] if len(parts) >= 7 and parts[5] == "南山区" else "未知"

def get_coords(path):
    parts = path.split("/")
    return parts[9] if len(parts) >= 10 else ""

# ===================== 绘图函数 =====================
def draw_one(img_path, detections, score, street, out_path):
    if not os.path.exists(img_path):
        return False

    img = Image.open(img_path)
    w_img, h_img = img.size
    fig_h = max(9, h_img / 80)
    fig, ax = plt.subplots(figsize=(14, fig_h))
    ax.imshow(img)
    ax.axis("off")

    title_font = fm.FontProperties(fname=next(
        (fp for fp in fm.findSystemFonts()
         if CHINESE_FONT and CHINESE_FONT in fm.FontProperties(fname=fp).get_name()),
        fm.findSystemFonts()[0]
    )) if CHINESE_FONT else None
    ax.set_title(f"{street}街道  |  障碍评分: {score:.1f}",
                 fontsize=13, fontweight="bold", pad=8,
                 fontproperties=title_font)

    drawn_cats = []
    for det in detections:
        if det["conf"] < 0.35:
            continue
        x1, y1, x2, y2 = det["bbox"]
        rw, rh = x2 - x1, y2 - y1
        if rw <= 0 or rh <= 0:
            continue
        name = det["coco_name"]
        color = cat_color(name)
        cn = coco_cn(name)

        pad_v = max(3, int(0.012 * max(w_img, h_img)))
        rect = FancyBboxPatch(
            (x1, y1), rw, rh,
            boxstyle=f"round,pad={pad_v}",
            linewidth=2.5, edgecolor=color,
            facecolor=color + "30", zorder=3
        )
        ax.add_patch(rect)

        lbl = f"{cn} {det['conf']:.0%}"
        ax.text(x1 + 5, y1 - 5, lbl,
                fontsize=9, color="white", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", facecolor=color, alpha=0.9, edgecolor="none"),
                zorder=4)
        drawn_cats.append((cn, color))

    # 评分标签
    if score < 10:   bc, sl = "#27AE60", "畅通"
    elif score < 20: bc, sl = "#2ECC71", "较畅通"
    elif score < 40: bc, sl = "#F1C40F", "一般"
    elif score < 60: bc, sl = "#E67E22", "较困难"
    elif score < 80: bc, sl = "#E74C3C", "困难"
    else:             bc, sl = "#C0392B", "严重"

    ax.text(w_img - 6, 20,
            f"障碍评分: {score:.1f}  ({sl})",
            fontsize=10, color="white", fontweight="bold",
            ha="right", va="center",
            bbox=dict(boxstyle="round,pad=0.5", facecolor=bc, alpha=0.9))

    # 图例
    seen, patches = set(), []
    for cn, color in drawn_cats:
        if cn not in seen:
            seen.add(cn)
            patches.append(mpatches.Patch(color=color, label=cn))
    if patches:
        ax.legend(handles=patches, loc="upper left", fontsize=8,
                  framealpha=0.85, edgecolor="#ccc", ncol=1)

    plt.tight_layout(pad=0)
    plt.savefig(out_path, dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return True

# ===================== 选择样本 =====================
sorted_ns = sorted(nanshan, key=lambda x: x["accessibility_score"])
high = [r for r in sorted_ns if r["accessibility_score"] >= 50]
mid  = [r for r in sorted_ns if 20 <= r["accessibility_score"] < 50]
low  = [r for r in sorted_ns if r["accessibility_score"] < 20]

print(f"高分(>=50): {len(high)} | 中分(20-50): {len(mid)} | 低分(<20): {len(low)}")

def pick_samples(group, n=3):
    if not group:
        return []
    s = sorted(group, key=lambda x: x["accessibility_score"])
    res = []
    if len(s) >= 1: res.append(s[-1])  # 最高
    if len(s) >= 3: res.append(s[len(s)//2])  # 中间
    if len(s) >= 2: res.append(s[0])  # 最低
    return res[:n]

selected = []
selected += pick_samples(high, 3)
selected += pick_samples(mid, 3)
selected += pick_samples(low, 3)

# 按街道各选最差一张
from collections import defaultdict
by_street = defaultdict(list)
for r in nanshan:
    by_street[get_street(r["image"])].append(r)

for street, recs in by_street.items():
    worst = sorted(recs, key=lambda x: x["accessibility_score"])[-1]
    if worst not in selected:
        selected.append(worst)

# 按街道各选最好一张
for street, recs in by_street.items():
    best = sorted(recs, key=lambda x: x["accessibility_score"])[0]
    if best not in selected:
        selected.append(best)

seen, uniq = set(), []
for r in selected:
    if r["image"] not in seen:
        seen.add(r["image"])
        uniq.append(r)

print(f"共 {len(uniq)} 张图片待标注\n")

# ===================== 开始绘制 =====================
ok_count = 0
for i, r in enumerate(uniq, 1):
    lp = remote_to_local(r["image"])
    if not lp:
        print(f"  [跳过] 路径无法映射: {r['image']}")
        continue
    if not os.path.exists(lp):
        print(f"  [跳过] 本地文件不存在: {lp[-80:]}")
        continue
    if not r.get("detections"):
        print(f"  [跳过] 无检测结果: {r['image'].split('/')[-1]}")
        continue

    street = get_street(r["image"])
    score  = r["accessibility_score"]
    coords = get_coords(r["image"])
    fn_out = f"标注{i:02d}_{street}_{score:.0f}分_{coords}.png"
    out_path = os.path.join(OUTPUT_DIR, fn_out)

    ok = draw_one(lp, r["detections"], score, street, out_path)
    if ok:
        ok_count += 1
        print(f"  [OK] {fn_out}")
    else:
        print(f"  [失败] {fn_out}")

print(f"\n完成: {ok_count}/{len(uniq)} 张已标注")
print(f"输出: {OUTPUT_DIR}")
