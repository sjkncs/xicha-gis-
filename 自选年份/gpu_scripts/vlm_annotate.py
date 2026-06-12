#!/usr/bin/env python3
"""
NVIDIA VLM 辅助标注脚本
1. 调用 NVIDIA VLM API 识别街景图像中的障碍物
2. 将 VLM 识别结果叠加到已有的 YOLO+DeepLabV3 标注图上
3. 使用 PIL + 中文字体渲染中文标注
"""
import os, sys, io, json, base64, glob, re
import requests
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

# ==================== NVIDIA API 配置 ====================
NVIDIA_API_KEY = "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"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# ==================== 中文字体 ====================
def get_font(size=20, bold=False):
    """获取可用的中文字体，优先使用系统自带字体"""
    font_paths = [
        # Windows 常用中文字体
        "C:/Windows/Fonts/msyh.ttc",   # 微软雅黑
        "C:/Windows/Fonts/simhei.ttf", # 黑体
        "C:/Windows/Fonts/simsun.ttc", # 宋体
        "C:/Windows/Fonts/simkai.ttf", # 楷体
        "C:/Windows/Fonts/arial.ttf",   # Arial (无中文，回退用)
        # Linux
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/usr/share/fonts/truetype/arphic/ukai.ttc",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()

# ==================== NVIDIA VLM 调用 ====================
def call_nvidia_vlm(image_path, prompt):
    """调用 NVIDIA VLM API（优先 llama-3.2-90b-vision-instruct）"""
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    # 优先使用最强的 VLM 模型
    models_to_try = [
        "meta/llama-3.2-90b-vision-instruct",  # 最强：90B 参数，多模态
        "microsoft/phi-3-vision-128k-instruct",  # 备选：Phi-3 VLM
        "meta/llama-3.2-11b-vision-instruct",   # 备选：11B，轻量
    ]

    payload_template = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                    {"type": "text", "text": prompt}
                ]
            }
        ],
        "max_tokens": 1024,
        "temperature": 0.1,
        "top_p": 0.95,
    }

    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }
    url = f"{NVIDIA_BASE_URL}/chat/completions"

    for model in models_to_try:
        payload = payload_template.copy()
        payload["model"] = model
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"], model
            elif resp.status_code == 400 and "not found" in resp.text.lower():
                continue  # 模型不存在，跳过
            else:
                print(f"      [{model}] HTTP {resp.status_code}: {resp.text[:80]}")
        except Exception as e:
            print(f"      [{model}] Error: {e}")

    raise RuntimeError("All VLM models failed")

# ==================== VLM 障碍物识别 ====================
def detect_obstacles_vlm(image_path):
    """使用 VLM 识别图像中的障碍物，返回结构化结果"""
    prompt = (
        "You are an expert at analyzing urban street view images for pedestrian accessibility. "
        "Your task: Identify ALL obstacles that would block pedestrian movement in this image. "
        "Look carefully for: "
        "1) Vehicles: cars, trucks, buses, motorcycles, bicycles (parked or moving)"
        "2) Street furniture: benches, poles, traffic signs, traffic lights, fire hydrants"
        "3) Urban elements: fences, walls, construction barriers, temporary structures"
        "4) Natural obstacles: trees, large planters, dense vegetation blocking path"
        "5) Other pedestrians/groups of people standing or walking"
        "6) Road conditions: potholes, construction, narrow passages"
        "\n\n"
        "For each obstacle you find, provide: "
        "1) Type (e.g., 'car', 'truck', 'bench', 'tree', 'person_cluster') "
        "2) Position in image: 'left', 'center-left', 'center', 'center-right', 'right', 'foreground', 'background' "
        "3) Severity: 'high' (blocks most of path), 'medium' (partial obstruction), 'low' (edge of path) "
        "4) Description: brief text description "
        "\n\n"
        "Also estimate: "
        "- Overall passability: what percentage (0-100%) of the walking path is unobstructed? "
        "- Key blocking elements: top 3 obstacles most limiting pedestrian access "
        "\n\n"
        "Output format (JSON ONLY, no other text): "
        "{"
        "  'obstacles': ["
        "    {'type': 'car', 'position': 'center-right', 'severity': 'high', 'description': 'white sedan partially blocking sidewalk'},"
        "    ..."
        "  ],"
        "  'passability_estimate': 45,"
        "  'top_blocking': ['white sedan', 'traffic cone cluster', 'bench']"
        "}"
    )

    try:
        content, model_used = call_nvidia_vlm(image_path, prompt)
        # 尝试解析 JSON
        # 去掉 markdown 代码块
        content = re.sub(r"```json\s*", "", content)
        content = re.sub(r"```\s*", "", content)
        result = json.loads(content)
        result["model"] = model_used
        return result
    except Exception as e:
        return {
            "obstacles": [],
            "passability_estimate": None,
            "top_blocking": [],
            "model": None,
            "error": str(e),
            "raw_response": content if "content" in dir() else None
        }

