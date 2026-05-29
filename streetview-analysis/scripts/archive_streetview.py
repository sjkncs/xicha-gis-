"""
标准化街景图片归档脚本
============================
按区域名称 (urban_form) 将百度街景图片归档为标准化目录结构。

目录结构:
  baidu_streetview/
  ├── Village/
  │   ├── 113.9263685_22.5129279/
  │   │   ├── 113.9263685_22.5129279_0_2022.jpg
  │   │   ├── 113.9263685_22.5129279_90_2022.jpg
  │   │   └── ...
  │   └── ...
  ├── High-End/
  ├── High-Rise/
  ├── Mid-Rise/
  ├── Low-Rise/
  ├── Open-Other/
  └── manifest.csv          # 归档清单

使用方法:
  python archive_streetview.py
"""

import os
import shutil
import csv
import math
import io
from pathlib import Path

# ======================== 配置 ========================
SCRIPT_DIR = Path(__file__).parent.resolve()
PICTURE_DIR = SCRIPT_DIR / "picture"              # 下载的原图目录
ARCHIVE_DIR = SCRIPT_DIR / "baidu_streetview"      # 归档目标目录
MANIFEST_PATH = ARCHIVE_DIR / "manifest.csv"

# 项目采样点CSV（包含 urban_form）
PROJECT_SAMPLES = {
    "n201": SCRIPT_DIR.parent / "projects" / "15min-urban-accessibility" / "data" / "streetview" / "integrated_collection" / "samples" / "sample_points_n201.csv",
    "n200": SCRIPT_DIR.parent / "projects" / "15min-urban-accessibility" / "data" / "streetview" / "integrated_collection" / "samples" / "sample_points_n200.csv",
    "n7":   SCRIPT_DIR.parent / "projects" / "15min-urban-accessibility" / "data" / "streetview" / "integrated_collection" / "samples" / "sample_points_n7.csv",
}

# ======================== 坐标容差 ========================
COORD_TOLERANCE = 1e-6  # 经纬度容差（度）


def coord_key(lng: float, lat: float) -> tuple:
    """将经纬度转为整数 key（乘1e7取整），避免浮点精度问题"""
    return (int(round(lng * 1e7)), int(round(lat * 1e7)))


