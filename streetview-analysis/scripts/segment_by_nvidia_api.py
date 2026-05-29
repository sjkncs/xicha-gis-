# -*- coding: utf-8 -*-
"""用 NVIDIA NIM API 做语义分割 - 无需本地 GPU/PyTorch 安装
API Key: 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
BaseUrl: https://integrate.api.nvidia.com/v1
"""
import os
import sys
import json
import base64
import time
import csv
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# 配置
# ============================================================
API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"

# 图像目录
BASE_DIR = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview")
NS_MANIFEST = BASE_DIR / "ns_manifest.csv"

# 输出目录
OUT_DIR = BASE_DIR / "segmentation_results"
OUT_DIR.mkdir(exist_ok=True)

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


# ============================================================
# Step 1: 测试 API 连通性
# ============================================================
def test_api():
    print("=" * 60)
    print("Step 1: 测试 NVIDIA NIM API 连通性")
    print("=" * 60)
    url = f"{BASE_URL}/models"
    resp = requests.get(url, headers={"Authorization": f"Bearer {API_KEY}"}, timeout=30)
    print(f"状态码: {resp.status_code}")
    if resp.status_code == 200:
        models = resp.json()
        print(f"可用模型数: {len(models.get('data', []))}")
        for m in models.get('data', [])[:10]:
            print(f"  - {m.get('id', 'N/A')}")
    else:
        print(f"错误: {resp.text[:300]}")
    return resp.status_code == 200


# ============================================================
# Step 2: 读取南山区图像清单
# ============================================================
def load_ns_images():
    print("\n" + "=" * 60)
    print("Step 2: 读取南山区图像清单")
    print("=" * 60)
    rows = []
    with open(NS_MANIFEST, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    print(f"南山区图像: {len(rows)} 张")

    # 按 unique point 分组（4个方向=1个采样点）
    points = {}
    for r in rows:
        key = (r.get("lng", ""), r.get("lat", ""), r.get("township", ""), r.get("year", ""))
        if key not in points:
            points[key] = []
        p = Path(r.get("archive_path", ""))
        if p.exists():
            points[key].append({
                "heading": r.get("heading_label", ""),
                "path": str(p),
                "township": r.get("township", ""),
                "community": r.get("community", ""),
                "urban_form": r.get("urban_form", ""),
                "road_name": r.get("road_name", ""),
                "lng": r.get("lng", ""),
                "lat": r.get("lat", ""),
            })
    print(f"唯一采样点: {len(points)} 个（每个点4个方向）")
    return rows, points


# ============================================================
# Step 3: 编码图像为 base64
# ============================================================
def encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ============================================================
# Step 4: 调用 VLM 做语义分割
# ============================================================
def analyze_image(item, model_id="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"):
    """用 VLM 分析单张图像，返回语义分割结果"""
    img_b64 = encode_image(item["path"])
    img_name = Path(item["path"]).name

    prompt = (
        "You are an expert urban geographer analyzing street view images from Shenzhen, China.\n"
        "Please analyze this panoramic street view image and provide:\n"
        "1. Urban morphology classification (城中村/商品房/老旧小区/新建小区/工业区/商业区/公共设施/其他)\n"
        "2. For the main view, estimate the percentage coverage of:\n"
        "   - Buildings/Structures (建筑): %\n"
        "   - Roads/Pavement (道路): %\n"
        "   - Green space/Vegetation (绿地): %\n"
        "   - Sky (天空): %\n"
        "   - Other (其他): %\n"
        "3. Visual openness (开阔度): 1-10 scale\n"
        "4. Street Canyon effect (街道峡谷效应): 1-10 scale (higher = more enclosed)\n"
        "5. Building density perception (建筑密度感知): 1-10 scale\n"
        "6. Green coverage perception (绿化感知): 1-10 scale\n"
        "7. Overall walkability (步行可达性感知): 1-10 scale\n"
        "8. Brief description in Chinese\n\n"
        "Format your response as JSON:\n"
        "```json\n"
        "{\n"
        '  "urban_form": "分类",\n'
        '  "building_pct": 0-100,\n'
        '  "road_pct": 0-100,\n'
        '  "green_pct": 0-100,\n'
        '  "sky_pct": 0-100,\n'
        '  "other_pct": 0-100,\n'
        '  "openness": 1-10,\n'
        '  "street_canyon": 1-10,\n'
        '  "building_density": 1-10,\n'
        '  "green_perception": 1-10,\n'
        '  "walkability": 1-10,\n'
        '  "description_zh": "中文描述"\n'
        "}\n"
        "```"
    )

    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ],
        "max_tokens": 1024,
        "temperature": 0.1,
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=HEADERS,
            json=payload,
            timeout=120
        )
        if resp.status_code == 200:
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            # 提取 JSON
            import re
            match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
            else:
                data = {"raw_text": content}
            return {
                "status": "success",
                "data": data,
                "model": model_id,
                "usage": result.get("usage", {}),
            }
        else:
            return {
                "status": "error",
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


# ============================================================
# Step 5: 批量处理（多线程并发）
# ============================================================
def batch_process(points, max_workers=4, max_items=None):
    print("\n" + "=" * 60)
    print("Step 3: 批量语义分析")
    print("=" * 60)

    # 展平为单个图像任务
    tasks = []
    for (lng, lat, twp, year), items in points.items():
        for item in items:
            tasks.append({**item, "lng": lng, "lat": lat, "township": twp, "year": year})

    if max_items:
        tasks = tasks[:max_items]
    print(f"待处理任务: {len(tasks)} 张图像")

    results = []
    done = 0
    errors = 0

    def save_partial():
        # 保存中间结果
        out_file = OUT_DIR / "seg_results_partial.csv"
        with open(out_file, "w", encoding="utf-8", newline="") as f:
            if results:
                w = csv.DictWriter(f, fieldnames=results[0].keys())
                w.writeheader()
                w.writerows(results)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(analyze_image, t): t for t in tasks}
        for future in as_completed(futures):
            done += 1
            task = futures[future]
            try:
                res = future.result()
                row = {
                    "path": task["path"],
                    "heading": task["heading"],
                    "township": task["township"],
                    "community": task["community"],
                    "urban_form": task["urban_form"],
                    "lng": task["lng"],
                    "lat": task["lat"],
                    "year": task["year"],
                    "status": res["status"],
                }
                if res["status"] == "success":
                    row.update(res["data"])
                    print(f"[{done}/{len(tasks)}] OK  {Path(task['path']).name[:30]} -> "
                          f"建筑{int(res['data'].get('building_pct', 0))}% "
                          f"道路{int(res['data'].get('road_pct', 0))}% "
                          f"绿地{int(res['data'].get('green_pct', 0))}%")
                else:
                    row["error"] = res.get("error", "")
                    print(f"[{done}/{len(tasks)}] ERR {Path(task['path']).name[:30]}: {res.get('error', '')[:50]}")
                    errors += 1
                results.append(row)
            except Exception as e:
                errors += 1
                print(f"[{done}/{len(tasks)}] EXC {Path(task['path']).name[:30]}: {str(e)[:50]}")
                results.append({
                    "path": task["path"], "heading": task["heading"],
                    "township": task["township"], "lng": task["lng"], "lat": task["lat"],
                    "status": "exception", "error": str(e)
                })

            # 每10个保存一次
            if done % 10 == 0:
                save_partial()

    save_partial()
    print(f"\n完成: {done} | 成功: {done - errors} | 失败: {errors}")
    return results