# ==================== 标注叠加函数 ====================
def overlay_vlm_results(orig_image_path, vlm_result, output_path,
                         panel_x_offset=310, font_size=18):
    """
    将 VLM 识别结果叠加到原始标注图上
    - 读取原始图像
    - 在右下角或右上角叠加 VLM 分析结果
    - 使用 PIL 渲染中文文本
    """
    # 读取原图
    img_bgr = cv2.imread(orig_image_path)
    if img_bgr is None:
        print(f"  [WARN] Cannot read: {orig_image_path}")
        return False
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]

    # 转 PIL
    pil_img = Image.fromarray(img_rgb)
    draw = ImageDraw.Draw(pil_img)

    # 字体
    font_normal = get_font(font_size)
    font_small = get_font(font_size - 2)
    font_title = get_font(font_size + 4, bold=True)

    # ==================== VLM 结果面板 ====================
    panel_w = 340
    panel_h = 300
    panel_x = w - panel_w - 5
    panel_y = h - panel_h - 5

    # 半透明背景
    panel_overlay = Image.new("RGBA", pil_img.size, (0, 0, 0, 0))
    panel_draw = ImageDraw.Draw(panel_overlay)
    panel_draw.rectangle([panel_x, panel_y, panel_x + panel_w, panel_y + panel_h],
                          fill=(240, 248, 255, 230), outline=(30, 100, 200, 255), width=2)
    pil_img = Image.alpha_composite(pil_img.convert("RGBA"), panel_overlay)

    # 重新获取 draw（因为 alpha_composite 创建了新图像）
    draw = ImageDraw.Draw(pil_img)

    y = panel_y + 12
    line_h = font_size + 8

    # VLM 标题
    model_name = vlm_result.get("model", "VLM")
    if "/" in str(model_name):
        model_name = str(model_name).split("/")[-1]
    draw.text((panel_x + 8, y), f"[VLM] {model_name}", font=font_title, fill=(20, 80, 180))
    y += line_h + 4

    # 分隔线
    draw.line([(panel_x + 5, y), (panel_x + panel_w - 5, y)], fill=(100, 150, 200), width=1)
    y += 6

    # 通行率估计
    passab = vlm_result.get("passability_estimate")
    if passab is not None:
        # 颜色编码
        if passab >= 70:
            c = (0, 160, 60)
        elif passab >= 40:
            c = (200, 140, 0)
        else:
            c = (200, 0, 0)
        draw.text((panel_x + 8, y), f"VLM通行率: {passab}%", font=font_normal, fill=c)
        y += line_h
    else:
        draw.text((panel_x + 8, y), f"VLM通行率: N/A", font=font_normal, fill=(100, 100, 100))
        y += line_h

    # 障碍物列表
    obstacles = vlm_result.get("obstacles", [])
    draw.text((panel_x + 8, y), f"识别障碍物: {len(obstacles)}个", font=font_normal, fill=(80, 60, 20))
    y += line_h

    draw.line([(panel_x + 5, y), (panel_x + panel_w - 5, y)], fill=(180, 180, 180), width=1)
    y += 6

    # 每个障碍物
    sev_colors = {"high": (220, 0, 0), "medium": (220, 140, 0), "low": (0, 160, 60)}
    for i, obs in enumerate(obstacles[:8]):  # 最多显示8个
        obs_type = obs.get("type", "?")
        severity = obs.get("severity", "?")
        position = obs.get("position", "")
        desc = obs.get("description", "")[:30]
        sev_c = sev_colors.get(severity, (100, 100, 100))
        label = f"#{i+1} {obs_type}"
        if severity:
            sev_icon = {"high": "[!]", "medium": "[~]", "low": "[o]"}.get(severity, "[-]")
            label += f" {sev_icon}"
        draw.text((panel_x + 8, y), label, font=font_small, fill=sev_c)
        y += font_size + 4
        if desc:
            draw.text((panel_x + 16, y), f"  {position} | {desc}", font=font_small, fill=(80, 80, 80))
            y += font_size + 4
        y += 2
        if y > panel_y + panel_h - 20:
            draw.text((panel_x + 8, y), "  ... more obstacles", font=font_small, fill=(120, 120, 120))
            break

    # 转换回 BGR 并保存
    final_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGBA2BGR)
    cv2.imwrite(output_path, final_bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return True


# ==================== 主流程 ====================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="NVIDIA VLM 辅助标注")
    parser.add_argument("--input", "-i", required=True, help="输入图片路径或目录")
    parser.add_argument("--output", "-o", help="输出目录（默认同输入目录）")
    parser.add_argument("--vlm-only", action="store_true", help="只做 VLM 识别，不读取原 YOLO 标注图")
    args = parser.parse_args()

    inp = args.input
    out_dir = args.output or (os.path.dirname(inp) if os.path.isfile(inp) else inp)

    if os.path.isfile(inp):
        files = [inp]
    else:
        files = []
        for ext in ["*.jpg", "*.jpeg", "*.png"]:
            files.extend(glob.glob(os.path.join(inp, ext)))
        files.extend(glob.glob(os.path.join(inp, "**", ext), recursive=True) for ext in ["*.jpg", "*.png"])

    if not files:
        print("No images found!")
        return

    print(f"Found {len(files)} images")
    os.makedirs(out_dir, exist_ok=True)

    results = []
    for i, fpath in enumerate(files, 1):
        fname = os.path.basename(fpath)
        print(f"\n[{i}/{len(files)}] {fname}")
        print(f"  Calling NVIDIA VLM...")
        vlm_result = detect_obstacles_vlm(fpath)

        if "error" in vlm_result:
            print(f"  [ERROR] {vlm_result['error']}")
        else:
            n_obs = len(vlm_result.get("obstacles", []))
            passab = vlm_result.get("passability_estimate")
            model = vlm_result.get("model", "?")
            print(f"  [OK] {model} | obstacles={n_obs} | passability={passab}%")

        # 输出
        out_name = os.path.splitext(fname)[0] + "_vlm_annotated.jpg"
        out_path = os.path.join(out_dir, out_name)
        print(f"  Saving to {out_path}")
        if overlay_vlm_results(fpath, vlm_result, out_path):
            print(f"  [OK] Saved")
        else:
            print(f"  [FAIL]")

        results.append({"file": fpath, "output": out_path, "vlm_result": vlm_result})

    # 保存汇总 JSON
    json_out = os.path.join(out_dir, "vlm_results.json")
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nDone! Results saved to {json_out}")


if __name__ == "__main__":
    main()
