# -*- coding: utf-8 -*-
"""
world_model_validator.py — 世界模型验证器
World Model Validator for Accessibility Illusion
融合特斯拉 Occupancy Network + Bird's Eye View 表示思路，
构建物理世界模型（街景特征网格）与数字世界模型（OSM路网）的对照验证。
核心假设（对应你的"可达性幻觉"）：
  数字规划假设"两点之间必可达" —— OSM 认为连通即通行
  物理现实并非如此              —— 街景揭示了真实通行阻抗
模块层级：
  world_model_validator.py  — 主验证器， orchestrates all steps
  ├── GridOccupancy — 构建占用网格（物理）
  │     ├── 物理占用：building_pct / canyon / density / walkability → 网格占用概率
  │     └── 数字占用：OSM 路网边类型 / 宽度估计  → 数字通行概率
  ├── EmbeddingGrid — 构建特征嵌入网格
  │     ├── 物理嵌入：街景多维指标归一化向量
  │     └── 数字嵌入：道路类型 + 拓扑中心性向量
  └── PlanningGap   — 计算规划偏差
        ├── 物理 A* 路径：用物理占用 cost 引导
        ├── 数字 A* 路径：用 OSM 欧氏距离引导
        └── Gap Score：两条路径的离散度
输出：
  world_model_output/physical_occupancy.json    — 物理占用网格
  world_model_output/digital_occupancy.json     — 数字占用网格
  world_model_output/embedding_comparison.json   — 嵌入对比图
  world_model_output/planning_gap.json          — 规划偏差路径
  world_model_output/world_model_summary.json   — 验证摘要
  world_model_output/bev_voxel_3d.json         — 3D体素网格（Tesla Occupancy Network风格）
  world_model_output/road_geometry.json         — 道路几何数据
"""
from __future__ import annotations
import csv
import json
import math
import logging
from collections import defaultdict
from pathlib import Path
from typing import Optional
import numpy as np
import pandas as pd
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("world_model_validator")


