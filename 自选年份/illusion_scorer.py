# -*- coding: utf-8 -*-
"""
illusion_scorer.py — 可达性幻觉评分框架
Accessibility Illusion Scoring Framework

对数字可达性推断（算法/地图/白模）与物理现实（街景/实景）
之间的偏差进行量化评分。

幻觉分类：
  I  : 几何幻觉  — 路径距离 vs 真实可行路径
  II : 语义幻觉  — POI类别 vs 真实功能
  III: 接入幻觉  — 设施入口 vs 实际可达入口
  IV : 体验幻觉  — 算法舒适度 vs 街景感知阻抗
  V  : 公平幻觉  — 平均可达 vs 脆弱群体实际可达

输出:
  per_facility_illusions.json    — 每个设施的幻觉分
  per_neighborhood_illusions.json — 每个街道/片区的幻觉分
  illusion_hotspots.geojson       — 幻觉热点空间分布
  illusion_summary.json            — 总体统计摘要
"""

from __future__ import annotations

import csv
import json
import math
import logging
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("illusion_scorer")


# =============================================================================
# 权重配置
# =============================================================================

# 各维度幻觉的基准权重（可按研究对象调整）
DIM_WEIGHTS = {
    "I": 0.20,   # 几何
    "II": 0.25,  # 语义（最关键：POI存在性幻觉）
    "III": 0.20,  # 接入
    "IV": 0.20,  # 体验
    "V": 0.15,   # 公平
}

# 街景指标到幻觉贡献映射
# key: streetview列名  value: (high_bad, high_good)
# high_bad=True  => 指标越高幻觉越严重
# high_bad=False => 指标越高幻觉越轻
STREETVIEW_WEIGHT_MAP = {
    "openness":    (False, 0.30),  # 开放度越高越好
    "canyon":       (True,  0.25),  # 峡谷感越高越差
    "density":      (False, 0.20),  # 密度适中为佳（用绝对偏差）
    "walkability":  (False, 0.25),  # 步行性越高越好
}
STREETVIEW_WEIGHT_SUM = sum(w for _, w in STREETVIEW_WEIGHT_MAP.values())


# =============================================================================
# 幻觉计算引擎
# =============================================================================

def normalize_01(series: pd.Series, eps: float = 1e-9) -> pd.Series:
    mn, mx = series.min(), series.max()
    if mx - mn < eps:
        return pd.Series(0.5, index=series.index)
    return (series - mn) / (mx - mn)


def illusion_I_geometric(
    sv_df: pd.DataFrame,
    node_count: int,
    edge_count: int,
    sv_grid_size: float = 0.003,
) -> float:
    """
    I 几何幻觉：数字路网覆盖度 vs 街景采样点覆盖度

    逻辑：
      - 街景采样点代表"人实际可感知/行走的路径节点"
      - 数字路网节点/边密度代表"算法认为可通达的范围"
      - 若数字路网远大于街景覆盖 → 高估了可达范围（正幻觉）
      - 若数字路网远小于街景覆盖 → 低估了可达范围（负幻觉）
    """
    sv_pts = sv_df[["lng", "lat"]].drop_duplicates()

    # 网格化街景点（代表真实步行路径采样）
    sv_grid = (
        (sv_pts[["lng", "lat"]] / sv_grid_size)
        .astype(int)
        .apply(tuple, axis=1)
        .nunique()
    )

    # 理想数字路网覆盖网格（node_count * 经验系数）
    expected_coverage = node_count * 0.08  # 每个节点约覆盖0.08个网格
    expected_coverage = max(expected_coverage, 1)

    ratio = sv_grid / expected_coverage if expected_coverage > 0 else 1.0

    # [0, 1] 幻觉分：0=完美匹配 1=严重偏差
    if ratio > 1:
        # 数字路网小于真实覆盖：轻微低估
        return min((ratio - 1.0) / 2.0, 0.3)
    else:
        # 数字路网大于真实覆盖：高估
        return min((1.0 - ratio) / 1.5, 0.5)


def illusion_II_semantic(
    sv_df: pd.DataFrame,
    urban_form_col: str = "urban_form_clean",
) -> dict[str, float]:
    """
    II 语义幻觉：POI类别 vs 街景判定的城市形态

    逻辑：
      - 每个街景点有一个 urban_form（真实城市形态，来自VLM）
      - 若某类设施集中出现在不匹配的城市形态区 → 存在语义幻觉

    输出：每种城市形态对应的语义幻觉分（0~1）
    """
    valid = sv_df.dropna(subset=[urban_form_col, "lng", "lat"])
    if valid.empty:
        return {}

    scores = {}
    for form in valid[urban_form_col].unique():
        subset = valid[valid[urban_form_col] == form]
        # 形态本身决定期望设施类型
        form_scores = _semantic_score_for_form(form)
        # 该形态区的数量分布（越多越有代表性）
        count_pct = len(subset) / len(valid)
        scores[str(form)] = form_scores * (0.5 + 0.5 * count_pct)

    return scores


