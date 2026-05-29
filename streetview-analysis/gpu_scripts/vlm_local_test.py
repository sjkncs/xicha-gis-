#!/usr/bin/env python3
"""本地 VLM 辅助标注测试脚本"""
import os, sys, json, re, base64, time, glob, shutil
import requests
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"
OUT_DIR = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results\vlm_output"
os.makedirs(OUT_DIR, exist_ok=True)


def get_font(size=18):
    for fp in [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttc",
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/simkai.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()


FONT_CACHE = {s: get_font(s) for s in [10, 11, 12, 14, 16, 20, 24]}


def call_vlm(image_path, prompt):
    """调用 NVIDIA VLM（自动选择可用模型）"""
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    models = [
        "meta/llama-3.2-90b-vision-instruct",
        "microsoft/phi-3-vision-128k-instruct",
        "meta/llama-3.2-11b-vision-instruct",
    ]
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    url = f"{BASE_URL}/chat/completions"

    for model in models:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                {"type": "text", "text": prompt}
            ]}],
            "max_tokens": 512,
            "temperature": 0.1,
        }
        try:
            t0 = time.time()
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            elapsed = time.time() - t0
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                return content, model, elapsed
        except Exception as e:
            print(f"      [{model}] Error: {e}")
    return None, None, None


def parse_vlm(content):
    try:
        content = re.sub(r"```json\s*", "", content)
        content = re.sub(r"```\s*", "", content)
        return json.loads(content)
    except Exception:
        return {"obstacles": [], "passability_estimate": None, "top_blocking": [], "raw": content[:200]}


OBSTACLE_PROMPT = (
    "You are an expert at analyzing urban street view images for pedestrian accessibility. "
    "Identify ALL obstacles that block pedestrian movement in this image. "
    "Look for: vehicles (cars, trucks, buses, motorcycles, bicycles), street furniture (benches, poles, traffic signs, traffic lights, fire hydrants), "
    "fences, walls, construction barriers, dense vegetation, pedestrians, narrow passages. "
    "Output ONLY valid JSON: {\"obstacles\":[{\"type\":\"car\",\"position\":\"center-right\",\"severity\":\"high\",\"description\":\"white sedan\"}],\"passability_estimate\":45,\"top_blocking\":[\"car\"]}"
)


SEV_COLOR = {"high": (220, 0, 0), "medium": (200, 120, 0), "low": (0, 160, 60)}
SEV_ICON = {"high": "!", "medium": "~", "low": "o"}