# =============================================================================
# GridOccupancy — 占用网格构建
# =============================================================================
class GridOccupancy:
    """
    将散点街景数据和 OSM 路网转换为规则网格占用表征。
    物理占用 (Physical Occupancy):
      - 每个网格格子里融合所有落入的街景点
      - 占用概率 P_occ = 1 - f(openness, walkability, canyon)
      - canyon 越高 → 占用越高（峡谷感 = 物理障碍的一种）
      - walkability 越低 → 占用越高
    数字占用 (Digital Occupancy):
      - 落入 OSM 道路边的区域 → 通行概率高
      - 其他区域 → 通行概率低（但非零，数字模型通常乐观）
    """
    def __init__(
        self,
        grid_size_deg: float = 0.003,
        openness_weight: float = 0.35,
        walkability_weight: float = 0.40,
        canyon_weight: float = 0.25,
    ):
        self.grid_size_deg = grid_size_deg
        self.openness_weight = openness_weight
        self.walkability_weight = walkability_weight
        self.canyon_weight = canyon_weight

    def compute_physical_occupancy(self, sv_df: pd.DataFrame) -> dict:
        """
        从街景 DataFrame 构建物理占用网格。
        Returns
        -------
        dict with keys:
          - grid_size_deg
          - bounds: [min_lng, min_lat, max_lng, max_lat]
          - cells: list of dicts {lng, lat, p_occ, n_samples, openness, walkability, canyon, density}
        """
        if len(sv_df) == 0:
            return {"grid_size_deg": self.grid_size_deg, "cells": []}
        sv_df = sv_df.copy()
        sv_df["grid_lng"] = (
            (sv_df["lng"] // self.grid_size_deg) * self.grid_size_deg
        ).round(10)
        sv_df["grid_lat"] = (
            (sv_df["lat"] // self.grid_size_deg) * self.grid_size_deg
        ).round(10)
        numeric_cols = ["openness", "walkability", "canyon", "density",
                        "building_pct", "road_pct", "green_pct"]
        for col in numeric_cols:
            if col not in sv_df.columns:
                sv_df[col] = 0.0
        sv_df[numeric_cols] = sv_df[numeric_cols].fillna(0.0)
        agg = sv_df.groupby(["grid_lng", "grid_lat"]).agg(
            openness=("openness", "mean"),
            walkability=("walkability", "mean"),
            canyon=("canyon", "mean"),
            density=("density", "mean"),
            building_pct=("building_pct", "mean"),
            road_pct=("road_pct", "mean"),
            green_pct=("green_pct", "mean"),
            n_samples=("lng", "count"),
            lng=("lng", "mean"),
            lat=("lat", "mean"),
        ).reset_index()
        g = self.grid_size_deg

        def cell_occ(row):
            """
            占用概率计算：
              P_occ ∈ [0, 1]
              canyon 高（路窄+高楼）→ 占用高
              walkability 低 → 占用高（步行困难）
              openness 低 → 占用高
            """
            canyon_norm = np.clip(row["canyon"] / 10.0, 0, 1)
            walkability_norm = np.clip(1 - row["walkability"] / 10.0, 0, 1)
            openness_norm = np.clip(1 - row["openness"] / 10.0, 0, 1)
            raw = (
                self.canyon_weight * canyon_norm
                + self.walkability_weight * walkability_norm
                + self.openness_weight * openness_norm
            )
            return float(np.clip(raw, 0.0, 1.0))

        agg["p_occ"] = agg.apply(cell_occ, axis=1)
        cells = []
        for _, row in agg.iterrows():
            cells.append({
                "lng": float(row["grid_lng"]),
                "lat": float(row["grid_lat"]),
                "center_lng": float(row["lng"]),
                "center_lat": float(row["lat"]),
                "p_occ": round(float(row["p_occ"]), 4),
                "n_samples": int(row["n_samples"]),
                "openness": round(float(row["openness"]), 2),
                "walkability": round(float(row["walkability"]), 2),
                "canyon": round(float(row["canyon"]), 2),
                "density": round(float(row["density"]), 2),
                "building_pct": round(float(row["building_pct"]), 2),
                "road_pct": round(float(row["road_pct"]), 2),
                "green_pct": round(float(row["green_pct"]), 2),
                "urban_form": str(row.get("urban_form_clean", "unknown")),
            })
        result = {
            "grid_size_deg": self.grid_size_deg,
            "bounds": [
                float(agg["grid_lng"].min()),
                float(agg["grid_lat"].min()),
                float(agg["grid_lng"].max()),
                float(agg["grid_lat"].max()),
            ],
            "total_cells": len(cells),
            "cells": cells,
            "occupancy_stats": {
                "mean_p_occ": round(float(agg["p_occ"].mean()), 4),
                "median_p_occ": round(float(agg["p_occ"].median()), 4),
                "high_occ_cells": int((agg["p_occ"] > 0.6).sum()),
                "low_occ_cells": int((agg["p_occ"] < 0.3).sum()),
            },
            "method": "streetview_voxel",
            "description": (
                "物理占用网格：canyon + walkability + openness 加权融合。"
                "canyon_weight={}, walkability_weight={}, openness_weight={}".format(
                    self.canyon_weight, self.walkability_weight, self.openness_weight
                )
            ),
        }
        log.info(
            f"[ GridOccupancy ] 物理占用: {len(cells)} 格, "
            f"平均占用 {result['occupancy_stats']['mean_p_occ']:.3f}"
        )
        return result

    def compute_digital_occupancy_from_network(
        self, network_stats: dict
    ) -> dict:
        """
        从路网统计构建数字占用表征。
        OSM 假设：
          - 有道路 → 可通行 (p_occ ≈ 0)
          - 无道路 → 不可通行 (p_occ ≈ 1)
        这本身就是"数字乐观偏差"的来源。
        进一步的数字占用分层：
          - 高速/主干路 (primary, secondary): 机动车优先，行人占用高
          - 支路 (tertiary, residential): 行人可达，占用低
          - 人行道 (footway, pedestrian): 完全可达，占用=0
          - 台阶 (steps): 某些群体不可达，占用=0.5
        """
        by_fclass = network_stats.get("by_fclass", {})
        total_edges = network_stats.get("total_edges", 1)
        road_class_weights = {
            "primary": 0.70,
            "primary_link": 0.65,
            "secondary": 0.50,
            "secondary_link": 0.50,
            "tertiary": 0.30,
            "tertiary_link": 0.30,
            "residential": 0.15,
            "living_street": 0.10,
            "unclassified": 0.20,
            "pedestrian": 0.02,
            "footway": 0.02,
            "path": 0.02,
            "service": 0.10,
            "steps": 0.45,
            "track": 0.35,
        }
        breakdown = {}
        for fclass, count in by_fclass.items():
            p_occ = road_class_weights.get(fclass, 0.25)
            breakdown[fclass] = {
                "edge_count": count,
                "weight": p_occ,
                "p_occ": p_occ,
                "share": round(count / total_edges, 4),
            }
        weighted_p_occ = sum(
            breakdown[k]["weight"] * breakdown[k]["share"]
            for k in breakdown
        )
        result = {
            "total_edges": total_edges,
            "total_nodes": network_stats.get("total_nodes", 0),
            "road_class_breakdown": breakdown,
            "mean_p_occ": round(weighted_p_occ, 4),
            "method": "osm_occupancy",
            "description": (
                "数字占用：OSM 道路类型分层。" * 1 +
                "数字模型假设有路即通行，但物理现实未必如此。"
            ),
        }
        log.info(
            f"[ GridOccupancy ] 数字占用: {total_edges} 边, "
            f"加权平均 p_occ={weighted_p_occ:.3f}"
        )
        return result

    def compute_bev_occupancy_layers(self, sv_df: pd.DataFrame) -> dict:
        """
        Tesla Occupancy Network 风格的 BEV 多层占用表征。
        计算4个高度层的占用值，模拟街道垂直方向的空间分布。

        Layer 0 "ground" (h=0-1m): 道路表面、人行道
          - 来源: road_pct (越高占用越低，因为道路本身可通行)

        Layer 1 "pedestrian" (h=1-2.5m): 行人活动区
          - 来源: canyon * (1 - walkability)
          - 高峡谷感+低步行可达 → 占用高

        Layer 2 "vehicle" (h=2.5-5m): 车体、建筑立面
          - 来源: building_pct * density
          - 高密度+高建筑比 → 占用高

        Layer 3 "canopy" (h=5-15m): 树冠、高层建筑
          - 来源: green_pct + building_pct
          - 有绿化或超高层 → 占用高

        Returns
        -------
        dict: 包含bev_voxel_3d.json的完整数据
        """
        if len(sv_df) == 0:
            return {"grid_size_deg": self.grid_size_deg, "cells": []}

        sv_df = sv_df.copy()
        sv_df["grid_lng"] = (
            (sv_df["lng"] // self.grid_size_deg) * self.grid_size_deg
        ).round(10)
        sv_df["grid_lat"] = (
            (sv_df["lat"] // self.grid_size_deg) * self.grid_size_deg
        ).round(10)
        numeric_cols = ["openness", "walkability", "canyon", "density",
                        "building_pct", "road_pct", "green_pct", "road_type"]
        for col in numeric_cols:
            if col not in sv_df.columns:
                sv_df[col] = 0.0 if col != "road_type" else "unknown"
        sv_df[numeric_cols[:-1]] = sv_df[numeric_cols[:-1]].fillna(0.0)
        sv_df["road_type"] = sv_df["road_type"].fillna("unknown")

        agg = sv_df.groupby(["grid_lng", "grid_lat"]).agg(
            openness=("openness", "mean"),
            walkability=("walkability", "mean"),
            canyon=("canyon", "mean"),
            density=("density", "mean"),
            building_pct=("building_pct", "mean"),
            road_pct=("road_pct", "mean"),
            green_pct=("green_pct", "mean"),
            n_samples=("lng", "count"),
            lng=("lng", "mean"),
            lat=("lat", "mean"),
            road_type=("road_type", lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "unknown"),
        ).reset_index()

        def compute_height_layers(row: pd.Series) -> tuple:
            """计算4个高度层的占用值"""
            road_pct = float(row["road_pct"]) / 100.0
            canyon = float(row["canyon"]) / 10.0
            walkability = float(row["walkability"]) / 10.0
            building_pct = float(row["building_pct"]) / 100.0
            density = float(row["density"]) / 10.0
            green_pct = float(row["green_pct"]) / 100.0

            # Layer 0: ground (0-1m) - 道路/人行道，road_pct越高越通畅
            occ_ground = float(np.clip(1.0 - road_pct * 0.8, 0.0, 1.0))

            # Layer 1: pedestrian (1-2.5m) - 行人区被峡谷效应挤压
            pedestrian_barrier = canyon * (1.0 - walkability)
            occ_pedestrian = float(np.clip(pedestrian_barrier, 0.0, 1.0))

            # Layer 2: vehicle (2.5-5m) - 车体/建筑立面
            occ_vehicle = float(np.clip(building_pct * density * 1.5, 0.0, 1.0))

            # Layer 3: canopy (5-15m) - 树冠/超高层
            occ_canopy = float(np.clip(green_pct * 0.7 + building_pct * density * 0.5, 0.0, 1.0))

            return (occ_ground, occ_pedestrian, occ_vehicle, occ_canopy)

        # 计算流动场（基于walkability梯度）
        flow_field = self._compute_flow_field(agg)

        cells = []
        for idx, row in agg.iterrows():
            occ_ground, occ_ped, occ_veh, occ_canopy = compute_height_layers(row)
            lng_key = float(row["grid_lng"])
            lat_key = float(row["grid_lat"])
            flow = flow_field.get((lng_key, lat_key), [0.0, 0.0])

            # 总占用（4层平均）
            total_occ = (occ_ground + occ_ped + occ_veh + occ_canopy) / 4.0

            # 物理占用（基于原始公式）
            canyon_norm = np.clip(row["canyon"] / 10.0, 0, 1)
            walkability_norm = np.clip(1 - row["walkability"] / 10.0, 0, 1)
            openness_norm = np.clip(1 - row["openness"] / 10.0, 0, 1)
            physical_occ = float(np.clip(
                self.canyon_weight * canyon_norm +
                self.walkability_weight * walkability_norm +
                self.openness_weight * openness_norm,
                0.0, 1.0
            ))

            cells.append({
                "lng": lng_key,
                "lat": lat_key,
                "center_lng": float(row["lng"]),
                "center_lat": float(row["lat"]),
                "height_layers": [
                    round(occ_ground, 4),
                    round(occ_ped, 4),
                    round(occ_veh, 4),
                    round(occ_canopy, 4),
                ],
                "total_occupancy": round(total_occ, 4),
                "physical_flow": [round(flow[0], 4), round(flow[1], 4)],
                "p_occ": round(physical_occ, 4),
                "digital_occ": 0.5,  # placeholder, will be populated from OSM data
                "road_type": str(row["road_type"]),
                "urban_form": str(row.get("urban_form_clean", "unknown")),
                "n_samples": int(row["n_samples"]),
                # 原始特征保留（用于调试）
                "openness": round(float(row["openness"]), 2),
                "walkability": round(float(row["walkability"]), 2),
                "canyon": round(float(row["canyon"]), 2),
                "density": round(float(row["density"]), 2),
                "building_pct": round(float(row["building_pct"]), 2),
                "road_pct": round(float(row["road_pct"]), 2),
                "green_pct": round(float(row["green_pct"]), 2),
            })

        bounds = [
            float(agg["grid_lng"].min()),
            float(agg["grid_lat"].min()),
            float(agg["grid_lng"].max()),
            float(agg["grid_lat"].max()),
        ]

        result = {
            "format_version": "1.0",
            "description": "Tesla Occupancy Network 风格 3D BEV 体素表征",
            "bounds": bounds,
            "grid_resolution_deg": self.grid_size_deg,
            "height_layers": {
                "layer_0": {"name": "ground", "height_range_m": [0, 1], "source": "road_pct"},
                "layer_1": {"name": "pedestrian", "height_range_m": [1, 2.5], "source": "canyon * (1-walkability)"},
                "layer_2": {"name": "vehicle", "height_range_m": [2.5, 5], "source": "building_pct * density"},
                "layer_3": {"name": "canopy", "height_range_m": [5, 15], "source": "green_pct + building_pct"},
            },
            "physical_flow": {
                "description": "基于walkability梯度的流动方向场",
                "flow_direction": "从低占用指向高占用",
                "magnitude": "与walkability成正比",
                "normalization": "[-1, 1]",
            },
            "total_cells": len(cells),
            "cells": cells,
            "layer_stats": {
                "mean_occ_ground": round(float(np.mean([c["height_layers"][0] for c in cells])), 4),
                "mean_occ_pedestrian": round(float(np.mean([c["height_layers"][1] for c in cells])), 4),
                "mean_occ_vehicle": round(float(np.mean([c["height_layers"][2] for c in cells])), 4),
                "mean_occ_canopy": round(float(np.mean([c["height_layers"][3] for c in cells])), 4),
                "mean_total_occupancy": round(float(np.mean([c["total_occupancy"] for c in cells])), 4),
            },
        }

        log.info(
            f"[ GridOccupancy ] BEV 3D体素: {len(cells)} 格, "
            f"平均总占用={result['layer_stats']['mean_total_occupancy']:.3f}"
        )
        return result

    def _compute_flow_field(self, agg: pd.DataFrame) -> dict:
        """
        计算基于walkability梯度的流动场。
        流动方向：从低占用区域流向高占用区域（行人倾向于绕过障碍）
        流动强度：与walkability成正比
        """
        # 构建查找表
        grid_lookup = {}
        for _, row in agg.iterrows():
            key = (float(row["grid_lng"]), float(row["grid_lat"]))
            walkability = float(row["walkability"])
            canyon = float(row["canyon"])
            # 计算局部占用（用于梯度计算）
            local_occ = canyon / 10.0 * (1 - walkability / 10.0)
            grid_lookup[key] = {
                "walkability": walkability,
                "occupancy": local_occ,
                "lng": float(row["lng"]),
                "lat": float(row["lat"]),
            }

        flow_field = {}
        g = self.grid_size_deg
        directions = [
            (g, 0), (-g, 0), (0, g), (0, -g),  # 4邻域
            (g, g), (-g, -g), (g, -g), (-g, g),  # 对角
        ]

        for key, cell_data in grid_lookup.items():
            lng, lat = key
            occ_center = cell_data["occupancy"]
            walk_center = cell_data["walkability"]

            # 计算梯度（周围8邻域的平均占用 - 中心占用）
            grad_x = 0.0
            grad_y = 0.0
            n_neighbors = 0

            for dx, dy in directions:
                neighbor_key = (lng + dx, lat + dy)
                if neighbor_key in grid_lookup:
                    neighbor_occ = grid_lookup[neighbor_key]["occupancy"]
                    # 梯度 = 邻域 - 中心（正=流向邻域）
                    grad_x += (neighbor_occ - occ_center) * (dx / g)
                    grad_y += (neighbor_occ - occ_center) * (dy / g)
                    n_neighbors += 1

            if n_neighbors > 0:
                grad_x /= n_neighbors
                grad_y /= n_neighbors

            # 流动方向 = 梯度方向（从低占用指向高占用）
            # 流动强度 = walkability归一化
            flow_magnitude = walk_center / 10.0  # [0, 1]
            grad_magnitude = math.sqrt(grad_x**2 + grad_y**2)

            if grad_magnitude > 1e-6:
                # 归一化梯度向量
                flow_x = (grad_x / grad_magnitude) * flow_magnitude
                flow_y = (grad_y / grad_magnitude) * flow_magnitude
            else:
                flow_x, flow_y = 0.0, 0.0

            flow_field[key] = [float(np.clip(flow_x, -1.0, 1.0)),
                               float(np.clip(flow_y, -1.0, 1.0))]

        return flow_field

    def compute_road_geometry(self, network_stats: Optional[dict] = None,
                                sv_df: Optional[pd.DataFrame] = None) -> dict:
        """
        从OSM路网数据或街景数据生成道路几何数据。
        优先使用OSM数据，否则基于街景推断。

        Returns
        -------
        dict: road_geometry.json 完整数据
        """
        bounds = [0, 0, 0, 0]
        road_segments = []

        if network_stats is not None:
            # 从OSM数据提取道路几何
            osm_edges = network_stats.get("edges", [])
            osm_nodes = network_stats.get("nodes", {})
            road_class_weights = {
                "primary": {"road_class": "primary", "width_m": 15.0},
                "primary_link": {"road_class": "primary", "width_m": 12.0},
                "secondary": {"road_class": "secondary", "width_m": 12.0},
                "secondary_link": {"road_class": "secondary", "width_m": 10.0},
                "tertiary": {"road_class": "tertiary", "width_m": 8.0},
                "tertiary_link": {"road_class": "tertiary", "width_m": 6.0},
                "residential": {"road_class": "residential", "width_m": 6.0},
                "living_street": {"road_class": "living_street", "width_m": 5.0},
                "unclassified": {"road_class": "unclassified", "width_m": 6.0},
                "pedestrian": {"road_class": "pedestrian", "width_m": 3.0},
                "footway": {"road_class": "footway", "width_m": 2.0},
                "path": {"road_class": "path", "width_m": 2.0},
                "service": {"road_class": "service", "width_m": 4.0},
                "steps": {"road_class": "steps", "width_m": 1.5},
                "track": {"road_class": "track", "width_m": 3.5},
            }

            # 如果edges是坐标列表格式
            if isinstance(osm_edges, list) and len(osm_edges) > 0:
                first_edge = osm_edges[0]
                if isinstance(first_edge, dict) and "geometry" in first_edge:
                    # 新的几何格式
                    for edge in osm_edges:
                        geom = edge.get("geometry", [])
                        if len(geom) >= 2:
                            road_class = edge.get("fclass", "unknown")
                            road_info = road_class_weights.get(road_class, {"road_class": road_class, "width_m": 6.0})
                            road_segments.append({
                                "lng_start": float(geom[0][0]),
                                "lat_start": float(geom[0][1]),
                                "lng_end": float(geom[-1][0]),
                                "lat_end": float(geom[-1][1]),
                                "road_class": road_info["road_class"],
                                "digital_occ": road_class_weights.get(road_class, {}).get("road_class", 0.25),
                                "width_m": road_info["width_m"],
                                "edge_id": edge.get("edge_id", ""),
                            })
                elif isinstance(first_edge, (list, tuple)):
                    # 简化格式：[[lng1, lat1], [lng2, lat2], ...]
                    road_class = "unknown"
                    for edge in osm_edges:
                        if len(edge) >= 2:
                            road_segments.append({
                                "lng_start": float(edge[0][0]),
                                "lat_start": float(edge[0][1]),
                                "lng_end": float(edge[1][0]),
                                "lat_end": float(edge[1][1]),
                                "road_class": road_class,
                                "digital_occ": 0.25,
                                "width_m": 6.0,
                            })
            elif isinstance(osm_edges, dict):
                # 字典格式
                for edge_id, edge_data in osm_edges.items():
                    geom = edge_data.get("geometry", [])
                    if len(geom) >= 2:
                        road_class = edge_data.get("fclass", "unknown")
                        road_info = road_class_weights.get(road_class, {"road_class": road_class, "width_m": 6.0})
                        road_segments.append({
                            "lng_start": float(geom[0][0]),
                            "lat_start": float(geom[0][1]),
                            "lng_end": float(geom[-1][0]),
                            "lat_end": float(geom[-1][1]),
                            "road_class": road_info["road_class"],
                            "digital_occ": road_class_weights.get(road_class, {}).get("road_class", 0.25),
                            "width_m": road_info["width_m"],
                            "edge_id": str(edge_id),
                        })

        # 如果没有OSM数据，从街景数据生成合成道路
        if len(road_segments) == 0 and sv_df is not None and len(sv_df) > 0:
            log.info("[ GridOccupancy ] 无OSM数据，从街景推断道路几何...")
            sv_df = sv_df.copy()
            sv_df["grid_lng"] = (
                (sv_df["lng"] // self.grid_size_deg) * self.grid_size_deg
            ).round(10)
            sv_df["grid_lat"] = (
                (sv_df["lat"] // self.grid_size_deg) * self.grid_size_deg
            ).round(10)

            # 按grid分组，取高road_pct的格子作为道路节点
            road_cells = sv_df[sv_df["road_pct"] > 20].groupby(
                ["grid_lng", "grid_lat"]
            ).agg({
                "lng": "mean",
                "lat": "mean",
                "road_pct": "mean",
                "urban_form": lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "unknown"
            }).reset_index()
            road_cells.rename(columns={"urban_form": "road_type"}, inplace=True)

            road_cells = road_cells.sort_values(["grid_lng", "grid_lat"])

            # 生成道路线段（沿lng或lat方向连接相邻格子）
            for idx in range(len(road_cells) - 1):
                curr = road_cells.iloc[idx]
                next_row = road_cells.iloc[idx + 1]

                # 只连接距离较近的格子
                dist = math.sqrt(
                    (curr["grid_lng"] - next_row["grid_lng"])**2 +
                    (curr["grid_lat"] - next_row["grid_lat"])**2
                )
                if dist < self.grid_size_deg * 3:
                    road_type = str(curr["road_type"]) if pd.notna(curr["road_type"]) else "residential"
                    width_map = {
                        "primary": 15.0, "secondary": 12.0, "tertiary": 8.0,
                        "residential": 6.0, "pedestrian": 3.0, "footway": 2.0
                    }
                    road_segments.append({
                        "lng_start": float(curr["lng"]),
                        "lat_start": float(curr["lat"]),
                        "lng_end": float(next_row["lng"]),
                        "lat_end": float(next_row["lat"]),
                        "road_class": road_type if road_type in width_map else "residential",
                        "digital_occ": 0.15 if road_type in ["residential", "pedestrian", "footway"] else 0.30,
                        "width_m": width_map.get(road_type, 6.0),
                    })

        # 计算bounds
        if road_segments:
            lngs = [s["lng_start"] for s in road_segments] + [s["lng_end"] for s in road_segments]
            lats = [s["lat_start"] for s in road_segments] + [s["lat_end"] for s in road_segments]
            bounds = [min(lngs), min(lats), max(lngs), max(lats)]

        # 按road_class统计
        class_stats = defaultdict(lambda: {"count": 0, "total_length_deg": 0.0})
        for seg in road_segments:
            rc = seg["road_class"]
            seg_len = math.sqrt(
                (seg["lng_end"] - seg["lng_start"])**2 +
                (seg["lat_end"] - seg["lat_start"])**2
            )
            class_stats[rc]["count"] += 1
            class_stats[rc]["total_length_deg"] += seg_len

        result = {
            "format_version": "1.0",
            "description": "道路几何数据 - OSM提取或街景推断",
            "bounds": bounds,
            "total_segments": len(road_segments),
            "road_class_stats": {
                rc: {
                    "segment_count": int(stats["count"]),
                    "total_length_deg": round(stats["total_length_deg"], 6),
                }
                for rc, stats in class_stats.items()
            },
            "road_segments": road_segments[:10000],  # 限制数量避免过大
        }

        log.info(
            f"[ GridOccupancy ] 道路几何: {len(road_segments)} 段, "
            f"{len(class_stats)} 种道路类型"
        )
        return result


# =============================================================================
# EmbeddingGrid — 特征嵌入网格
# =============================================================================
class EmbeddingGrid:
    """
    将每个网格单元编码为多维特征向量（嵌入），用于比较数字和物理表征。
    物理嵌入维度（4维）：
      [openness_norm, walkability_norm, 1-canyon_norm, green_pct]
      - 高 openness  → 开放可达
      - 高 walkability → 步行友好
      - 低 canyon   → 非峡谷地形
      - 高 green_pct → 有绿化缓冲
    数字嵌入维度（3维）：
      [road_type_score, centrality_norm, breadth_score]
      - road_type_score: 基于 OSM fclass 的通行优先级
      - centrality_norm: 该道路在拓扑网络中的中心性（节点度归一化）
      - breadth_score: 估计的道路宽度（宽路→机动车主导→行人可达性低）
    比较方法：
      - Cosine Similarity: 衡量两套嵌入的空间分布相似度
      - Euclidean Distance: 衡量每个格子的偏差幅度
      - Hotspot Detection: 找出数字与物理严重不吻合的格子
    """
    PHYSICAL_DIM_NAMES = ["openness", "walkability", "non_canyon", "green_pct"]
    DIGITAL_DIM_NAMES = ["road_type", "centrality", "breadth"]

    def __init__(self):
        pass

    def build_physical_embedding(self, cell: dict) -> list[float]:
        """构建单个格子的物理嵌入向量（归一化到 [0,1]）"""
        openness = float(cell.get("openness", 0)) / 10.0
        walkability = float(cell.get("walkability", 0)) / 10.0
        canyon = float(cell.get("canyon", 0)) / 10.0
        green = float(cell.get("green_pct", 0))
        non_canyon = max(0.0, 1.0 - canyon)
        return [
            float(np.clip(openness, 0, 1)),
            float(np.clip(walkability, 0, 1)),
            float(np.clip(non_canyon, 0, 1)),
            float(np.clip(green, 0, 1)),
        ]

    def build_digital_embedding(self, cell: dict, network_stats: dict = None) -> list[float]:
        """
        构建单个格子的数字嵌入向量。
        如果 cell 中有 urban_form，使用形态类型推断：
          - commercial     → 道路宽但密度高，行人受机动车挤压
          - residential   → 道路窄但慢行友好
          - new_community → 新开发区域，道路宽敞但步行设施可能不完善
          - 城中村        → 道路极窄，可达但体验差
        """
        urban_form = cell.get("urban_form", "unknown")
        form_scores = {
            "commercial":       (0.7, 0.6, 0.75),
            "residential":     (0.3, 0.4, 0.35),
            "new_community":   (0.4, 0.7, 0.55),
            "城中村":           (0.5, 0.2, 0.80),
            "low_rise":        (0.2, 0.3, 0.30),
            "industrial":     (0.6, 0.5, 0.70),
            "mixed":           (0.5, 0.5, 0.55),
            "绿地进行中":        (0.1, 0.8, 0.20),
            "Open/Other":      (0.4, 0.5, 0.50),
            "unknown":         (0.4, 0.5, 0.50),
        }
        scores = form_scores.get(urban_form, (0.4, 0.5, 0.50))
        road_type, centrality, breadth = scores
        building_pct = float(cell.get("building_pct", 0))
        density = float(cell.get("density", 0))
        breadth_score = (building_pct + density / 10.0) / 2.0
        format_consistency = 1.0 - breadth_score
        return [
            float(np.clip(road_type, 0, 1)),
            float(np.clip(centrality, 0, 1)),
            float(np.clip(breadth_score, 0, 1)),
            float(np.clip(format_consistency, 0, 1)),
        ]

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """计算两个向量的余弦相似度"""
        if len(a) != len(b) or len(a) == 0:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a < 1e-9 or norm_b < 1e-9:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def euclidean_distance(a: list[float], b: list[float]) -> float:
        """计算两个向量的欧氏距离"""
        if len(a) != len(b):
            return float("inf")
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    def compute_embedding_comparison(
        self, physical_cells: list[dict]
    ) -> dict:
        """
        对所有物理格子，计算物理嵌入 vs 数字嵌入的偏差。
        Returns
        -------
        dict with:
          - global_cosine_sim: 所有格子的平均余弦相似度
          - global_euclidean: 所有格子的平均欧氏距离
          - hotspots: 高偏差格子列表
          - per_cell_deviation: 每格偏差
        """
        if not physical_cells:
            return {
                "global_cosine_sim": 0.0,
                "global_euclidean": 0.0,
                "hotspots": [],
                "per_cell_deviation": [],
            }
        cos_sims = []
        eucl_dists = []
        per_cell = []
        hotspots = []
        for cell in physical_cells:
            phys_emb = self.build_physical_embedding(cell)
            dig_emb = self.build_digital_embedding(cell)
            cos_sim = self.cosine_similarity(phys_emb, dig_emb)
            eucl_dist = self.euclidean_distance(phys_emb, dig_emb)
            deviation = float(eucl_dist) / math.sqrt(len(phys_emb)) if len(phys_emb) > 0 else 0.0
            cos_sims.append(cos_sim)
            eucl_dists.append(deviation)
            item = {
                "lng": cell.get("lng"),
                "lat": cell.get("lat"),
                "cosine_sim": round(cos_sim, 4),
                "euclidean_dev": round(deviation, 4),
                "phys_emb": [round(v, 3) for v in phys_emb],
                "dig_emb": [round(v, 3) for v in dig_emb],
                "urban_form": cell.get("urban_form", "unknown"),
                "p_occ": cell.get("p_occ", 0.0),
            }
            per_cell.append(item)
            if deviation > 0.30:
                hotspots.append(item)
        hotspots.sort(key=lambda x: x["euclidean_dev"], reverse=True)
        result = {
            "n_cells": len(physical_cells),
            "global_cosine_sim": round(float(np.mean(cos_sims)), 4),
            "global_euclidean_dev": round(float(np.mean(eucl_dists)), 4),
            "cosine_std": round(float(np.std(cos_sims)), 4),
            "hotspots": hotspots[:20],
            "n_hotspots": len(hotspots),
            "per_cell_deviation": per_cell,
            "interpretation": {
                "cosine_sim_guide": "1.0=完美吻合, 0=完全相反",
                "euclidean_dev_guide": "值越大表示数字与物理表征偏差越大",
            },
        }
        log.info(
            f"[ EmbeddingGrid ] 嵌入对比: {len(physical_cells)} 格, "
            f"cos_sim={result['global_cosine_sim']:.3f}, "
            f"eucl_dev={result['global_euclidean_dev']:.3f}, "
            f"hotspots={len(hotspots)}"
        )
        return result


# =============================================================================
# PlanningGap — 规划偏差计算
# =============================================================================
class PlanningGap:
    """
    对比数字最优路径（欧氏距离最短）和物理可行路径（考虑占用 cost）的差异。
    方法（基于 A* 伪路径，不依赖外部路网库）：
      1. 在物理占用网格上做贪婪爬山（greedy ascent）
         cost = p_occ（高占用 = 高通行代价）
      2. 数字路径 = 直线插值（OSM 认为连通即直达）
      3. Gap = 路径 cost 差异 + 绕行比例 + 偏差面积
    关键指标：
      - path_cost_gap: 物理路径 vs 数字路径的累积 cost 差
      - detour_ratio: 物理路径长度 / 数字路径长度
      - blocked_segments: 数字认为可通行但物理被高占用阻断的路段
    """
    def __init__(self, occupancy_result: dict, embedding_result: dict):
        self.occupancy_result = occupancy_result
        self.embedding_result = embedding_result
        self.cells = {f"{c['lng']:.6f},{c['lat']:.6f}": c
                      for c in occupancy_result.get("cells", [])}

    @staticmethod
    def haversine_m(lat1, lon1, lat2, lon2):
        R = 6371000
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
             * math.sin(dlon / 2) ** 2)
        return R * 2 * math.asin(math.sqrt(a))

    def get_nearest_cell(self, lat: float, lon: float) -> dict | None:
        """找到最近的占用格子"""
        min_dist = float("inf")
        best = None
        for key, cell in self.cells.items():
            d = self.haversine_m(lat, lon, cell["center_lat"], cell["center_lng"])
            if d < min_dist:
                min_dist = d
                best = cell
        return best

    def greedy_path_cost(self, path_coords: list[tuple[float, float]]) -> dict:
        """
        计算物理引导路径的 cost。
        Parameters
        ----------
        path_coords : [(lat, lon), ...]
        Returns dict with:
          - total_cost: float 累积通行代价
          - total_distance_m: float 物理路径长度
          - avg_p_occ: float 平均占用
          - blocked_ratio: float 高占用(p_occ>0.7)占比
          - n_steps: int
        """
        if len(path_coords) < 2:
            return {"total_cost": 0.0, "total_distance_m": 0.0,
                    "avg_p_occ": 0.0, "blocked_ratio": 0.0, "n_steps": 0}
        total_cost = 0.0
        total_dist = 0.0
        p_occs = []
        n_steps = 0
        for i in range(len(path_coords) - 1):
            lat1, lon1 = path_coords[i]
            lat2, lon2 = path_coords[i + 1]
            dist = self.haversine_m(lat1, lon1, lat2, lon2)
            total_dist += dist
            cell = self.get_nearest_cell(lat1, lon1)
            if cell:
                cost = cell["p_occ"]
                total_cost += cost * dist
                p_occs.append(cost)
                n_steps += 1
        avg_p_occ = float(np.mean(p_occs)) if p_occs else 0.0
        blocked_ratio = float(np.mean([1 if p > 0.7 else 0 for p in p_occs])) if p_occs else 0.0
        return {
            "total_cost": round(total_cost, 2),
            "total_distance_m": round(total_dist, 2),
            "avg_p_occ": round(avg_p_occ, 4),
            "blocked_ratio": round(blocked_ratio, 4),
            "n_steps": n_steps,
        }

    @staticmethod
    def straight_path_cost(
        path_coords: list[tuple[float, float]]
    ) -> dict:
        """
        数字最短路径（直线插值）的 cost。
        OSM 假设：任意两个连通节点之间可以直线到达（理想化）。
        cost = 欧氏距离（不考虑物理占用）
        """
        if len(path_coords) < 2:
            return {"total_cost": 0.0, "total_distance_m": 0.0, "n_segments": 0}
        total_dist = sum(
            PlanningGap.haversine_m(p[0], p[1], q[0], q[1])
            for p, q in zip(path_coords[:-1], path_coords[1:])
        )
        return {
            "total_cost": round(total_dist, 2),
            "total_distance_m": round(total_dist, 2),
            "n_segments": len(path_coords) - 1,
            "note": "数字直线 cost = 欧氏距离，假设连通即通行",
        }

    def compute_planning_gap(
        self,
        sample_paths: list[dict] | None = None,
    ) -> dict:
        """
        计算预设路径的规划偏差。
        sample_paths: list of {name, coords: [(lat,lon), ...]}
        """
        if sample_paths is None:
            sample_paths = self._get_default_paths()
        results = []
        for path_def in sample_paths:
            coords = path_def["coords"]
            if len(coords) < 2:
                continue
            dig_result = self.straight_path_cost(coords)
            phys_result = self.greedy_path_cost(coords)
            path_dist = dig_result["total_distance_m"]
            cost_gap = abs(phys_result["total_cost"] - phys_result["total_distance_m"])
            detour_ratio = (
                phys_result["total_distance_m"] / max(path_dist, 1.0)
            )
            blocked_ratio = phys_result.get("blocked_ratio", 0.0)
            gap_score = (
                0.4 * np.clip(cost_gap / max(path_dist, 1.0), 0, 1)
                + 0.3 * np.clip(detour_ratio - 1.0, 0, 2) / 2.0
                + 0.3 * blocked_ratio
            )
            results.append({
                "path_name": path_def["name"],
                "digital_cost": dig_result["total_cost"],
                "physical_cost": phys_result["total_cost"],
                "cost_gap": round(cost_gap, 2),
                "detour_ratio": round(detour_ratio, 3),
                "blocked_ratio": round(blocked_ratio, 4),
                "gap_score": round(float(np.clip(gap_score, 0, 1)), 3),
                "avg_physical_occ": phys_result["avg_p_occ"],
                "n_physical_steps": phys_result["n_steps"],
                "coords": [[lat, lon] for lat, lon in coords],
            })
        gap_scores = [r["gap_score"] for r in results]
        result = {
            "n_paths": len(results),
            "paths": results,
            "mean_gap_score": round(float(np.mean(gap_scores)), 4),
            "max_gap_score": round(float(np.max(gap_scores)), 4),
            "gap_levels": {
                "low": sum(1 for g in gap_scores if g < 0.2),
                "medium": sum(1 for g in gap_scores if 0.2 <= g < 0.4),
                "high": sum(1 for g in gap_scores if 0.4 <= g < 0.6),
                "extreme": sum(1 for g in gap_scores if g >= 0.6),
            },
            "interpretation": {
                "gap_score": "0=数字与物理完全吻合, 1=规划与现实完全脱节",
                "detour_ratio": ">1 表示物理路径比数字直线更长",
                "blocked_ratio": ">0 表示存在被数字认为可通行但物理高占用的路段",
            },
        }
        log.info(
            f"[ PlanningGap ] 规划偏差: {len(results)} 条路径, "
            f"平均 gap_score={result['mean_gap_score']:.3f}"
        )
        return result

    def _get_default_paths(self) -> list[dict]:
        """
        基于街景数据分布自动生成代表性路径。
        方法：取 walkability 最高和最低的格子作为端点，
        构建跨形态类型的对照路径。
        """
        cells_sorted = sorted(
            self.occupancy_result.get("cells", []),
            key=lambda c: c.get("walkability", 5),
            reverse=True,
        )
        paths = []
        max_pairs = min(5, len(cells_sorted))
        for i in range(0, max_pairs, 2):
            if i + 1 >= len(cells_sorted):
                break
            c0 = cells_sorted[i]
            c1 = cells_sorted[i + 1]
            paths.append({
                "name": f"walkability差异路径_{i//2+1}",
                "coords": [
                    (c0["center_lat"], c0["center_lng"]),
                    (c1["center_lat"], c1["center_lng"]),
                ],
                "start_form": c0.get("urban_form", "unknown"),
                "end_form": c1.get("urban_form", "unknown"),
            })
        if len(cells_sorted) >= 2:
            paths.append({
                "name": "高密度-低密度对照",
                "coords": [
                    (cells_sorted[0]["center_lat"], cells_sorted[0]["center_lng"]),
                    (cells_sorted[-1]["center_lat"], cells_sorted[-1]["center_lng"]),
                ],
                "start_form": cells_sorted[0].get("urban_form", "unknown"),
                "end_form": cells_sorted[-1].get("urban_form", "unknown"),
            })
        return paths


# =============================================================================
# 主验证器 — orchestrates all components
# =============================================================================
def validate_world_model(
    sv_csv: str,
    network_stats: str,
    output_dir: str,
    grid_size_deg: float = 0.003,
) -> dict:
    """
    入口函数：运行完整的世界模型验证流程。
    Parameters
    ----------
    sv_csv : str — VLM 分割结果 CSV 路径
    network_stats : str — 路网统计 JSON 路径
    output_dir : str — 输出目录
    grid_size_deg : float — 网格分辨率（度）
    Returns
    -------
    dict — 验证摘要
    """
    log.info(f"\n{'#' * 60}")
    log.info("# 世界模型验证器")
    log.info(f"# {'#' * 53}")
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    log.info(f"[读取] 街景分割数据: {sv_csv}")
    sv_df = pd.read_csv(sv_csv, low_memory=False)
    log.info(f"[读取] 路网统计: {network_stats}")
    with open(network_stats, encoding="utf-8") as f:
        network_stats_dict = json.load(f)
    log.info(f"[Step 1/5] 构建物理占用网格...")
    grid_occ = GridOccupancy(grid_size_deg=grid_size_deg)
    physical_occ = grid_occ.compute_physical_occupancy(sv_df)
    digital_occ = grid_occ.compute_digital_occupancy_from_network(network_stats_dict)
    (out_path / "physical_occupancy.json").write_text(
        json.dumps(physical_occ, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_path / "digital_occupancy.json").write_text(
        json.dumps(digital_occ, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info(f"[写入] {out_path}/physical_occupancy.json")
    log.info(f"[写入] {out_path}/digital_occupancy.json")

    log.info(f"[Step 2/5] 构建特征嵌入并对比...")
    emb_grid = EmbeddingGrid()
    embedding_result = emb_grid.compute_embedding_comparison(
        physical_occ.get("cells", [])
    )
    (out_path / "embedding_comparison.json").write_text(
        json.dumps(embedding_result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info(f"[写入] {out_path}/embedding_comparison.json")

    log.info(f"[Step 3/5] 计算规划偏差路径...")
    planner = PlanningGap(physical_occ, embedding_result)
    planning_gap = planner.compute_planning_gap()
    (out_path / "planning_gap.json").write_text(
        json.dumps(planning_gap, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info(f"[写入] {out_path}/planning_gap.json")

    log.info(f"[Step 4/5] 生成 BEV 3D 体素表征...")
    bev_voxel = grid_occ.compute_bev_occupancy_layers(sv_df)
    # 注入数字占用信息
    for cell in bev_voxel.get("cells", []):
        cell["digital_occ"] = digital_occ.get("mean_p_occ", 0.5)
    (out_path / "bev_voxel_3d.json").write_text(
        json.dumps(bev_voxel, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info(f"[写入] {out_path}/bev_voxel_3d.json")

    log.info(f"[Step 5/5] 生成道路几何数据...")
    road_geometry = grid_occ.compute_road_geometry(
        network_stats=network_stats_dict,
        sv_df=sv_df
    )
    (out_path / "road_geometry.json").write_text(
        json.dumps(road_geometry, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info(f"[写入] {out_path}/road_geometry.json")

    log.info(f"[生成] 验证摘要...")
    cos_sim = embedding_result["global_cosine_sim"]
    eucl_dev = embedding_result["global_euclidean_dev"]
    mean_gap = planning_gap["mean_gap_score"]
    phys_occ_mean = physical_occ["occupancy_stats"]["mean_p_occ"]
    dig_occ_mean = digital_occ["mean_p_occ"]
    illusion_hypothesis_score = (
        0.30 * (1 - cos_sim)
        + 0.25 * np.clip(eucl_dev, 0, 1)
        + 0.25 * mean_gap
        + 0.20 * abs(phys_occ_mean - dig_occ_mean)
    )
    illusion_hypothesis_score = round(float(np.clip(illusion_hypothesis_score, 0, 1)), 4)

    # 计算体素统计
    bev_stats = bev_voxel.get("layer_stats", {})
    summary = {
        "generated_at": str(pd.Timestamp.now()),
        "data_summary": {
            "sv_records": len(sv_df),
            "sv_unique_points": sv_df["point_key"].nunique() if "point_key" in sv_df.columns else len(sv_df),
            "grid_cells": physical_occ["total_cells"],
            "grid_size_deg": grid_size_deg,
            "osm_edges": network_stats_dict.get("total_edges", 0),
            "osm_nodes": network_stats_dict.get("total_nodes", 0),
            "bev_voxel_cells": bev_voxel.get("total_cells", 0),
            "road_segments": road_geometry.get("total_segments", 0),
        },
        "physical_occupancy": {
            "mean_p_occ": physical_occ["occupancy_stats"]["mean_p_occ"],
            "high_occ_cells": physical_occ["occupancy_stats"]["high_occ_cells"],
            "low_occ_cells": physical_occ["occupancy_stats"]["low_occ_cells"],
        },
        "bev_3d_occupancy": {
            "mean_occ_ground": bev_stats.get("mean_occ_ground", 0),
            "mean_occ_pedestrian": bev_stats.get("mean_occ_pedestrian", 0),
            "mean_occ_vehicle": bev_stats.get("mean_occ_vehicle", 0),
            "mean_occ_canopy": bev_stats.get("mean_occ_canopy", 0),
            "mean_total_occupancy": bev_stats.get("mean_total_occupancy", 0),
        },
        "digital_occupancy": {
            "mean_p_occ": digital_occ["mean_p_occ"],
        },
        "occupancy_gap": {
            "physical_vs_digital": round(abs(phys_occ_mean - dig_occ_mean), 4),
            "interpretation": (
                "正值表示数字模型低估了物理通行障碍（更乐观），"
                "负值表示数字模型高估了通行难度"
            ),
        },
        "embedding_comparison": {
            "global_cosine_sim": cos_sim,
            "global_euclidean_dev": eucl_dev,
            "n_hotspots": embedding_result["n_hotspots"],
        },
        "planning_gap": {
            "mean_gap_score": mean_gap,
            "max_gap_score": planning_gap["max_gap_score"],
            "gap_levels": planning_gap["gap_levels"],
        },
        "illusion_hypothesis_score": illusion_hypothesis_score,
        "hypothesis_interpretation": _interpret_hypothesis(illusion_hypothesis_score),
        "files": {
            "physical_occupancy": str(out_path / "physical_occupancy.json"),
            "digital_occupancy": str(out_path / "digital_occupancy.json"),
            "embedding_comparison": str(out_path / "embedding_comparison.json"),
            "planning_gap": str(out_path / "planning_gap.json"),
            "bev_voxel_3d": str(out_path / "bev_voxel_3d.json"),
            "road_geometry": str(out_path / "road_geometry.json"),
        },
    }
    (out_path / "world_model_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info(f"[写入] {out_path}/world_model_summary.json")
    log.info(f"\n{'=' * 60}")
    log.info(f"# 世界模型验证摘要")
    log.info(f"  幻觉假说分: {summary['illusion_hypothesis_score']:.4f}")
    log.info(f"  {summary['hypothesis_interpretation']}")
    log.info(f"  嵌入余弦相似度: {cos_sim:.4f}  (1=完美, 0=完全相反)")
    log.info(f"  嵌入偏差: {eucl_dev:.4f}")
    log.info(f"  平均规划偏差: {mean_gap:.4f}")
    log.info(f"  物理占用均值: {phys_occ_mean:.4f}  数字占用均值: {dig_occ_mean:.4f}")
    log.info(f"  高占格: {physical_occ['occupancy_stats']['high_occ_cells']} / "
             f"{physical_occ['total_cells']} 格")
    log.info(f"  BEV 3D体素: {bev_voxel.get('total_cells', 0)} 格")
    log.info(f"  道路几何: {road_geometry.get('total_segments', 0)} 段")
    log.info(f"{'=' * 60}")
    return summary


def _interpret_hypothesis(score: float) -> str:
    if score < 0.15:
        return "低幻觉：数字规划与物理现实高度吻合"
    elif score < 0.30:
        return "中幻觉：存在系统性偏差，需关注特定区域"
    elif score < 0.50:
        return "高幻觉：数字模型显著低估了物理通行障碍"
    else:
        return "极高幻觉：规划与现实严重脱节，建议重新评估规划模型"


# =============================================================================
# CLI 入口
# =============================================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="世界模型验证器")
    parser.add_argument("--sv-csv", required=True,
                        help="VLM 分割结果 CSV 路径")
    parser.add_argument("--network-stats", required=True,
                        help="路网统计 JSON 路径")
    parser.add_argument("--output", default="world_model_output",
                        help="输出目录")
    parser.add_argument("--grid-size", type=float, default=0.003,
                        help="网格分辨率（度）")
    args = parser.parse_args()
    result = validate_world_model(
        args.sv_csv, args.network_stats, args.output, args.grid_size
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
