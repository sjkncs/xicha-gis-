# -*- coding: utf-8 -*-
"""
NVIDIA NIM Llama 3.2 Vision 语义分割 - 完整批量处理脚本
模型: meta/llama-3.2-11b-vision-instruct (7-8s/张, 速度快!)
"""
import os, sys, json, base64, time, csv, re, io
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

# 路径
BASE_DIR = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview")
MANIFEST_PATH = BASE_DIR / "manifest.csv"
OUT_DIR = BASE_DIR / "segmentation_results"
OUT_DIR.mkdir(exist_ok=True)
RESULTS_CSV = OUT_DIR / "seg_results.csv"
CHECKPOINT_JSON = OUT_DIR / "checkpoint.json"

# 并发配置（避免触发速率限制）
MAX_WORKERS = 2        # 并发数
MAX_RETRIES = 3        # 最大重试次数
REQUEST_TIMEOUT = 90    # 单次请求超时(s)
BATCH_DELAY = 0.5      # 每批间隔(s)

PROMPT = (
    '你是一位城市地理专家，分析深圳街景图像。'
    '严格按以下JSON格式输出，不要有任何其他文字：\n'
    '{\n'
    '  "building_pct": 50,\n'
    '  "road_pct": 20,\n'
    '  "green_pct": 10,\n'
    '  "sky_pct": 20,\n'
    '  "openness": 6,\n'
    '  "street_canyon": 7,\n'
    '  "building_density": 8,\n'
    '  "walkability": 5,\n'
    '  "urban_form": "商品房住宅街区",\n'
    '  "description_zh": "描述"\n'
    '}\n'
)


# ============================================================
# JSON 解析（兼容多种格式）
# ============================================================
def parse_json_response(content):
    """解析模型输出，兼容中文/英文key，修复截断JSON"""
    # 策略1: 代码块
    m = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
    if m:
        raw = m.group(1).strip()
    else:
        raw = content.strip()

    # 替换中文key
    key_map = {
        "建筑占比": "building_pct", "建筑比例": "building_pct",
        "道路占比": "road_pct", "道路比例": "road_pct",
        "绿地占比": "green_pct", "绿化占比": "green_pct",
        "天空占比": "sky_pct",
        "开阔度": "openness", "空间开阔度": "openness",
        "街道峡谷效应": "street_canyon", "峡谷效应": "street_canyon",
        "建筑密度": "building_density", "建筑密度感知": "building_density",
        "步行可达性": "walkability", "步行性": "walkability",
        "城市形态": "urban_form", "城市形态分类": "urban_form",
        "描述": "description_zh", "简短描述": "description_zh",
    }
    for cn, en in key_map.items():
        raw = raw.replace(cn, en)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 截断JSON修复: 尝试补全缺失的闭合括号
        open_braces = raw.count('{')
        close_braces = raw.count('}')
        if open_braces > close_braces:
            raw_fixed = raw + '}' * (open_braces - close_braces)
            try:
                return json.loads(raw_fixed)
            except:
                pass
        # 修复尾部逗号
        raw_fixed = re.sub(r',(\s*[}\]])', r'\1', raw)
        try:
            return json.loads(raw_fixed)
        except:
            return {"_raw": raw[:500]}