def overlay_vlm(img_path, vlm_result, out_path):
    """将 VLM 结果叠加到图片上，使用 PIL 中文字体"""
    # 用 PIL 读取（支持中文路径）
    pil_orig = Image.open(img_path).convert("RGB")
    img_rgb = np.array(pil_orig)
    h, w = img_rgb.shape[:2]
    if h == 0 or w == 0:
        return False

    pil_img = Image.fromarray(img_rgb).convert("RGBA")
    draw = ImageDraw.Draw(pil_img)

    # 右侧 VLM 面板
    pw, ph = 320, min(320, h - 10)
    px, py = w - pw - 5, 5
    panel = Image.new("RGBA", (pw, ph), (240, 248, 255, 230))
    pd = ImageDraw.Draw(panel)

    passab = vlm_result.get("passability_estimate")
    if passab is not None:
        if passab >= 70:
            border_color = (0, 160, 60)
        elif passab >= 40:
            border_color = (200, 140, 0)
        else:
            border_color = (200, 0, 0)
    else:
        border_color = (0, 150, 220)

    pd.rectangle([0, 0, pw - 1, ph - 1], outline=(*border_color, 255), width=2)
    y = 8

    def put(txt, fs=12, fc=(30, 30, 30)):
        nonlocal y
        fnt = FONT_CACHE.get(fs, get_font(fs))
        pd.text((8, y), txt, font=fnt, fill=(*fc, 255))
        y += fs + 7

    put("[VLM] 障碍物识别", 14, (20, 80, 180))
    put("-" * 28, 10, (150, 150, 150))
    y += 3

    if passab is not None:
        if passab >= 70:
            pc = (0, 160, 60)
        elif passab >= 40:
            pc = (200, 140, 0)
        else:
            pc = (200, 0, 0)
        put(f"VLM通行率: {passab}%", 14, pc)
    else:
        put("VLM通行率: N/A", 12, (100, 100, 100))

    obstacles = vlm_result.get("obstacles", [])
    put(f"识别障碍物: {len(obstacles)} 个", 12, (80, 60, 20))
    put("-" * 28, 10, (150, 150, 150))
    y += 3

    for i, obs in enumerate(obstacles[:7]):
        obs_type = obs.get("type", "?")
        sev = obs.get("severity", "")
        pos = obs.get("position", "")
        desc = obs.get("description", "")[:25]
        sev_c = SEV_COLOR.get(sev, (100, 100, 100))
        icon = SEV_ICON.get(sev, "-")
        put(f"#{i+1} {obs_type} [{icon}]", 12, sev_c)
        if desc:
            put(f"   {pos} | {desc}", 10, (80, 80, 80))
        y += 2

    top_blocking = vlm_result.get("top_blocking", [])
    if top_blocking:
        y += 3
        blocking_text = "主要阻断: " + ", ".join(str(t)[:15] for t in top_blocking[:3])
        put(blocking_text, 11, (180, 60, 20))

    # 粘贴面板
    pil_img.paste(panel, (px, py), mask=panel)

    # 用 PIL 保存（支持中文路径）
    final_rgb = np.array(pil_img.convert("RGB"))
    pil_out = Image.fromarray(final_rgb)
    pil_out.save(out_path, quality=92)
    return True


def main():
    print("=" * 60)
    print("VLM 辅助标注测试")
    print("=" * 60)

    fig_dir = r"e:\xicha gis 智能定位\papers\conference-slides\会议论文\15min可达性幻觉\overleaf_paper\figures"
    test_imgs = (
        glob.glob(os.path.join(fig_dir, "fig_sim_*.png")) +
        glob.glob(os.path.join(fig_dir, "fig_sim_*.jpg"))
    )
    print(f"找到 {len(test_imgs)} 张测试图片")

    all_imgs = sorted(test_imgs)[:3]
    results = []

    for i, img_path in enumerate(all_imgs, 1):
        fname = os.path.basename(img_path)
        print(f"\n[{i}/{len(all_imgs)}] {fname}")
        print(f"  -> 调用 VLM...")

        content, model, elapsed = call_vlm(img_path, OBSTACLE_PROMPT)
        if content is None:
            print(f"  [FAIL] VLM 调用失败")
            continue

        vlm_result = parse_vlm(content)
        n_obs = len(vlm_result.get("obstacles", []))
        passab = vlm_result.get("passability_estimate", "?")
        print(f"  [OK] {model} ({elapsed:.1f}s)")
        print(f"  障碍物: {n_obs} | 通行率: {passab}%")
        if n_obs > 0:
            for obs in vlm_result["obstacles"][:3]:
                print(f"    - {obs.get('type','?')} [{obs.get('severity','?')}] {obs.get('description','')[:40]}")

        # 叠加标注
        out_name = os.path.splitext(fname)[0] + "_vlm.jpg"
        out_path = os.path.join(OUT_DIR, out_name)
        if overlay_vlm(img_path, vlm_result, out_path):
            print(f"  [OK] 保存: {out_path}")
            results.append({
                "input": img_path,
                "output": out_path,
                "vlm_result": vlm_result,
                "model": model,
                "elapsed_s": round(elapsed, 1)
            })

    json_path = os.path.join(OUT_DIR, "vlm_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n{'=' * 60}")
    print(f"完成! {len(results)} 张图片已处理")
    print(f"结果: {OUT_DIR}")
    print(f"JSON: {json_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