# ============================================================
# Step 6: 保存完整结果
# ============================================================
def save_results(results):
    print("\n" + "=" * 60)
    print("Step 4: 保存结果")
    print("=" * 60)
    out_file = OUT_DIR / "seg_results_final.csv"
    with open(out_file, "w", encoding="utf-8", newline="") as f:
        if results:
            w = csv.DictWriter(f, fieldnames=results[0].keys())
            w.writeheader()
            w.writerows(results)
    print(f"已保存: {out_file}")
    return out_file


def summarize(results):
    print("\n" + "=" * 60)
    print("分析汇总")
    print("=" * 60)
    ok = [r for r in results if r.get("status") == "success"]
    print(f"成功分析: {len(ok)} 张")

    if ok:
        import statistics
        bld = [r.get("building_pct", 0) for r in ok if r.get("building_pct") is not None]
        rd  = [r.get("road_pct", 0) for r in ok if r.get("road_pct") is not None]
        grn = [r.get("green_pct", 0) for r in ok if r.get("green_pct") is not None]
        sky = [r.get("sky_pct", 0) for r in ok if r.get("sky_pct") is not None]

        def avg(x): return statistics.mean(x) if x else 0
        def rng(x): return f"{min(x):.0f}-{max(x):.0f}" if x else "N/A"

        print(f"\n建筑覆盖率: 平均{avg(bld):.1f}% | 范围{rng(bld)}")
        print(f"道路覆盖率: 平均{avg(rd):.1f}% | 范围{rng(rd)}")
        print(f"绿地覆盖率: 平均{avg(grn):.1f}% | 范围{rng(grn)}")
        print(f"天空占比:   平均{avg(sky):.1f}% | 范围{rng(sky)}")

        from collections import Counter
        forms = Counter(r.get("urban_form", "未知") for r in ok)
        print(f"\n城市形态分布:")
        for k, v in forms.most_common():
            print(f"  {k}: {v} 张")

        # 按街道统计
        from collections import defaultdict
        by_twp = defaultdict(list)
        for r in ok:
            by_twp[r.get("township", "")].append(r.get("building_pct", 0))
        print(f"\n各街道平均建筑覆盖率:")
        for twp, vals in sorted(by_twp.items()):
            if vals:
                print(f"  {twp}: {avg(vals):.1f}%")

    print(f"\n结果文件: {OUT_DIR / 'seg_results_final.csv'}")


# ============================================================
# MAIN
# ============================================================
def main():
    os.environ["HTTP_TIMEOUT"] = "120"
    print("NVIDIA NIM API 语义分割分析")
    print(f"API: {BASE_URL}")
    print(f"Key: {API_KEY[:20]}...")

    # Test
    if not test_api():
        print("API连通失败，请检查API Key和网络")
        return

    # Load
    rows, points = load_ns_images()

    # 先测试1张
    print("\n先测试1张图像...")
    test_tasks = []
    for (lng, lat, twp, year), items in list(points.items())[:1]:
        test_tasks.append({**items[0], "lng": lng, "lat": lat, "township": twp, "year": year})

    test_res = analyze_image(test_tasks[0])
    print(f"\n测试结果:")
    if test_res["status"] == "success":
        import json
        print(json.dumps(test_res["data"], ensure_ascii=False, indent=2))
    else:
        print(test_res.get("error", ""))

    # 确认可以后再批量
    confirm = input("\n测试成功，是否继续批量处理全部图像？(y/n): ")
    if confirm.lower() != 'y':
        print("取消")
        return

    # 批量处理
    results = batch_process(points, max_workers=3)
    save_results(results)
    summarize(results)


if __name__ == "__main__":
    main()
