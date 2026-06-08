# -*- coding: utf-8 -*-
"""
NVIDIA NIM VLM 语义分割 - 最终版
模型: meta/llama-3.2-11b-vision-instruct
策略: detailed_analysis_first (先用文本描述，再用JSON结构化输出)
JSON提取: 支持嵌套花括号的正则
"""
import os, sys, json, base64, time, csv, re
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

# ============================================================
# 配置
# ============================================================
API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL_ID = "meta/llama-3.2-11b-vision-instruct"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

BASE_DIR = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview")
MANIFEST_PATH = BASE_DIR / "manifest.csv"
OUT_DIR = BASE_DIR / "segmentation_results_v3"
OUT_DIR.mkdir(exist_ok=True)
RESULTS_CSV = OUT_DIR / "seg_results.csv"
CHECKPOINT_JSON = OUT_DIR / "checkpoint.json"

MAX_WORKERS = 2
MAX_RETRIES = 3
REQUEST_TIMEOUT = 90
BATCH_DELAY = 0.5

# 成功验证过的prompt策略
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


# ============================================================
# JSON 提取（支持嵌套）
# ============================================================
def extract_json(content):
    """从文本中提取JSON，支持嵌套结构"""
    # 找最后一个 { 和最后一个 }
    last_brace_open = content.rfind('{')
    last_brace_close = content.rfind('}')
    if last_brace_open < 0 or last_brace_close <= last_brace_open:
        return None
    raw = content[last_brace_open:last_brace_close + 1]

    # 中文key替换
    key_map = {
        "建筑占比": "building_pct", "建筑比例": "building_pct",
        "道路占比": "road_pct", "道路比例": "road_pct",
        "绿地占比": "green_pct", "绿化占比": "green_pct",
        "天空占比": "sky_pct",
        "开阔度": "openness",
        "街道峡谷效应": "canyon",
        "峡谷效应": "canyon",
        "建筑密度": "density",
        "步行可达性": "walkability",
        "城市形态": "urban_form",
        "描述": "description_zh",
    }
    for cn, en in key_map.items():
        raw = raw.replace(cn, en)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 修复尾部逗号/换行问题
    raw_fixed = re.sub(r',(\s*[}\]])', r'\1', raw)
    try:
        return json.loads(raw_fixed)
    except:
        pass

    # 逐字段提取
    vals = {}
    for k, en in [
        ("building", "building_pct"), ("road", "road_pct"),
        ("green", "green_pct"), ("sky", "sky_pct"),
        ("openness", "openness"), ("canyon", "canyon"),
        ("density", "density"), ("walkability", "walkability"),
    ]:
        m = re.search(r'"' + k + r'"\s*:\s*(\d+(?:\.\d+)?)', raw)
        if m:
            vals[en] = float(m.group(1))
    if vals:
        vals["_partial"] = True
        return vals
    return None


# ============================================================
# 单张分析
# ============================================================
def analyze_one(item, retry_count=0):
    img_path = item["path"]
    img_name = Path(img_path).name

    try:
        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        return {"status": "file_error", "error": str(e), "img": img_name}

    payload = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            {"type": "text", "text": PROMPT}
        ]}],
        "max_tokens": 512,
        "temperature": 0.2,
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=HEADERS,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        if resp.status_code == 200:
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})
            parsed = extract_json(content)

            if parsed:
                return {
                    "status": "partial" if parsed.get("_partial") else "success",
                    "data": parsed,
                    "tokens": usage.get("completion_tokens", 0),
                    "img": img_name,
                    "raw": content[:200],
                }
            return {"status": "parse_error", "raw": content[:300], "img": img_name}

        elif resp.status_code == 429:
            if retry_count < MAX_RETRIES:
                time.sleep(8 * (retry_count + 1))
                return analyze_one(item, retry_count + 1)
            return {"status": "rate_limited", "img": img_name}
        else:
            return {"status": "http_error", "code": resp.status_code, "error": resp.text[:200], "img": img_name}

    except requests.exceptions.Timeout:
        if retry_count < MAX_RETRIES:
            time.sleep(3 * (retry_count + 1))
            return analyze_one(item, retry_count + 1)
        return {"status": "timeout", "img": img_name}
    except Exception as e:
        return {"status": "error", "error": str(e), "img": img_name}


