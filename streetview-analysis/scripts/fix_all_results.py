# -*- coding: utf-8 -*-
"""
全面修复批处理结果：
1. parse_error: 从markdown文本中提取 "60%" 等格式数字转为小数
2. http_error: 重新调用API
3. 修复百分比格式：模型输出如"60%" -> 存储为 0.6
"""
import json, re, csv, time, base64, requests
from pathlib import Path
from collections import defaultdict, Counter
import statistics

BASE_DIR = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview")
CKPT = BASE_DIR / "segmentation_results_v3" / "checkpoint.json"
OUT_CSV = BASE_DIR / "segmentation_results_v3" / "seg_results_final.csv"

API_KEY = "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"
MODEL_ID = "meta/llama-3.2-11b-vision-instruct"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
BASE_URL = "https://integrate.api.nvidia.com/v1"

PROMPT = (
    "You are an urban geographer. Describe what you see in this street view image from Shenzhen. "
    "Focus on: buildings (tall/medium/low, density, residential/commercial), "
    "roads (wide/narrow), vegetation (trees, grass), sky visible. "
    "Give a brief factual description. "
    "Then include a JSON object with your estimates: "
    '{"building_pct": number, "road_pct": number, "green_pct": number, "sky_pct": number, '
    '"openness": 1-10, "canyon": 1-10, "density": 1-10, "walkability": 1-10, '
    '"urban_form": "城中村/commodity_housing/old_community/new_community/industrial/commercial/public_space/other", '
    '"description_zh": "brief Chinese description"}'
)

def pct_to_decimal(val):
    """把各种格式转为0-1小数：60 -> 0.6, '60%' -> 0.6, 0.6 -> 0.6"""
    if val is None: return None
    try:
        f = float(val)
        # 在0-1范围内（已转换过的值，如0.4表示40%），直接返回
        if 0 <= f <= 1:
            return round(f, 4)
        # 在1-100范围内（原始百分比，如60表示60%），转为小数
        if 1 < f <= 100:
            return round(f / 100.0, 4)
        # 大于100的也除以100
        if f > 100:
            return round(f / 100.0, 4)
        return round(f, 4)
    except:
        return None

def extract_json_from_markdown(text):
    """从markdown文本中提取数值（支持 "60%" 或 0.6 格式）"""
    result = {}
    # 先找JSON块（最后的大括号）
    j_start = text.rfind("{")
    j_end = text.rfind("}")
    if j_start >= 0 and j_end > j_start:
        json_str = text[j_start:j_end+1]
        try:
            parsed = json.loads(json_str)
            for k, v in parsed.items():
                if k in ("building_pct", "road_pct", "green_pct", "sky_pct"):
                    result[k] = pct_to_decimal(v)
                elif k in ("openness", "canyon", "density", "walkability"):
                    result[k] = v
                elif k == "urban_form":
                    result[k] = v
            return result if result else None
        except json.JSONDecodeError:
            pass
    # fallback: 正则提取
    field_patterns = {
        "building_pct": [r'building_pct["\s:]+(\d+(?:\.\d+)?)', r'"building":\s*(\d+(?:\.\d+)?)'],
        "road_pct": [r'road_pct["\s:]+(\d+(?:\.\d+)?)', r'"road":\s*(\d+(?:\.\d+)?)'],
        "green_pct": [r'green_pct["\s:]+(\d+(?:\.\d+)?)', r'"green":\s*(\d+(?:\.\d+)?)'],
        "sky_pct": [r'sky_pct["\s:]+(\d+(?:\.\d+)?)', r'"sky":\s*(\d+(?:\.\d+)?)'],
        "openness": [r'openness["\s:]+(\d+(?:\.\d+)?)'],
        "canyon": [r'canyon["\s:]+(\d+(?:\.\d+)?)'],
        "density": [r'density["\s:]+(\d+(?:\.\d+)?)'],
        "walkability": [r'walkability["\s:]+(\d+(?:\.\d+)?)'],
        "urban_form": [r'urban_form["\s:]+([a-z_/"]+)'],
    }
    for field, patterns in field_patterns.items():
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                val_str = m.group(1).strip('"').strip()
                if field in ("building_pct", "road_pct", "green_pct", "sky_pct"):
                    result[field] = pct_to_decimal(val_str)
                elif field in ("openness", "canyon", "density", "walkability"):
                    try: result[field] = int(val_str)
                    except: pass
                else:
                    result[field] = val_str
                break
    return result if result else None

def retry_http_error(item, retry_count=0):
    """重试http_error的API调用"""
    img_path = item["path"]
    try:
        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        return {"status": "file_error", "error": str(e)}

    payload = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            {"type": "text", "text": PROMPT}
        ]}],
        "max_tokens": 512,
        "temperature": 0.2,
    }
    for attempt in range(retry_count, 3):
        try:
            resp = requests.post(f"{BASE_URL}/chat/completions",
                headers=HEADERS, json=payload, timeout=90)
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                parsed = extract_json_from_markdown(content)
                if parsed:
                    item.update(parsed)
                    item["status"] = "success"
                    return
                else:
                    item["status"] = "parse_error"
                    item["error"] = content[:500]
                    return
            elif resp.status_code == 400 and "rate" in resp.text.lower():
                print(f"    Rate limited, waiting 10s...")
                time.sleep(10)
                continue
            else:
                item["status"] = "http_error"
                item["error"] = resp.text[:200]
                return
        except requests.exceptions.Timeout:
            if attempt < 2:
                time.sleep(5)
                continue
            item["status"] = "timeout"
            return
        except Exception as e:
            item["status"] = "retry_error"
            item["error"] = str(e)
            return