def load_project_points():
    """从项目CSV加载所有采样点，返回 {coord_key: {metadata}}"""
    points = {}
    for name, csv_path in PROJECT_SAMPLES.items():
        if not csv_path.exists():
            continue
        try:
            with open(csv_path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        lng = float(row.get("lng", 0))
                        lat = float(row.get("lat", 0))
                        if lng == 0 and lat == 0:
                            continue
                        key = coord_key(lng, lat)
                        if key not in points:
                            points[key] = {
                                "lng": lng,
                                "lat": lat,
                                "urban_form": normalize_urban_form(row.get("urban_form", "Open/Other")),
                                "road_fclass": row.get("road_fclass", ""),
                                "road_name": row.get("road_name", "").strip(),
                                "source": name,
                                "bld_density": row.get("bld_density_100m", ""),
                                "avg_floors": row.get("avg_floors_100m", ""),
                                "village_nearby": row.get("village_nearby_cnt", ""),
                                "highend_nearby": row.get("highend_nearby_cnt", ""),
                            }
                    except (ValueError, KeyError):
                        continue
        except Exception as e:
            print(f"  警告：无法读取 {csv_path}: {e}")

    print(f"  加载了 {len(points)} 个采样点（来自 n201/n200/n7）")
    return points


def normalize_urban_form(raw: str) -> str:
    """将原始 urban_form 映射为标准化英文目录名"""
    mapping = {
        "Village":       "Village",
        "村庄":           "Village",
        "High-End":       "High-End",
        "高端":           "High-End",
        "Village Fringe": "Village-Fringe",
        "村庄边缘":        "Village-Fringe",
        "High-Rise":      "High-Rise",
        "高密度":          "High-Rise",
        "Mid-Rise":       "Mid-Rise",
        "中密度":          "Mid-Rise",
        "Low-Rise":       "Low-Rise",
        "低密度":          "Low-Rise",
        "Open/Other":     "Open-Other",
        "开放/其他":        "Open-Other",
        "开放":            "Open-Other",
    }
    return mapping.get(raw.strip(), "Open-Other")


def find_point_metadata(lng: float, lat: float, points: dict):
    """根据经纬度（整数 key 精确匹配）查找项目采样点元数据"""
    key = coord_key(lng, lat)
    return points.get(key)


def parse_image_filename(fname: str):
    """从文件名解析元数据。
    格式: {rid}_{lng}_{lat}_{heading}_{year}.jpg
    示例: 1_113.9263685_22.5129279_0_2022.jpg
    """
    name = Path(fname).stem  # 不带扩展名
    parts = name.split("_")
    if len(parts) >= 5:
        try:
            return {
                "rid": parts[0],
                "lng": float(parts[1]),
                "lat": float(parts[2]),
                "heading": int(parts[3]),
                "year": int(parts[4]),
                "ext": Path(fname).suffix,
            }
        except ValueError:
            pass
    return None


def heading_label(h: int) -> str:
    """将方向角转为文字标签"""
    labels = {0: "N", 90: "E", 180: "S", 270: "W"}
    if h % 90 == 0:
        return labels.get(h % 360, str(h))
    return str(h)


def heading_filename(meta: dict) -> str:
    """生成标准化的文件名: {lng}_{lat}_{heading_label}_{year}{ext}"""
    h = meta["heading"]
    hlabel = heading_label(h)
    return f"{meta['lng']}_{meta['lat']}_{hlabel}_{meta['year']}{meta['ext']}"


def heading_to_chinese(h: int) -> str:
    labels = {0: "北", 90: "东", 180: "南", 270: "西"}
    if h % 90 == 0:
        return labels.get(h % 360, str(h))
    return str(h)


def archive_images():
    """主归档流程"""
    print("\n========== 街景图片标准化归档 ==========")

    # Step 1: 加载项目采样点
    print("\n[1/4] 加载项目采样点元数据...")
    points = load_project_points()
    if not points:
        print("  错误：无法加载任何项目采样点！")
        return

    # Step 2: 扫描原图目录
    print("\n[2/4] 扫描下载图片...")
    if not PICTURE_DIR.exists():
        print(f"  错误：图片目录不存在: {PICTURE_DIR}")
        return

    images = []
    for subdir in sorted(PICTURE_DIR.iterdir()):
        if subdir.is_dir():
            for img_file in subdir.iterdir():
                if img_file.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    meta = parse_image_filename(img_file.name)
                    if meta:
                        images.append((img_file, meta))

    print(f"  找到 {len(images)} 张图片")
    if not images:
        return

    # Step 3: 匹配并归档
    print("\n[3/4] 匹配坐标并归档...")
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    # 统计
    stats = {}
    manifest_rows = []
    archived = 0
    unmatched = 0

    for img_path, img_meta in sorted(images, key=lambda x: (x[1]["lng"], x[1]["lat"])):
        pt_meta = find_point_metadata(img_meta["lng"], img_meta["lat"], points)

        if pt_meta:
            urban_form = pt_meta["urban_form"]
            area_dir = ARCHIVE_DIR / urban_form
            os.makedirs(area_dir, exist_ok=True)

            # 建立以坐标命名的子目录
            coord_name = f"{img_meta['lng']}_{img_meta['lat']}"
            sample_dir = area_dir / coord_name
            os.makedirs(sample_dir, exist_ok=True)

            # 标准化文件名
            new_name = heading_filename(img_meta)
            dest_path = sample_dir / new_name

            # 复制文件（避免重复覆盖）
            if not dest_path.exists():
                shutil.copy2(img_path, dest_path)

            # manifest 行
            manifest_rows.append({
                "archive_path": str(dest_path.relative_to(SCRIPT_DIR)),
                "urban_form": urban_form,
                "road_fclass": pt_meta.get("road_fclass", ""),
                "road_name": pt_meta.get("road_name", ""),
                "lng": img_meta["lng"],
                "lat": img_meta["lat"],
                "heading": img_meta["heading"],
                "heading_label": heading_label(img_meta["heading"]),
                "heading_chinese": heading_to_chinese(img_meta["heading"]),
                "year": img_meta["year"],
                "source_file": img_path.name,
                "bld_density": pt_meta.get("bld_density", ""),
                "avg_floors": pt_meta.get("avg_floors", ""),
                "village_nearby": pt_meta.get("village_nearby", ""),
                "highend_nearby": pt_meta.get("highend_nearby", ""),
                "sample_source": pt_meta.get("source", ""),
            })

            # 统计
            stats[urban_form] = stats.get(urban_form, 0) + 1
            archived += 1
            print(f"  [{urban_form:16s}] {coord_name} 方向={img_meta['heading']} ({heading_label(img_meta['heading'])})  ->  {new_name}")
        else:
            print(f"  [未匹配] {img_path.name}  (lng={img_meta['lng']}, lat={img_meta['lat']})")
            unmatched += 1

    # Step 4: 写入 manifest.csv
    print(f"\n[4/4] 写入归档清单 manifest.csv...")
    fieldnames = [
        "archive_path", "urban_form", "road_fclass", "road_name",
        "lng", "lat", "heading", "heading_label", "heading_chinese",
        "year", "source_file",
        "bld_density", "avg_floors", "village_nearby", "highend_nearby",
        "sample_source",
    ]
    with open(MANIFEST_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    # 输出汇总
    print(f"\n========== 归档完成 ==========")
    print(f"  归档图片: {archived} 张")
    print(f"  未匹配坐标: {unmatched} 张")
    print(f"  manifest: {MANIFEST_PATH}")
    print(f"\n  各区域统计:")
    for form, count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"    {form:20s}: {count} 张")

    # 打印目录树（只显示顶层）
    print(f"\n  归档目录结构:")
    for subdir in sorted(ARCHIVE_DIR.iterdir()):
        if subdir.is_dir():
            n_images = sum(1 for f in subdir.rglob("*") if f.is_file())
            n_samples = sum(1 for d in subdir.iterdir() if d.is_dir())
            print(f"    {subdir.name}/ ({n_samples} 采样点, {n_images} 张图)")


if __name__ == "__main__":
    archive_images()