# ============================================================
# 单张图像分析
# ============================================================
def analyze_one(item, retry_count=0):
    """调用 VLM 分析单张图像"""
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
        "max_tokens": 256,
        "temperature": 0.1,
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
            parsed = parse_json_response(content)

            if parsed and "_raw" not in parsed:
                return {
                    "status": "success",
                    "data": parsed,
                    "tokens": usage.get("completion_tokens", 0),
                    "img": img_name,
                }
            elif parsed and "_raw" in parsed:
                return {
                    "status": "parse_error",
                    "raw": parsed["_raw"][:500],
                    "img": img_name,
                }
            else:
                return {
                    "status": "parse_error",
                    "raw": content[:500],
                    "img": img_name,
                }
        elif resp.status_code == 429:
            # Rate limit - retry after delay
            if retry_count < MAX_RETRIES:
                time.sleep(5 * (retry_count + 1))
                return analyze_one(item, retry_count + 1)
            return {"status": "rate_limited", "img": img_name}
        else:
            return {
                "status": "http_error",
                "code": resp.status_code,
                "error": resp.text[:200],
                "img": img_name,
            }

    except requests.exceptions.Timeout:
        if retry_count < MAX_RETRIES:
            time.sleep(3 * (retry_count + 1))
            return analyze_one(item, retry_count + 1)
        return {"status": "timeout", "img": img_name}
    except Exception as e:
        return {"status": "error", "error": str(e), "img": img_name}


# ============================================================
# 加载图像列表
# ============================================================
def load_images():
    print(f"读取清单: {MANIFEST_PATH}")
    rows = []
    with open(MANIFEST_PATH, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    # 只处理南山区
    ns_rows = [r for r in rows if r.get("district", "").strip() == "南山区"]
    print(f"南山区图像: {len(ns_rows)} 张")

    # 展平（4方向）
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
        else:
            print(f"  跳过(不存在): {p}")

    print(f"有效任务: {len(tasks)} 张")
    return tasks


# ============================================================
# 加载 checkpoint（断点续传）
# ============================================================
def load_checkpoint():
    done_paths = {}
    if CHECKPOINT_JSON.exists():
        with open(CHECKPOINT_JSON, encoding="utf-8") as f:
            data = json.load(f)
            for item in data.get("done", []):
                done_paths[item["path"]] = item
    return done_paths


def save_checkpoint(done_list):
    with open(CHECKPOINT_JSON, "w", encoding="utf-8") as f:
        json.dump({"done": done_list, "count": len(done_list)}, f, ensure_ascii=False, indent=2)


# ============================================================
# 保存结果 CSV
# ============================================================
def save_csv(results):
    if not results:
        return
    # 合并所有字段
    all_fields = set()
    for r in results:
        all_fields.update(r.keys())
    # 固定字段优先
    priority = ["path", "filename", "heading", "township", "community",
                 "urban_form_source", "road_name", "lng", "lat", "year", "point_key",
                 "status", "building_pct", "road_pct", "green_pct", "sky_pct",
                 "openness", "street_canyon", "building_density", "walkability",
                 "urban_form", "description_zh", "tokens", "error"]
    ordered = [f for f in priority if f in all_fields]
    ordered += sorted(f for f in all_fields if f not in priority)
    with open(RESULTS_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ordered, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)
    print(f"已保存: {RESULTS_CSV}")


# ============================================================
# 主循环
# ============================================================
def main():
    print("=" * 60)
    print("NVIDIA NIM 语义分割批量处理")
    print(f"模型: {MODEL_ID}")
    print(f"并发: {MAX_WORKERS}")
    print("=" * 60)

    # Load tasks
    tasks = load_images()
    if not tasks:
        print("没有找到有效图像！")
        return

    # Load checkpoint
    checkpoint = load_checkpoint()
    remaining = [t for t in tasks if t["path"] not in checkpoint]
    print(f"\n已处理: {len(checkpoint)} | 剩余: {len(remaining)}")

    if not remaining:
        print("全部处理完成！")
        # Load all results
        all_results = list(checkpoint.values())
        save_csv(all_results)
        summarize(all_results)
        return

    # Batch processing with concurrency control
    print(f"\n开始处理 {len(remaining)} 张图像...")
    done_list = list(checkpoint.values())
    results = list(checkpoint.values())

    def process_task(task):
        return task, analyze_one(task)

    batch_num = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(process_task, t): t for t in remaining}

        for future in as_completed(futures):
            batch_num += 1
            task, res = future.result()

            row = {
                "path": task["path"],
                "filename": Path(task["path"]).name,
                "heading": task["heading"],
                "township": task["township"],
                "community": task["community"],
                "urban_form_source": task["urban_form"],
                "road_name": task["road_name"],
                "lng": task["lng"],
                "lat": task["lat"],
                "year": task["year"],
                "point_key": task["point_key"],
                "status": res["status"],
            }

            if res["status"] == "success":
                row.update(res["data"])
                row["tokens"] = res.get("tokens", 0)
                b = res["data"].get("building_pct", 0)
                g = res["data"].get("green_pct", 0)
                r = res["data"].get("road_pct", 0)
                print(f"  [{batch_num}/{len(remaining)}] OK  {task['heading']:4s} | 建筑{b}% 道路{r}% 绿地{g}% | "
                      f"{task['township']} | {res['data'].get('urban_form','')}")
            else:
                row["error"] = res.get("error", res.get("raw", ""))
                row["tokens"] = 0
                print(f"  [{batch_num}/{len(remaining)}] ERR {task['heading']:4s} | "
                      f"{task['township']} | {res['status']}: {row['error'][:60]}")

            results.append(row)
            done_list.append(row)

            # 每20张保存checkpoint
            if batch_num % 20 == 0:
                save_checkpoint(done_list)
                save_csv(results)

            # 速率控制
            time.sleep(BATCH_DELAY)

    # Final save
    save_checkpoint(done_list)
    save_csv(results)
    summarize(results)