# ============================================================
# 加载图像
# ============================================================
def load_images():
    rows = []
    with open(MANIFEST_PATH, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    ns_rows = [r for r in rows if r.get("district", "").strip() == "南山区"]
    tasks = []
    for r in ns_rows:
        p = Path(r.get("archive_path", ""))
        if p.exists():
            tasks.append({
                "path": str(p),
                "heading": r.get("heading_label", ""),
                "township": r.get("township", ""),
                "community": r.get("community", ""),
                "urban_form": r.get("urban_form", ""),
                "road_name": r.get("road_name", ""),
                "lng": r.get("lng", ""),
                "lat": r.get("lat", ""),
                "year": r.get("year", ""),
                "point_key": f"{r.get('lng')}_{r.get('lat')}",
            })
    return tasks


# ============================================================
# Checkpoint
# ============================================================
def load_checkpoint():
    if CHECKPOINT_JSON.exists():
        with open(CHECKPOINT_JSON, encoding="utf-8") as f:
            return {item["path"]: item for item in json.load(f).get("done", [])}
    return {}


def save_checkpoint(done_list):
    with open(CHECKPOINT_JSON, "w", encoding="utf-8") as f:
        json.dump({"done": done_list, "count": len(done_list)}, f, ensure_ascii=False, indent=2)


# ============================================================
# CSV 保存
# ============================================================
def save_csv(results):
    if not results:
        return
    all_fields = set()
    for r in results:
        all_fields.update(r.keys())
    priority = ["path", "filename", "heading", "township", "community",
                 "urban_form", "road_name", "lng", "lat", "year", "point_key",
                 "status", "building_pct", "road_pct", "green_pct", "sky_pct",
                 "openness", "canyon", "density", "walkability",
                 "description_zh", "tokens", "error", "raw"]
    ordered = [f for f in priority if f in all_fields]
    ordered += sorted(f for f in all_fields if f not in priority)
    with open(RESULTS_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ordered, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)
    print(f"已保存: {RESULTS_CSV} ({len(results)}条)")


# ============================================================
# 主循环
# ============================================================
def main():
    import sys
    print("=" * 60, flush=True)
    print("NVIDIA NIM VLM 语义分割 (最终版)", flush=True)
    print(f"模型: {MODEL_ID}", flush=True)
    print("=" * 60, flush=True)

    tasks = load_images()
    print(f"南山区图像: {len(tasks)} 张", flush=True)

    checkpoint = load_checkpoint()
    remaining = [t for t in tasks if t["path"] not in checkpoint]
    print(f"已处理: {len(checkpoint)} | 剩余: {len(remaining)}", flush=True)

    if not remaining:
        print("全部完成!", flush=True)
        all_results = list(checkpoint.values())
        save_csv(all_results)
        summarize(all_results)
        return

    print(f"\n开始处理 {len(remaining)} 张...", flush=True)
    done_list = list(checkpoint.values())
    results = list(checkpoint.values())

    batch_num = len(checkpoint)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {}
        for t in remaining:
            def _run(task=t):
                return task, analyze_one(task)
            futures[ex.submit(_run)] = t

        for future in as_completed(futures):
            batch_num += 1
            task, res = future.result()

            row = {
                "path": task["path"],
                "filename": Path(task["path"]).name,
                "heading": task["heading"],
                "township": task["township"],
                "community": task["community"],
                "urban_form": task.get("urban_form", ""),
                "road_name": task.get("road_name", ""),
                "lng": task["lng"],
                "lat": task["lat"],
                "year": task["year"],
                "point_key": task["point_key"],
                "status": res["status"],
            }

            if res["status"] in ("success", "partial"):
                row.update(res["data"])
                row["tokens"] = res.get("tokens", 0)
                b = res["data"].get("building_pct", "?")
                g = res["data"].get("green_pct", "?")
                r = res["data"].get("road_pct", "?")
                s = res["data"].get("sky_pct", "?")
                uf = res["data"].get("urban_form", "?")
                src = "[P]" if res["status"] == "partial" else "[OK]"
                print(f"  [{batch_num}/{len(tasks)}] {src} {task['heading']:4s} | "
                      f"建筑{b}% 道路{r}% 绿地{g}% 天空{s}% | "
                      f"{task['township']} | {uf}")
            else:
                row["error"] = res.get("error", res.get("raw", ""))
                print(f"  [{batch_num}/{len(tasks)}] ERR {task['heading']:4s} | "
                      f"{task['township']} | {res['status']}: {row['error'][:60]}")

            results.append(row)
            done_list.append(row)

            if batch_num % 20 == 0:
                save_checkpoint(done_list)
                save_csv(results)

            time.sleep(BATCH_DELAY)

    save_checkpoint(done_list)
    save_csv(results)
    summarize(results)


def summarize(results):
    print("\n" + "=" * 60)
    print("分析结果汇总")
    print("=" * 60)

    ok = [r for r in results if r.get("status") in ("success", "partial")]
    print(f"总任务: {len(results)} | 成功: {len(ok)} | 失败: {len(results) - len(ok)}")

    if not ok:
        return

    import statistics

    def avg(l): return statistics.mean(l) if l else 0
    def rng(l): return f"{min(l):.0f}-{max(l):.0f}" if l else "N/A"
    def med(l): return statistics.median(l) if l else 0

    fields = [
        ("building_pct", "建筑%"), ("road_pct", "道路%"),
        ("green_pct", "绿地%"), ("sky_pct", "天空%"),
    ]
    print(f"\n覆盖率统计:")
    for k, name in fields:
        vals = [r.get(k, 0) for r in ok if r.get(k) is not None
                and isinstance(r.get(k), (int, float))]
        if vals:
            print(f"  {name:6s}: 平均{avg(vals):5.1f}% | 范围 {rng(vals)} | "
                  f"中位数{med(vals):.1f}%")

    print(f"\n感知评分:")
    for k, name in [("openness", "开阔度"), ("canyon", "峡谷"),
                     ("density", "建筑密度"), ("walkability", "步行性")]:
        vals = [r.get(k, 0) for r in ok if r.get(k) is not None
                and isinstance(r.get(k), (int, float))]
        if vals:
            print(f"  {name:6s}: 平均{avg(vals):5.1f}/10 | 范围 {rng(vals)}")

    from collections import Counter
    forms = Counter(r.get("urban_form", "未知") for r in ok)
    print(f"\n城市形态分布:")
    for k, v in forms.most_common():
        print(f"  {k}: {v} 张({v/len(ok)*100:.1f}%)")

    by_twp = defaultdict(list)
    for r in ok:
        b = r.get("building_pct")
        if b is not None:
            by_twp[r.get("township", "")].append(b)
    print(f"\n各街道平均建筑覆盖率:")
    for twp in sorted(by_twp.keys()):
        vals = by_twp[twp]
        if vals:
            print(f"  {twp}: {avg(vals):.1f}% (n={len(vals)})")

    print(f"\n完整结果: {RESULTS_CSV}")


if __name__ == "__main__":
    main()
