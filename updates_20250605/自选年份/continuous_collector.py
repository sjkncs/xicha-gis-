# -*- coding: utf-8 -*-
"""
==============================================================================
南山区连续街景采集管线
Continuous Street View Collection Pipeline for Nanshan 3DGS Reconstruction

复用 full_pipeline.py 的坐标转换、API 调用、归档逻辑，
但以连续轨迹为输入，实现批量高速采集

用法:
    # 方式1：直接采集连续轨迹（需要先运行 trajectory_sampler.py 生成 CSV）
    python continuous_collector.py --input trajectory_output/trajectory_10m.csv --max-images 100

    # 方式2：沿特定道路段采集
    python continuous_collector.py --input trajectory_output/scipark_5m.csv --max-images 500 --spacing 5

    # 方式3：批量+断点续传（生产模式）
    python continuous_collector.py --input trajectory_output/trajectory_10m.csv --max-images 0 --batch 500

依赖:
    - requests, Pillow (已在 full_pipeline.py 中使用)
    - numpy, pandas (轨迹处理)
==============================================================================
"""

import os
import sys
import csv
import json
import time
import random
import math
import logging
import argparse
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# ============================================================
# 复用 full_pipeline.py 的核心模块
# ============================================================
# 直接 import，避免重复代码
sys.path.insert(0, str(Path(__file__).parent))
from full_pipeline import (
    wgs84_to_bdmc,
    wgs84_to_gcj02,
    amap_regeocode,
    bd_sid,
    sid_timeline,
    make_archive_path,
    ARCHIVE_DIR as BASE_ARCHIVE_DIR,
    TARGET_YEARS,
    DIRECTIONS,
    HEADING_LABELS,
    UA_LIST,
    CACHE_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ============================================================
# 全局状态（断点续传）
# ============================================================
lock = Lock()
checkpoint_file = CACHE_DIR / "continuous_collector_checkpoint.json"
stats_lock = {
    "total": 0,
    "success": 0,
    "failed": 0,
    "skipped": 0,
}


# ============================================================
# 轨迹 CSV 格式说明
# ============================================================
# 输入 CSV 应包含列: pt_id, lon, lat, heading, heading_label, fclass, building_density
# 如果没有 heading，则自动从行进方向推断
#
# 输出归档格式（与 full_pipeline.py 一致）:
#   baidu_streetview/
#     南山区/蛇口/xxx/113.xxx_22.xxx/
#       113.xxx_22.xxx_N_2022.jpg
#       113.xxx_22.xxx_E_2022.jpg
#       113.xxx_22.xxx_S_2022.jpg
#       113.xxx_22.xxx_W_2022.jpg

def _headers():
    return {
        "User-Agent": random.choice(UA_LIST),
        "Referer": "https://map.baidu.com/",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }


def _date_str():
    return time.strftime("%Y%m%d", time.localtime())


def bd_sid_from_wgs84(lng, lat):
    """WGS84 -> BD墨卡托 -> SID"""
    bd_x, bd_y = wgs84_to_bdmc(lng, lat)
    params = {
        "udt": _date_str(), "action": 0,
        "x": bd_x, "y": bd_y,
        "l": 18.367179030452565,
        "mode": "day",
        "t": int(time.time() * 1000),
        "fn": "jsonp1", "qt": "qsdata",
    }
    try:
        import requests
        r = requests.get("https://mapsv0.bdimg.com/?", params=params, headers=_headers(), timeout=(5, 10))
        raw = r.content
        start = raw.find(b"(") + 1
        end = raw.rfind(b")")
        if start > 0 and end > start:
            j = json.loads(raw[start:end].decode("utf-8", errors="replace"))
            if j.get("result", {}).get("error") == 0:
                return j["content"]["id"]
    except Exception:
        pass
    return None


def get_timeline_for_sid(sid):
    """获取全景时间轴"""
    params = {
        "sid": sid, "pc": 1,
        "udt": _date_str(),
        "fn": "jsonp.p3991630", "qt": "sdata",
    }
    try:
        import requests
        r = requests.get("https://mapsv0.bdimg.com/?", params=params, headers=_headers(), timeout=(3, 7))
        raw = r.content
        start = raw.find(b"(") + 1
        end = raw.rfind(b")")
        if start > 0 and end > start:
            j = json.loads(raw[start:end].decode("utf-8", errors="replace"))
            content = j.get("content", [])
            if content and isinstance(content, list):
                timeline = content[0].get("TimeLine", [])
                return timeline
    except Exception:
        pass
    return []


def download_image(sid, heading, year, lng, lat):
    """下载单张街景图"""
    params = {
        "sid": sid,
        "pc": 1,
        "udt": _date_str(),
        "width": 1024,
        "height": 512,
        "fov": 100,
        "heading": heading,
        "pitch": 0,
        "mode": "day",
    }
    try:
        import requests
        r = requests.get("https://mapsv0.bdimg.com/?", params=params, headers=_headers(), timeout=(15, 30))
        if r.status_code == 200 and len(r.content) > 5000:
            return r.content
    except Exception:
        pass
    return None


def estimate_heading_from_trajectory(lon, lat, prev_lon, prev_lat, next_lon, next_lat):
    """从轨迹行进方向估算朝向"""
    bearing = None

    if prev_lon is not None and next_lon is not None:
        # 计算从上一个点到下一个点的方位角
        phi1, phi2 = math.radians(prev_lat), math.radians(next_lat)
        dlambda = math.radians(next_lon - prev_lon)
        x = math.sin(dlambda) * math.cos(phi2)
        y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
        bearing = (math.degrees(math.atan2(x, y)) + 360) % 360
    elif next_lon is not None:
        phi1, phi2 = math.radians(lat), math.radians(next_lat)
        dlambda = math.radians(next_lon - lon)
        x = math.sin(dlambda) * math.cos(phi2)
        y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
        bearing = (math.degrees(math.atan2(x, y)) + 360) % 360

    # 映射到四方向
    if bearing is not None:
        if 315 <= bearing or bearing < 45:
            return 0, "N"
        elif 45 <= bearing < 135:
            return 90, "E"
        elif 135 <= bearing < 225:
            return 180, "S"
        else:
            return 270, "W"
    return 0, "N"


# ============================================================
# 采集单个轨迹点
# ============================================================
def collect_one_point(row, urban_form_override=None, heading_override=None, max_year_attempts=4):
    """
    采集一个轨迹点的街景图
    row: CSV 行字典
    返回: (success, message)
    """
    global stats_lock

    lng = float(row["lon"])
    lat = float(row["lat"])
    pt_id = row.get("pt_id", f"{lng:.6f}_{lat:.6f}")

    # 归档路径
    archive_sub = f"连续采集/{pt_id}"
    archive_base = BASE_ARCHIVE_DIR / archive_sub
    os.makedirs(archive_base, exist_ok=True)

    # 检查是否已有完整数据
    existing = list(archive_base.glob("*.jpg"))
    if len(existing) >= 4:
        with lock:
            stats_lock["skipped"] += 1
        return True, "已有完整数据"

    # 连续采集模式下，每个点只采1张（朝向前进方向），减少存储
    if heading_override is not None:
        headings_to_collect = [heading_override]
    else:
        headings_to_collect = [0, 90, 180, 270]  # 全方向

    # 获取 SID
    sid = bd_sid_from_wgs84(lng, lat)
    if not sid:
        with lock:
            stats_lock["failed"] += 1
        return False, "无SID"

    # 获取时间轴
    timeline = get_timeline_for_sid(sid)

    # 找年份
    timeid = None
    chosen_year = None
    for year in TARGET_YEARS[:max_year_attempts]:
        for item in timeline:
            if int(item.get("Year", 0)) == year:
                timeid = item.get("ID")
                chosen_year = year
                break
        if timeid:
            break

    if not timeid:
        with lock:
            stats_lock["failed"] += 1
        return False, "无时间轴"

    # 下载图像
    success_count = 0
    for heading in headings_to_collect:
        heading_label = HEADING_LABELS.get(heading, "N")
        filename = f"{lng:.6f}_{lat:.6f}_{heading_label}_{chosen_year}.jpg"
        out_path = archive_base / filename

        # 已有则跳过
        if out_path.exists() and out_path.stat().st_size > 10000:
            success_count += 1
            continue

        img_data = download_image(sid, heading, chosen_year, lng, lat)
        if img_data and len(img_data) > 5000:
            with open(out_path, "wb") as f:
                f.write(img_data)
            success_count += 1
            time.sleep(random.uniform(0.3, 0.8))
        else:
            with lock:
                stats_lock["failed"] += 1

    with lock:
        if success_count > 0:
            stats_lock["success"] += 1
        else:
            stats_lock["failed"] += 1

    return success_count > 0, f"成功{success_count}/{len(headings_to_collect)}张"


# ============================================================
# 批量采集
# ============================================================
def collect_batch(points_df, max_images=0, max_workers=3, delay=0.5):
    """
    批量采集街景图
    points_df: DataFrame，含 lon, lat, pt_id 等列
    max_images: 最大采集数量（0=不限制）
    max_workers: 并发线程数
    """
    global stats_lock

    log.info(f"开始批量采集: {len(points_df):,} 个点, 并发={max_workers}")

    # 加载断点
    completed = set()
    if checkpoint_file.exists():
        try:
            with open(checkpoint_file, encoding="utf-8") as f:
                cp = json.load(f)
                completed = set(cp.get("completed", []))
            log.info(f"  断点续传: {len(completed):,} 个点已完成")
        except Exception:
            pass

    # 过滤已完成
    if "pt_id" in points_df.columns:
        points_df = points_df[~points_df["pt_id"].astype(str).isin(completed)]

    if max_images > 0:
        points_df = points_df.head(max_images)

    total = len(points_df)
    log.info(f"  待采集: {total:,} 个点")

    stats_lock["total"] = total

    results = []
    start_time = time.time()

    def process_row(row_dict):
        row_dict = {k: (v if pd.notna(v) else None) for k, v in row_dict.items()}
        return collect_one_point(row_dict)

    # 线程池采集
    import pandas as pd

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for _, row in points_df.iterrows():
            row_dict = row.to_dict()
            pt_id = row_dict.get("pt_id", f"{row_dict['lon']:.6f}_{row_dict['lat']:.6f}")
            heading_override = None
            if "heading" in row_dict and pd.notna(row_dict.get("heading")):
                try:
                    heading_override = int(row_dict["heading"])
                except (ValueError, TypeError):
                    pass

            future = executor.submit(collect_one_point, row_dict, None, heading_override)
            futures[future] = pt_id

        for i, future in enumerate(as_completed(futures)):
            pt_id = futures[future]
            try:
                success, msg = future.result()
                results.append((pt_id, success, msg))
            except Exception as e:
                results.append((pt_id, False, str(e)))

            # 进度报告
            done = i + 1
            if done % 50 == 0 or done == total:
                elapsed = time.time() - start_time
                rate = done / elapsed if elapsed > 0 else 0
                remaining = (total - done) / rate if rate > 0 else 0

                with lock:
                    s = stats_lock["success"]
                    f = stats_lock["failed"]
                    sk = stats_lock["skipped"]

                log.info(
                    f"  进度: {done:,}/{total:,} "
                    f"({done/total*100:.1f}%) | "
                    f"成功:{s} 失败:{f} 跳过:{sk} | "
                    f"速度:{rate:.1f}点/s | "
                    f"剩余:~{remaining/60:.0f}min"
                )

                # 保存断点
                with lock:
                    completed_list = list(completed) + [r[0] for r in results]
                with open(checkpoint_file, "w", encoding="utf-8") as f:
                    json.dump({"completed": completed_list, "timestamp": datetime.now().isoformat()}, f)


def parse_trajectory_csv(csv_path):
    """解析轨迹 CSV，返回 DataFrame"""
    log.info(f"加载轨迹文件: {csv_path}")
    import pandas as pd

    df = pd.read_csv(csv_path)
    required = ["lon", "lat"]
    for col in required:
        if col not in df.columns:
            log.error(f"轨迹CSV缺少必需列: {col}")
            return None

    log.info(f"  加载: {len(df):,} 个点")
    if "pt_id" not in df.columns:
        df["pt_id"] = df.apply(lambda r: f"{r['lon']:.6f}_{r['lat']:.6f}", axis=1)

    return df


def generate_view_sequence(df, output_path, sequence_length=5):
    """
    为连续采集生成序列视图展开
    将连续轨迹点展开为序列（用于 3DGS SfM）

    每个序列 = 5-10 个连续点，每个点 4 方向
    存储为：sequence_id, pt_id, lon, lat, heading, heading_label, frame_in_seq
    """
    log.info(f"生成序列视图展开...")

    sequences = []
    n = len(df)
    seq_id = 0

    for i in range(n):
        for j in range(sequence_length):
            idx = i + j
            if idx >= n:
                break

            row = df.iloc[idx]
            for heading, label in [(0, "N"), (90, "E"), (180, "S"), (270, "W")]:
                sequences.append({
                    "seq_id": seq_id,
                    "pt_id": row.get("pt_id", f"{row['lon']:.6f}_{row['lat']:.6f}"),
                    "lon": row["lon"],
                    "lat": row["lat"],
                    "heading": heading,
                    "heading_label": label,
                    "frame_in_seq": j,
                    "fclass": row.get("fclass", ""),
                    "building_density": row.get("building_density", ""),
                })

            seq_id += 1

    import pandas as pd
    seq_df = pd.DataFrame(sequences)
    out_path = Path(csv_path).parent / output_path
    seq_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    log.info(f"  序列文件: {out_path} ({len(seq_df):,} 行)")

    return seq_df


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="连续街景采集管线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 采集100张测试
  python continuous_collector.py --input trajectory_output/trajectory_10m.csv --max-images 100

  # 全量采集（断点续传）
  python continuous_collector.py --input trajectory_output/scipark_5m.csv --max-images 0

  # 仅主方向（减少存储）
  python continuous_collector.py --input trajectory_output/trajectory_10m.csv --max-images 200 --single-heading

  # 从已有采样点列表采集（复用 manifest 格式）
  python continuous_collector.py --input baidu_streetview/ns_manifest.csv --manifest-mode
""",
    )
    parser.add_argument("--input", type=str, required=True, help="轨迹 CSV 路径")
    parser.add_argument("--max-images", type=int, default=100, help="最大采集数量（0=全部）")
    parser.add_argument("--max-workers", type=int, default=3, help="并发线程数")
    parser.add_argument("--delay", type=float, default=0.5, help="请求间隔（秒）")
    parser.add_argument("--single-heading", action="store_true", help="每个点只采1个方向（省存储）")
    parser.add_argument("--manifest-mode", action="store_true", help="输入为 manifest CSV 格式")
    parser.add_argument("--seq-length", type=int, default=5, help="连续序列长度（用于3DGS）")
    parser.add_argument("--output-seq", type=str, default="sequence_viewpoints.csv", help="序列输出文件名")

    args = parser.parse_args()

    if not Path(args.input).exists():
        log.error(f"输入文件不存在: {args.input}")
        return

    # 解析输入
    df = parse_trajectory_csv(args.input)
    if df is None:
        return

    if args.manifest_mode:
        # manifest 格式特殊解析
        log.info("使用 manifest 模式（复用 full_pipeline.py 归档结构）")
        # 已在 parse_trajectory_csv 中处理

    # 序列视图生成
    if args.seq_length > 0:
        generate_view_sequence(df, args.output_seq, sequence_length=args.seq_length)

    # 批量采集
    collect_batch(df, max_images=args.max_images, max_workers=args.max_workers, delay=args.delay)

    elapsed = time.time() - stats_lock.get("_start_time", time.time()) if "_start_time" in dir() else 0
    log.info("\n" + "=" * 50)
    log.info(f"采集完成！")
    log.info(f"  成功: {stats_lock['success']}")
    log.info(f"  失败: {stats_lock['failed']}")
    log.info(f"  跳过: {stats_lock['skipped']}")
    log.info(f"  输出目录: {BASE_ARCHIVE_DIR}")
    log.info("=" * 50)


if __name__ == "__main__":
    main()