def summarize(results):
    print("\n" + "=" * 60)
    print("分析结果汇总")
    print("=" * 60)

    ok = [r for r in results if r.get("status") == "success"]
    print(f"总任务: {len(results)} | 成功: {len(ok)} | 失败: {len(results) - len(ok)}")

    if not ok:
        return

    import statistics

    def avg(lst): return statistics.mean(lst) if lst else 0
    def rng(lst): return f"{min(lst):.0f}-{max(lst):.0f}" if lst else "N/A"

    bld = [r.get("building_pct", 0) for r in ok if r.get("building_pct") is not None]
    rd  = [r.get("road_pct", 0) for r in ok if r.get("road_pct") is not None]
    grn = [r.get("green_pct", 0) for r in ok if r.get("green_pct") is not None]
    sky = [r.get("sky_pct", 0) for r in ok if r.get("sky_pct") is not None]
    opn = [r.get("openness", 0) for r in ok if r.get("openness") is not None]
    can = [r.get("street_canyon", 0) for r in ok if r.get("street_canyon") is not None]
    den = [r.get("building_density", 0) for r in ok if r.get("building_density") is not None]
    wal = [r.get("walkability", 0) for r in ok if r.get("walkability") is not None]

    print(f"\n覆盖率统计:")
    print(f"  建筑: 平均{avg(bld):.1f}% | 范围 {rng(bld)}")
    print(f"  道路: 平均{avg(rd):.1f}% | 范围 {rng(rd)}")
    print(f"  绿地: 平均{avg(grn):.1f}% | 范围 {rng(grn)}")
    print(f"  天空: 平均{avg(sky):.1f}% | 范围 {rng(sky)}")

    print(f"\n感知评分:")
    print(f"  开阔度:   平均{avg(opn):.1f}/10 | 范围 {rng(opn)}")
    print(f"  峡谷效应: 平均{avg(can):.1f}/10 | 范围 {rng(can)}")
    print(f"  建筑密度: 平均{avg(den):.1f}/10 | 范围 {rng(den)}")
    print(f"  步行可达性: 平均{avg(wal):.1f}/10 | 范围 {rng(wal)}")

    from collections import Counter
    forms = Counter(r.get("urban_form", "未知") for r in ok)
    print(f"\n城市形态分布:")
    for k, v in forms.most_common(10):
        print(f"  {k}: {v} 张({v/len(ok)*100:.1f}%)")

    # 按街道统计建筑覆盖
    by_twp = defaultdict(list)
    for r in ok:
        b = r.get("building_pct", 0)
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