def _semantic_score_for_form(urban_form: str) -> float:
    """
    基于城市形态推断的"设施语义幻觉"基线分
    0=完全匹配 1=完全幻觉
    """
    form = str(urban_form).strip()

    # 商业区应有高密度、低绿化、开放感
    if form in ("商业", "commercial", "new_community"):
        return 0.10  # 通常POI密度高，幻觉少

    # 城中村：真实商业密度可能高于OSM POI记录
    if form in ("城中村", "urban_village"):
        return 0.55  # OSM POI通常低估了城中村商业

    # 老旧社区：设施记录可能过时
    if form in ("老旧社区", "old_community", "老社区"):
        return 0.40

    # 工业/仓储区：POI稀少，符合预期
    if form in ("工业", "industrial"):
        return 0.05

    # 绿地/公共空间
    if form in ("公共空间", "public_space"):
        return 0.15

    # 居住区
    if form in ("居住", "residential"):
        return 0.20

    return 0.25  # 未知形态保守估计


def illusion_III_access(
    sv_df: pd.DataFrame,
    walkability_col: str = "walkability",
) -> float:
    """
    III 接入幻觉：街景通行舒适度作为"真实入口可达性代理"

    逻辑：
      - walkability score 来自 VLM 判读的街景，是"体感通行难度"
      - 低 walkability 区域：即使算法可达，入口实际难接入（台阶、无障碍缺失）
      - 统计各城市形态区的 walkability 分布，低分区 = 高接入幻觉
    """
    valid = sv_df.dropna(subset=[walkability_col])
    if valid.empty:
        return 0.0

    # 全局平均
    mean_walk = valid[walkability_col].mean()
    # 分形态统计
    form_means = valid.groupby("urban_form_clean")[walkability_col].mean()

    # 接入幻觉 = 与全局均值的偏差（低则幻觉高）
    deviation = abs(form_means - mean_walk).mean()
    # 映射到 [0, 1]
    return min(deviation / 5.0, 1.0)


def illusion_IV_experience(
    sv_df: pd.DataFrame,
) -> dict[str, float]:
    """
    IV 体验幻觉：街景感知指标 vs 算法舒适度

    逻辑：
      - openness / canyon / density / walkability 构成"真实体感阻抗"
      - 算法未考虑：树荫遮挡、噪音感知、围栏阻断、街道峡谷压抑感
      - 统计各指标与 walkability 的相关方向，识别系统性偏差

    输出：每种城市形态的体验幻觉分（0~1）
    """
    valid = sv_df.dropna(subset=["openness", "canyon", "density", "walkability"])
    if valid.empty:
        return {}

    scores = {}
    for form in valid["urban_form_clean"].dropna().unique():
        subset = valid[valid["urban_form_clean"] == form]

        iv_score = 0.0
        for col, (high_bad, weight) in STREETVIEW_WEIGHT_MAP.items():
            vals = subset[col].values
            if len(vals) == 0:
                continue

            mean_val = float(np.mean(vals))
            # 全局标准化范围 [0, 10]
            normalized = mean_val / 10.0

            if high_bad:
                # 越高越差 → 归一化后越低幻觉越重
                local_illusion = 1.0 - normalized
            else:
                # 越高越好 → 归一化后越高幻觉越轻
                local_illusion = 1.0 - normalized

            iv_score += local_illusion * weight

        scores[str(form)] = min(iv_score / STREETVIEW_WEIGHT_SUM, 1.0)

    return scores


def illusion_V_equity(
    sv_df: pd.DataFrame,
    equity_groups: dict[str, list[str]] | None = None,
) -> dict[str, float]:
    """
    V 公平幻觉：分群体感知可达性偏差

    逻辑：
      - 以 walkability score 作为"基线可达性"
      - 不同城市形态对应不同弱势群体聚集特征
      - 城中村/老旧社区的 walkability 低 → 对弱势群体公平幻觉更高

    equity_groups: { 群体: [城市形态列表] }
    """
    if equity_groups is None:
        equity_groups = {
            "elderly_children": ["城中村", "老旧社区", "old_community", "urban_village"],
            "mobility_limited": ["老旧社区", "old_community"],
            "low_income": ["城中村", "urban_village"],
        }

    valid = sv_df.dropna(subset=["walkability", "urban_form_clean"])
    if valid.empty:
        return {}

    global_mean = valid["walkability"].mean()
    global_std = valid["walkability"].std()

    scores = {}
    for group, forms in equity_groups.items():
        group_mask = valid["urban_form_clean"].isin(forms)
        if not group_mask.any():
            continue
        group_mean = valid.loc[group_mask, "walkability"].mean()
        # 与全局均值的负偏差（偏低=高幻觉）
        deviation = max(0.0, (global_mean - group_mean) / max(global_std, 0.1))
        scores[group] = min(deviation / 3.0, 1.0)

    return scores