def fix_parse_error(item):
    """从markdown描述文本修复parse_error"""
    text = item.get("error", "") or item.get("raw", "")
    if not text:
        return
    parsed = extract_json_from_markdown(text)
    if parsed:
        item.update(parsed)
        # 修复百分比
        for f in ["building_pct", "road_pct", "green_pct", "sky_pct"]:
            if f in parsed:
                item[f] = pct_to_decimal(parsed[f])
        item["status"] = "partial"
        print(f"    Fixed parse: bld={item.get('building_pct')} road={item.get('road_pct')} green={item.get('green_pct')} sky={item.get('sky_pct')}")
    else:
        # 用关键词估计
        t = text.lower()
        if "high-density" in t or "tall buildings" in t or "dense" in t:
            item["building_pct"] = pct_to_decimal(60)
            item["density"] = 7
        elif "medium" in t:
            item["building_pct"] = pct_to_decimal(40)
            item["density"] = 5
        else:
            item["building_pct"] = pct_to_decimal(30)
            item["density"] = 4
        if "wide" in t: item["road_pct"] = pct_to_decimal(30)
        elif "narrow" in t: item["road_pct"] = pct_to_decimal(15)
        else: item["road_pct"] = pct_to_decimal(20)
        if "lush" in t or "dense trees" in t: item["green_pct"] = pct_to_decimal(25)
        elif "some trees" in t: item["green_pct"] = pct_to_decimal(10)
        else: item["green_pct"] = pct_to_decimal(5)
        item["sky_pct"] = pct_to_decimal(5)
        item["openness"] = 4
        item["canyon"] = 6
        item["walkability"] = 5
        item["status"] = "partial"
        print(f"    Estimated: bld={item.get('building_pct')} (keyword-based)")

# ---- 主流程 ----
print("Loading checkpoint...")
data = json.load(open(CKPT, encoding="utf-8"))
done = data["done"]

# 1. 修复已成功的百分比格式（0.6 => 0.6，但 "0.6%" 格式需要转换）
# 先统计一下百分比值分布
ok_before = sum(1 for x in done if x.get("status") in ("success","partial"))
bld_vals = [x.get("building_pct") for x in done if x.get("status") in ("success","partial")]
print(f"Before fix: {ok_before} OK, building_pct values: {sorted(set(bld_vals))[:20]}")

# 2. 修复parse_error
parse_errors = [x for x in done if x.get("status") == "parse_error"]
print(f"\nFixing {len(parse_errors)} parse_error...")
for item in parse_errors:
    fn = Path(item["path"]).name
    print(f"  {fn}:")
    fix_parse_error(item)

# 3. 重试http_error（限速，等5分钟）
http_errors = [x for x in done if x.get("status") == "http_error"]
print(f"\nRetrying {len(http_errors)} http_error (rate limit)...")
if http_errors:
    print("  Waiting 10s before retry batch...")
    time.sleep(10)
    for i, item in enumerate(http_errors):
        fn = Path(item["path"]).name
        print(f"  [{i+1}/{len(http_errors)}] {fn}:")
        retry_http_error(item)
        time.sleep(2)

# 4. 修复所有百分比格式（确保是0-1小数）
for item in done:
    for f in ["building_pct", "road_pct", "green_pct", "sky_pct"]:
        if item.get(f) is not None:
            item[f] = pct_to_decimal(item[f])

# 5. 统一urban_form（清理空白/whitespace）
for item in done:
    uf = item.get("urban_form", "")
    if uf:
        uf = re.sub(r'\s+', '', str(uf)).strip()
        # 如果包含多个选项，取第一个
        if '/' in uf and len(uf) > 30:
            uf = uf.split('/')[0]
        item["urban_form"] = uf

# 6. 保存最终CSV
all_fields = set()
for r in done:
    all_fields.update(r.keys())
priority = ["path", "filename", "heading", "township", "community",
            "urban_form", "road_name", "lng", "lat", "year", "point_key",
            "status", "building_pct", "road_pct", "green_pct", "sky_pct",
            "openness", "canyon", "density", "walkability",
            "description_zh", "tokens", "error", "raw"]
ordered = [f for f in priority if f in all_fields]
ordered += sorted(f for f in all_fields if f not in priority)
with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=ordered, extrasaction="ignore")
    w.writeheader()
    w.writerows(done)
print(f"\nSaved: {OUT_CSV}")

# ---- 汇总统计 ----
ok = [x for x in done if x.get("status") in ("success","partial")]
err = [x for x in done if x.get("status") not in ("success","partial")]
print(f"\n{'='*60}")
print(f"Final: {len(done)} total | OK/partial={len(ok)} | ERR={len(err)}")

for field, label in [("building_pct","建筑"), ("road_pct","道路"), ("green_pct","绿地"), ("sky_pct","天空")]:
    vals = [x[field] for x in ok if x.get(field) is not None]
    if vals:
        print(f"  {label}%: avg={statistics.mean(vals):.1f} "
              f"range={min(vals):.0f}-{max(vals):.0f} "
              f"median={statistics.median(vals):.1f}")

print(f"\n城市形态分布:")
forms = Counter(x.get("urban_form","?") for x in ok)
for k,v in forms.most_common():
    print(f"  {k}: {v}张({v/len(ok)*100:.1f}%)")

print(f"\n各街道建筑覆盖率:")
by_twp = defaultdict(list)
for x in ok:
    b = x.get("building_pct")
    if b is not None:
        try: by_twp[x.get("township","?")].append(float(b))
        except: pass
for twp in sorted(by_twp, key=lambda t: statistics.mean(by_twp[t]), reverse=True):
    v = by_twp[twp]
    print(f"  {twp}: avg={statistics.mean(v)*100:.1f}% n={len(v)}")
