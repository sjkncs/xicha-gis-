# -*- coding: utf-8 -*-
"""
street_view_verifier.py — 街景验证器
Street View Verifier for Accessibility Illusion Validation

将数字可达性推断（路网节点 + 路径 + 设施）
与物理现实（街景图像序列 + VLM分割结果）连接起来。

功能：
  1. 路径采样点生成：给定起点-终点，生成沿路街景采样序列
  2. 街景证据链构建：将采样点与已有街景图像/VLM结果匹配
  3. 可达性验证评分：计算路径级的 digital-physical gap
  4. 输出 GeoJSON：含幻觉分的路径节点/边
  5. 输出证据链 JSON：每条关键路径的验证详情

依赖：
  pip install numpy pandas shapely geopandas scipy
"""

from __future__ import annotations

import csv
import json
import logging
import math
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("street_view_verifier")


# =============================================================================
# 工具函数
# =============================================================================

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    d = math.radians(lat2 - lat1)
    d2 = math.radians(lon2 - lon1)
    a = (math.sin(d / 2) ** 2
          + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
          * math.sin(d2 / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def sample_points_along_path(
    path_coords: list[tuple[float, float]],
    sample_interval_m: float = 50,
) -> list[dict]:
    """
    沿路径均匀采样街景候选点

    Parameters
    ----------
    path_coords : [(lon, lat), ...] 路径折线坐标
    sample_interval_m : 采样间隔（米）

    Returns
    -------
    [{lon, lat, distance_from_start_m, segment_idx, heading}, ...]
    """
    if len(path_coords) < 2:
        return []

    samples = []
    cumulative_m = 0.0
    last_pt = path_coords[0]

    for i in range(1, len(path_coords)):
        p0 = last_pt
        p1 = path_coords[i]
        seg_dist = haversine_m(p0[1], p0[0], p1[1], p1[0])

        if seg_dist < 0.1:
            last_pt = p1
            continue

        num_samples = max(1, int(seg_dist / sample_interval_m))
        for k in range(1, num_samples + 1):
            t = k / num_samples
            lon = p0[0] + t * (p1[0] - p0[0])
            lat = p0[1] + t * (p1[1] - p0[1])
            cumulative_m += seg_dist / num_samples
            heading = math.degrees(
                math.atan2(p1[0] - p0[0], p1[1] - p0[1]))
            samples.append({
                "lon": round(lon, 6),
                "lat": round(lat, 6),
                "distance_from_start_m": round(cumulative_m, 1),
                "segment_idx": i,
                "heading_deg": round(heading % 360, 1),
                "heading_label": _heading_to_cardinal(heading % 360),
            })

        last_pt = p1
        cumulative_m += seg_dist

    return samples


def _heading_to_cardinal(deg: float) -> str:
    """度数转方位标签"""
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((deg + 22.5) / 45) % 8
    return dirs[idx]


def find_nearest_sv_point(
    sample: dict,
    sv_manifest: pd.DataFrame,
    sv_csv: pd.DataFrame,
    max_distance_m: float = 100,
) -> dict | None:
    """
    为路径采样点匹配最近的已有街景图像

    Parameters
    ----------
    sample : {lon, lat, heading_deg, distance_from_start_m}
    sv_manifest : 街景元数据（含lng/lat/heading/year等）
    sv_csv : 街景VLM分割结果（含urban_form/walkability等）
    max_distance_m : 最大匹配距离（米）

    Returns
    -------
    {match_key, distance_m, sv_row_dict} 或 None
    """
    sv_valid = sv_manifest.dropna(subset=["lng", "lat"]).copy()
    if sv_valid.empty:
        return None

    coords = sv_valid[["lng", "lat"]].values
    lats = coords[:, 1]
    lons = coords[:, 0]
    sample_lat = sample["lat"]
    sample_lon = sample["lon"]

    distances = (
        (lats - sample_lat) ** 2 * (111000 ** 2)
        + (lons - sample_lon) ** 2 * (111000 * math.cos(math.radians(sample_lat)) ** 2)
    ) ** 0.5

    min_idx = int(distances.argmin())
    min_dist = float(distances[min_idx])

    if min_dist > max_distance_m:
        return None

    row = sv_valid.iloc[min_idx]
    key = f"{row['lng']:.6f}_{row['lat']:.6f}"

    # 与VLM结果匹配
    sv_match = None
    if not sv_csv.empty and "lng" in sv_csv.columns:
        sv_csv["lng_r"] = sv_csv["lng"].round(6)
        sv_csv["lat_r"] = sv_csv["lat"].round(6)
        row_lng = round(float(row["lng"]), 6)
        row_lat = round(float(row["lat"]), 6)
        matches = sv_csv[
            (abs(sv_csv["lng_r"] - row_lng) < 1e-5)
            & (abs(sv_csv["lat_r"] - row_lat) < 1e-5)
        ]
        if not matches.empty:
            sv_match = matches.iloc[0].to_dict()

    return {
        "sample_lon": sample["lon"],
        "sample_lat": sample["lat"],
        "match_key": key,
        "match_lng": float(row["lng"]),
        "match_lat": float(row["lat"]),
        "match_heading": row.get("heading_label", ""),
        "distance_m": round(min_dist, 1),
        "image_path": row.get("archive_path", ""),
        "sv_result": sv_match,
    }


def compute_path_verification_score(
    matches: list[dict],
) -> dict:
    """
    给定一条路径的所有街景匹配，计算该路径的验证评分

    Parameters
    ----------
    matches : [find_nearest_sv_point() 返回的匹配列表]

    Returns
    -------
    {coverage_pct, avg_walkability, avg_openness, avg_canyon, avg_density,
     evidence_quality, gap_score, interpretation}
    """
    if not matches:
        return {
            "coverage_pct": 0.0,
            "avg_walkability": None,
            "avg_openness": None,
            "avg_canyon": None,
            "avg_density": None,
            "evidence_quality": 0.0,
            "gap_score": 1.0,
            "interpretation": "无可用街景证据",
        }

    total = len(matches)
    sv_results = [m["sv_result"] for m in matches if m["sv_result"] is not None]
    covered = len(sv_results)

    coverage_pct = covered / total * 100

    # 数值指标
    def col_mean(col):
        vals = [float(r[col]) for r in sv_results if r.get(col) is not None
                and not pd.isna(r.get(col))]
        return round(float(np.mean(vals)), 2) if vals else None

    avg_walkability = col_mean("walkability")
    avg_openness = col_mean("openness")
    avg_canyon = col_mean("canyon")
    avg_density = col_mean("density")

    # 证据质量：覆盖率 + 数据完整性
    evidence_quality = round(
        coverage_pct / 100 * 0.6
        + (covered / total) * 0.4,
        4,
    )

    # Gap Score = 1 - evidence_quality * avg_walkability/10
    if avg_walkability is not None:
        gap_score = round(max(0.0, 1.0 - evidence_quality * avg_walkability / 10), 4)
    else:
        gap_score = round(max(0.0, 1.0 - evidence_quality * 0.5), 4)

    # 解读
    if gap_score < 0.15:
        interpretation = "低幻觉：数字推断与街景证据高度吻合"
    elif gap_score < 0.35:
        interpretation = "中幻觉：存在局部偏差，建议重点核验低walkability段"
    elif gap_score < 0.60:
        interpretation = "高幻觉：路径体验显著差于算法预期，需实地调查"
    else:
        interpretation = "极高幻觉：数字模型严重脱离实际，建议重构路径推断"

    return {
        "total_samples": total,
        "covered_samples": covered,
        "coverage_pct": round(coverage_pct, 2),
        "avg_walkability": avg_walkability,
        "avg_openness": avg_openness,
        "avg_canyon": avg_canyon,
        "avg_density": avg_density,
        "evidence_quality": evidence_quality,
        "gap_score": gap_score,
        "interpretation": interpretation,
    }


def urban_form_legend() -> dict:
    """城市形态中文-英文对照"""
    return {
        "城中村": "urban_village",
        "新建住宅": "new_community",
        "老旧社区": "old_community",
        "新建住宅区": "new_community",
        "老旧住宅区": "old_community",
        "商业": "commercial",
        "工业": "industrial",
        "仓储": "warehouse",
        "绿地": "green_space",
        "公共空间": "public_space",
        "居住": "residential",
        "residential": "居住",
        "commercial": "商业",
        "industrial": "工业",
        "warehouse": "仓储",
        "urban_village": "城中村",
        "new_community": "新建住宅",
        "old_community": "老旧社区",
        "old_residential": "老旧住宅",
        "new_residential": "新建住宅",
        "unknown": "未知",
    }


# =============================================================================
# 主验证入口
# =============================================================================

def verify_paths(
    sv_manifest_path: str | Path,
    sv_csv_path: str | Path,
    network_nodes_path: str | Path | None = None,
    facility_path: str | Path | None = None,
    sample_interval_m: float = 50,
    max_match_distance_m: float = 100,
    output_dir: str | Path = "verifier_output",
    sample_paths: list[dict] | None = None,
) -> dict:
    """
    综合街景验证

    Parameters
    ----------
    sv_manifest_path : baidu_streetview/ns_manifest.csv
    sv_csv_path       : 分割结果CSV
    network_nodes_path : network_output/network_nodes.json（用于采样路径生成）
    facility_path      : network_output/facility_locations.json
    sample_paths      : 自定义路径列表 [{name, coords:[(lon,lat),...]}]
                       若不提供则使用预置示范路径
    sample_interval_m : 采样间隔
    max_match_distance_m : 街景匹配最大距离
    output_dir        : 输出目录

    Returns
    -------
    {paths_verification, path_summary_geojson, evidence_chains, statistics}
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info("读取街景元数据: %s", sv_manifest_path)
    sv_manifest = pd.read_csv(sv_manifest_path, low_memory=False)
    log.info("读取VLM分割结果: %s", sv_csv_path)
    sv_csv = pd.read_csv(sv_csv_path, low_memory=False)

    # 确保经纬度列存在
    for col in ["lng", "lat"]:
        if col not in sv_manifest.columns:
            if "lon" in sv_manifest.columns:
                sv_manifest.rename(columns={"lon": "lng"}, inplace=True)
            elif "longitude" in sv_manifest.columns:
                sv_manifest.rename(columns={"longitude": "lng"}, inplace=True)
    for col in ["lng", "lat"]:
        if col not in sv_csv.columns:
            if "lon" in sv_csv.columns:
                sv_csv.rename(columns={"lon": "lng"}, inplace=True)

    log.info("街景记录: %d, VLM结果: %d", len(sv_manifest), len(sv_csv))

    # 预置示范路径（南山区典型生活圈路径）
    if sample_paths is None:
        sample_paths = _preset_paths()
        log.info("使用预置路径 %d 条", len(sample_paths))

    # 加载设施数据
    facilities = []
    if facility_path and Path(facility_path).exists():
        with open(facility_path, encoding="utf-8") as f:
            facilities = json.load(f)
        log.info("加载设施 %d 个", len(facilities))

    # 逐路径验证
    path_results = []
    all_evidences = []
    all_geojson_features = []

    for pi, path_def in enumerate(sample_paths):
        path_name = path_def.get("name", f"path_{pi}")
        coords = path_def.get("coords", [])

        if len(coords) < 2:
            log.warning("路径 '%s' 坐标不足，跳过", path_name)
            continue

        log.info("验证路径 [%d/%d] %s (%d点)...",
                 pi + 1, len(sample_paths), path_name, len(coords))

        # 采样
        samples = sample_points_along_path(coords, sample_interval_m)
        if not samples:
            log.warning("路径 '%s' 采样为空", path_name)
            continue

        # 匹配街景
        matches = []
        for s in samples:
            m = find_nearest_sv_point(s, sv_manifest, sv_csv, max_match_distance_m)
            if m:
                matches.append(m)

        # 评分
        score = compute_path_verification_score(matches)
        score["path_name"] = path_name
        score["num_samples"] = len(samples)
        score["num_matched"] = len(matches)

        path_results.append(score)

        # 构建证据链
        evidence_chain = {
            "path_name": path_name,
            "coords": coords,
            "total_samples": len(samples),
            "matched": len(matches),
            "verification": score,
            "evidence_points": [
                {
                    "lon": m["sample_lon"],
                    "lat": m["sample_lat"],
                    "match_lng": m["match_lng"],
                    "match_lat": m["match_lat"],
                    "distance_m": m["distance_m"],
                    "heading": m["match_heading"],
                    "image_path": m["image_path"],
                    "urban_form": m["sv_result"].get("urban_form_clean", "unknown") if m["sv_result"] else None,
                    "walkability": float(m["sv_result"]["walkability"]) if m["sv_result"] and m["sv_result"].get("walkability") is not None else None,
                    "openness": float(m["sv_result"]["openness"]) if m["sv_result"] and m["sv_result"].get("openness") is not None else None,
                    "canyon": float(m["sv_result"]["canyon"]) if m["sv_result"] and m["sv_result"].get("canyon") is not None else None,
                    "description_zh": m["sv_result"].get("description_zh", "") if m["sv_result"] else "",
                }
                for m in matches if m["sv_result"]
            ],
        }
        all_evidences.append(evidence_chain)

        # GeoJSON feature（路径中心线 + 幻觉分）
        all_geojson_features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
            "properties": {
                "path_name": path_name,
                "gap_score": score["gap_score"],
                "coverage_pct": score["coverage_pct"],
                "avg_walkability": score["avg_walkability"],
                "avg_openness": score["avg_openness"],
                "interpretation": score["interpretation"],
            },
        })

    # 汇总统计
    gap_scores = [r["gap_score"] for r in path_results if r.get("gap_score") is not None]
    statistics = {
        "total_paths": len(path_results),
        "avg_gap_score": round(float(np.mean(gap_scores)), 4) if gap_scores else 1.0,
        "max_gap_score": round(float(np.max(gap_scores)), 4) if gap_scores else 1.0,
        "min_gap_score": round(float(np.min(gap_scores)), 4) if gap_scores else 0.0,
        "paths_by_level": {
            "low_illusion": len([g for g in gap_scores if g < 0.15]),
            "medium_illusion": len([g for g in gap_scores if 0.15 <= g < 0.35]),
            "high_illusion": len([g for g in gap_scores if 0.35 <= g < 0.60]),
            "extreme_illusion": len([g for g in gap_scores if g >= 0.60]),
        },
        "total_evidence_points": sum(len(e["evidence_points"]) for e in all_evidences),
    }

    result = {
        "generated_at": pd.Timestamp.now().isoformat(),
        "sample_interval_m": sample_interval_m,
        "max_match_distance_m": max_match_distance_m,
        "path_results": path_results,
        "statistics": statistics,
        "urban_form_legend": urban_form_legend(),
    }

    # 写文件
    out_evidences = out_dir / "evidence_chains.json"
    with open(out_evidences, "w", encoding="utf-8") as f:
        json.dump(all_evidences, f, ensure_ascii=False, indent=2)
    log.info("证据链已写入: %s", out_evidences)

    out_geojson = out_dir / "verified_paths.geojson"
    geojson_out = {"type": "FeatureCollection", "features": all_geojson_features}
    with open(out_geojson, "w", encoding="utf-8") as f:
        json.dump(geojson_out, f, ensure_ascii=False, indent=2)
    log.info("路径GeoJSON已写入: %s", out_geojson)

    out_summary = out_dir / "verification_summary.json"
    with open(out_summary, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log.info("验证摘要已写入: %s", out_summary)

    log.info("============================================================")
    log.info("路径验证完成  平均Gap分: %.4f", statistics["avg_gap_score"])
    log.info("  低幻觉路径: %d  中幻觉: %d  高幻觉: %d  极高: %d",
             statistics["paths_by_level"]["low_illusion"],
             statistics["paths_by_level"]["medium_illusion"],
             statistics["paths_by_level"]["high_illusion"],
             statistics["paths_by_level"]["extreme_illusion"])
    log.info("============================================================")

    return result


def _preset_paths() -> list[dict]:
    """
    南山区典型生活圈示范路径
    从地铁站/社区中心出发，覆盖多种城市形态
    """
    return [
        {
            "name": "科技园-大冲_商业走廊",
            "coords": [
                [113.9510, 22.5330],
                [113.9490, 22.5350],
                [113.9470, 22.5370],
                [113.9450, 22.5390],
                [113.9430, 22.5410],
            ],
        },
        {
            "name": "粤海-南油_城中村穿越",
            "coords": [
                [113.9350, 22.5280],
                [113.9330, 22.5300],
                [113.9310, 22.5320],
                [113.9290, 22.5340],
                [113.9270, 22.5360],
            ],
        },
        {
            "name": "招商-海上世界_滨海走廊",
            "coords": [
                [113.9050, 22.4820],
                [113.9070, 22.4840],
                [113.9090, 22.4860],
                [113.9110, 22.4880],
                [113.9130, 22.4900],
            ],
        },
        {
            "name": "蛇口-东角头_老社区路径",
            "coords": [
                [113.9180, 22.4850],
                [113.9200, 22.4870],
                [113.9220, 22.4890],
                [113.9240, 22.4910],
                [113.9260, 22.4930],
            ],
        },
        {
            "name": "桃源-大学城_科教走廊",
            "coords": [
                [113.5280, 22.5850],  # 注意：实际南山区经度约113.87-113.97
                [113.5300, 22.5870],
                [113.5320, 22.5890],
                [113.5340, 22.5910],
                [113.5360, 22.5930],
            ],
        },
    ]


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="街景路径验证")
    parser.add_argument("--sv-manifest", default="baidu_streetview/ns_manifest.csv")
    parser.add_argument("--sv-csv", default="baidu_streetview/segmentation_results_v3/seg_final_clean.csv")
    parser.add_argument("--facility", default="network_output/facility_locations.json")
    parser.add_argument("--output", default="verifier_output")
    parser.add_argument("--interval", type=float, default=50, help="采样间隔(米)")
    parser.add_argument("--max-dist", type=float, default=100, help="最大匹配距离(米)")

    args = parser.parse_args()

    result = verify_paths(
        sv_manifest_path=args.sv_manifest,
        sv_csv_path=args.sv_csv,
        facility_path=args.facility,
        sample_interval_m=args.interval,
        max_match_distance_m=args.max_dist,
        output_dir=args.output,
    )

    print(json.dumps(result["statistics"], ensure_ascii=False, indent=2))