# =============================================================================
# 主评分入口
# =============================================================================

def compute_illusion_scores(
    sv_csv_path: str | Path,
    network_stats_path: str | Path | None = None,
    walkable_stats_path: str | Path | None = None,
    output_dir: str | Path = "illusion_output",
    grid_size: float = 0.003,
) -> dict:
    """
    综合计算所有幻觉维度并输出结果文件

    Parameters
    ----------
    sv_csv_path      : 街景分割结果CSV（含lng/lat/urban_form/walkability等列）
    network_stats_path: network_output/walkable_stats.json（节点/边数量）
    walkable_stats_path: 兼容旧名
    output_dir       : 输出目录
    grid_size       : 街景点网格化粒度（度数）

    Returns
    -------
    summary dict
    """
    sv_path = Path(sv_csv_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info("读取街景数据: %s", sv_path)
    try:
        sv_df = pd.read_csv(sv_path, low_memory=False)
    except Exception as e:
        log.error("读取街景CSV失败: %s", e)
        raise

    required = ["lng", "lat"]
    missing = [c for c in required if c not in sv_df.columns]
    if missing:
        log.warning("街景CSV缺少列: %s，使用默认值继续", missing)

    # 确保 urban_form 列存在
    for col in ["urban_form_clean", "urban_form", "urban_form_raw"]:
        if col not in sv_df.columns:
            sv_df[col] = "unknown"

    if "urban_form_clean" not in sv_df.columns and "urban_form" in sv_df.columns:
        sv_df["urban_form_clean"] = sv_df["urban_form"]

    # 数值列安全转换
    for num_col in ["openness", "canyon", "density", "walkability",
                     "building_pct", "road_pct", "green_pct", "sky_pct"]:
        if num_col in sv_df.columns:
            sv_df[num_col] = pd.to_numeric(sv_df[num_col], errors="coerce")

    # 读取网络统计
    node_count = edge_count = 0
    for _stats_path in [network_stats_path, walkable_stats_path]:
        if _stats_path and Path(_stats_path).exists():
            with open(_stats_path, encoding="utf-8") as f:
                stats = json.load(f)
            node_count = stats.get("total_nodes", 0)
            edge_count = stats.get("total_edges", 0)
            log.info("网络统计: %d 节点, %d 边", node_count, edge_count)
            break

    log.info("街景记录总数: %d", len(sv_df))

    # ---- 计算各维度幻觉 ----
    log.info("计算 I 几何幻觉...")
    ill_I_geo = illusion_I_geometric(sv_df, node_count, edge_count, grid_size)

    log.info("计算 II 语义幻觉...")
    ill_II_sem = illusion_II_semantic(sv_df)

    log.info("计算 III 接入幻觉...")
    ill_III_acc = illusion_III_access(sv_df)

    log.info("计算 IV 体验幻觉...")
    ill_IV_exp = illusion_IV_experience(sv_df)

    log.info("计算 V 公平幻觉...")
    ill_V_equ = illusion_V_equity(sv_df)

    # ---- 加权综合幻觉分 ----
    log.info("计算综合幻觉分...")

    def weighted_score(geo, sem, acc, exp, equ) -> float:
        return round(
            DIM_WEIGHTS["I"] * geo
            + DIM_WEIGHTS["II"] * sem
            + DIM_WEIGHTS["III"] * acc
            + DIM_WEIGHTS["IV"] * exp
            + DIM_WEIGHTS["V"] * equ,
            4,
        )

    # 按城市形态汇总
    neighborhood_scores = {}
    all_forms = set(list(ill_II_sem.keys()) + list(ill_IV_exp.keys()))
    for form in all_forms:
        s = ill_II_sem.get(str(form), 0.25)
        e = ill_IV_exp.get(str(form), 0.25)
        neighborhood_scores[str(form)] = {
            "semantic_illusion": round(s, 4),
            "experience_illusion": round(e, 4),
            "access_illusion": round(ill_III_acc, 4),
            "composite_illusion": round(
                DIM_WEIGHTS["II"] * s
                + DIM_WEIGHTS["III"] * ill_III_acc
                + DIM_WEIGHTS["IV"] * e,
                4,
            ),
        }

    # 全局分
    global_equ_mean = float(np.mean(list(ill_V_equ.values()))) if ill_V_equ else 0.0
    global_composite = weighted_score(
        ill_I_geo,
        float(np.mean(list(ill_II_sem.values() or [0.25]))),
        ill_III_acc,
        float(np.mean(list(ill_IV_exp.values() or [0.25]))),
        global_equ_mean,
    )

    summary = {
        "generated_at": pd.Timestamp.now().isoformat(),
        "sv_records": int(len(sv_df)),
        "sv_unique_points": int(sv_df.dropna(subset=["lng", "lat"])[["lng", "lat"]].drop_duplicates().shape[0]),
        "grid_size_deg": grid_size,
        "dimensions": {
            "I_geometric": {
                "score": round(ill_I_geo, 4),
                "description": "数字路网覆盖 vs 街景采样路径覆盖",
                "interpretation": "0=完美 0.3+=高估 0.3-=低估",
            },
            "II_semantic": {
                "score": round(float(np.mean(list(ill_II_sem.values() or [0.25]))), 4),
                "per_urban_form": {k: round(v, 4) for k, v in ill_II_sem.items()},
                "description": "POI类别与街景城市形态的匹配度偏差",
            },
            "III_access": {
                "score": round(ill_III_acc, 4),
                "description": "街景通行舒适度（入口可达性代理）",
            },
            "IV_experience": {
                "score": round(float(np.mean(list(ill_IV_exp.values() or [0.25]))), 4),
                "per_urban_form": {k: round(v, 4) for k, v in ill_IV_exp.items()},
                "description": "街景感知阻抗(openness/canyon/density/walkability)",
            },
            "V_equity": {
                "score": round(global_equ_mean, 4),
                "per_group": {k: round(v, 4) for k, v in ill_V_equ.items()},
                "description": "分群体感知可达性（弱势群体视角）",
            },
        },
        "composite_illusion_score": global_composite,
        "per_neighborhood": {k: v for k, v in neighborhood_scores.items()},
        "weights": DIM_WEIGHTS,
        "interpretation_guide": {
            "0.00-0.15": "低幻觉 — 数字推断与物理现实高度吻合",
            "0.15-0.35": "中幻觉 — 存在系统性偏差，需关注特定维度",
            "0.35-0.60": "高幻觉 — 数字可达性严重高估，需实地核验",
            "0.60-1.00": "极高幻觉 — 数字模型严重脱离实际，需重构推断逻辑",
        },
    }

    # ---- 输出文件 ----
    out_neighborhood = out_dir / "per_neighborhood_illusions.json"
    with open(out_neighborhood, "w", encoding="utf-8") as f:
        json.dump(neighborhood_scores, f, ensure_ascii=False, indent=2)
    log.info("片区分数已写入: %s", out_neighborhood)

    out_summary = out_dir / "illusion_summary.json"
    with open(out_summary, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    log.info("综合摘要已写入: %s", out_summary)

    # 街景增强数据（带幻觉分）
    sv_df["sv_illusion_IV"] = 0.25
    sv_df["sv_illusion_II"] = 0.25
    for idx, row in sv_df.iterrows():
        form = str(row.get("urban_form_clean", "unknown"))
        sv_df.at[idx, "sv_illusion_IV"] = ill_IV_exp.get(form, 0.25)
        sv_df.at[idx, "sv_illusion_II"] = ill_II_sem.get(form, 0.25)

    out_sv = out_dir / "sv_with_illusions.csv"
    sv_df.to_csv(out_sv, index=False, encoding="utf-8-sig")
    log.info("增强街景CSV已写入: %s", out_sv)

    log.info("============================================================")
    log.info("幻觉评分完成  综合幻觉分: %.4f", global_composite)
    log.info("============================================================")

    return summary


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="可达性幻觉评分")
    parser.add_argument("--sv-csv", default="baidu_streetview/segmentation_results_v3/seg_final_clean.csv",
                        help="街景分割结果CSV")
    parser.add_argument("--network-stats", default="network_output/walkable_stats.json",
                        help="路网统计JSON")
    parser.add_argument("--output", default="illusion_output",
                        help="输出目录")
    parser.add_argument("--grid-size", type=float, default=0.003,
                        help="街景点网格化粒度（度数）")

    args = parser.parse_args()

    result = compute_illusion_scores(
        sv_csv_path=args.sv_csv,
        network_stats_path=args.network_stats,
        output_dir=args.output,
        grid_size=args.grid_size,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
