# -*- coding: utf-8 -*-
"""
Generate de-cluttered layered maps for the Nanshan accessibility illusion study.

The previous single composite map is useful as a data inventory, but too dense
for interpretation. This script redraws the same real layers as a sequence:
  01 base road hierarchy
  02 POI service supply
  03 walkable route + street-view sampling
  04 community/AOI SAII risk
  05 low-density synthesis
  06 four-panel layout
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import geopandas as gpd
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import matplotlib.patheffects as pe

import redraw_total_gis_map as total


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "projects" / "15min-urban-accessibility"
OUT_DIR = PROJECT / "paper" / "figures" / "layered_total_map"
OUT_DIR.mkdir(parents=True, exist_ok=True)


ROAD_GROUPS = {
    "主干/快速路": {
        "classes": ["motorway", "trunk", "primary", "primary_link", "trunk_link"],
        "color": "#273142",
        "lw": 1.50,
        "alpha": 0.90,
    },
    "次干/支路": {
        "classes": ["secondary", "secondary_link", "tertiary", "tertiary_link"],
        "color": "#5b6472",
        "lw": 0.95,
        "alpha": 0.82,
    },
    "居住/服务道路": {
        "classes": ["residential", "living_street", "unclassified", "service"],
        "color": "#9aa2af",
        "lw": 0.42,
        "alpha": 0.58,
    },
    "步行/台阶/绿道": {
        "classes": ["footway", "pedestrian", "path", "steps", "cycleway"],
        "color": "#7c3aed",
        "lw": 0.38,
        "alpha": 0.78,
    },
}


POI_RULES = {
    "医疗": {"cats": ["医疗保健"], "color": "#dc2626", "marker": "P"},
    "教育": {"cats": ["教育培训"], "color": "#2563eb", "marker": "s"},
    "交通": {"cats": ["交通设施"], "color": "#0891b2", "marker": "^"},
    "购物": {"cats": ["购物服务"], "color": "#9333ea", "marker": "D"},
    "餐饮": {"cats": ["餐饮服务"], "color": "#f97316", "marker": "o"},
    "公共/生活": {"cats": ["公共设施", "生活服务"], "color": "#16a34a", "marker": "h"},
}


def load_layers():
    total.choose_font()
    boundary = total.read_boundary()
    boundary_geom = boundary.geometry.unary_union
    roads = total.read_roads(boundary_geom)
    buildings = total.read_buildings(boundary_geom)
    poi = total.read_pois(boundary_geom)
    comm = total.read_communities(boundary_geom)
    route_edges = total.read_route_edges(boundary_geom)
    traj = total.read_trajectory(boundary_geom)
    return boundary, roads, buildings, poi, comm, route_edges, traj


def main_bounds(roads: gpd.GeoDataFrame):
    xmin, ymin, xmax, ymax = roads.total_bounds
    pad_x = (xmax - xmin) * 0.035
    pad_y = (ymax - ymin) * 0.035
    return xmin - pad_x, ymin - pad_y, xmax + pad_x, ymax + pad_y


def setup_map(title: str, subtitle: str, figsize=(11.8, 8.2)):
    fig, ax = plt.subplots(figsize=figsize, dpi=300)
    fig.subplots_adjust(left=0.045, right=0.985, top=0.86, bottom=0.065)
    ax.set_facecolor("#f8fafc")
    ax.set_aspect("equal")
    fig.text(0.045, 0.955, title, ha="left", va="top", fontsize=16.2, fontweight="bold", color="#111827")
    fig.text(0.045, 0.905, subtitle, ha="left", va="top", fontsize=9.6, color="#374151")
    return fig, ax


def finish_map(fig, ax, boundary, bounds, note: str | None = None):
    ax.set_xlim(bounds[0], bounds[2])
    ax.set_ylim(bounds[1], bounds[3])
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#111827")
        spine.set_linewidth(0.8)
    total.add_locator_inset(ax, boundary, bounds)
    total.add_north_arrow(ax)
    total.add_scale_bar(ax, length_km=5)
    if note:
        fig.text(0.045, 0.025, note, ha="left", va="bottom", fontsize=7.6, color="#4b5563")


def save(fig, stem: str):
    png = OUT_DIR / f"{stem}.png"
    pdf = OUT_DIR / f"{stem}.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight", pad_inches=0.10)
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.10)
    plt.close(fig)
    print(f"saved: {png}")
    print(f"saved: {pdf}")


def draw_boundary(ax, boundary):
    boundary.plot(ax=ax, facecolor="#fff7d6", edgecolor="#111827", linewidth=1.15, alpha=0.55, zorder=1)
    boundary.boundary.plot(ax=ax, color="#111827", linewidth=1.15, zorder=20)


def draw_buildings(ax, buildings, alpha=0.20):
    if buildings.empty:
        return
    classes = {
        "住宅建筑": (["apartments", "residential", "house", "detached", "dormitory"], "#d1d5db"),
        "商业办公": (["commercial", "retail", "office"], "#f1c27d"),
        "产业仓储": (["industrial", "warehouse"], "#c7d2fe"),
        "公共建筑": (["public", "government"], "#bbf7d0"),
    }
    plotted = set()
    for _, (items, color) in classes.items():
        sub = buildings[buildings["building"].astype(str).str.lower().isin(items)]
        if not sub.empty:
            sub.plot(ax=ax, facecolor=color, edgecolor="none", alpha=alpha, zorder=2)
            plotted.update(sub.index)
    other = buildings.drop(index=list(plotted), errors="ignore")
    if not other.empty:
        other.plot(ax=ax, facecolor="#e5e7eb", edgecolor="none", alpha=alpha * 0.65, zorder=1)


def draw_roads(ax, roads, mode="full", zorder=8):
    if mode == "light":
        roads.plot(ax=ax, color="#cbd5e1", linewidth=0.22, alpha=0.52, zorder=zorder)
        return
    if mode == "major":
        groups = ["主干/快速路", "次干/支路"]
    else:
        groups = ROAD_GROUPS.keys()
    for label in groups:
        cfg = ROAD_GROUPS[label]
        sub = roads[roads["fclass"].isin(cfg["classes"])]
        if not sub.empty:
            sub.plot(ax=ax, color=cfg["color"], linewidth=cfg["lw"], alpha=cfg["alpha"], zorder=zorder)


def draw_road_labels(ax, roads, max_labels=10):
    major = ["trunk", "primary", "secondary", "tertiary"]
    named = roads[roads["fclass"].isin(major) & roads["name"].notna()].copy()
    if named.empty:
        return
    named["plot_len"] = named.geometry.length
    chosen = []
    used = []
    for name in named.groupby("name")["plot_len"].sum().sort_values(ascending=False).head(max_labels * 3).index:
        geom = named[named["name"] == name].sort_values("plot_len", ascending=False).iloc[0].geometry
        point = geom.interpolate(0.5, normalized=True)
        if any(point.distance(existing) < 3000 for existing in used):
            continue
        chosen.append((str(name)[:11], point))
        used.append(point)
        if len(chosen) >= max_labels:
            break
    for name, point in chosen:
        ax.text(
            point.x,
            point.y,
            name,
            fontsize=8.0,
            color="#374151",
            ha="center",
            va="center",
            zorder=25,
            path_effects=[pe.withStroke(linewidth=3.2, foreground="white")],
        )


def road_counts(roads):
    counts = {}
    for label, cfg in ROAD_GROUPS.items():
        counts[label] = int(roads["fclass"].isin(cfg["classes"]).sum())
    return counts


def add_road_legend(ax, roads):
    counts = road_counts(roads)
    handles = [
        Line2D(
            [],
            [],
            color=cfg["color"],
            lw=3.0,
            alpha=cfg["alpha"],
            label=f"{label}  {counts[label]:,}条",
        )
        for label, cfg in ROAD_GROUPS.items()
    ]
    ax.legend(
        handles=handles,
        title="道路层级",
        loc="lower right",
        frameon=True,
        framealpha=0.94,
        facecolor="white",
        edgecolor="#d1d5db",
        fontsize=8.0,
        title_fontsize=8.8,
    )


def sample_pois(poi, per_group=850):
    rng = np.random.default_rng(20260602)
    samples = {}
    counts = {}
    for label, cfg in POI_RULES.items():
        sub = poi[poi["facility_type"].isin(cfg["cats"])].copy()
        counts[label] = int(len(sub))
        if len(sub) > per_group:
            sub = sub.iloc[rng.choice(len(sub), size=per_group, replace=False)]
        samples[label] = sub
    return samples, counts


def draw_poi_samples(ax, poi, per_group=850, size=15, alpha=0.72):
    samples, counts = sample_pois(poi, per_group=per_group)
    for label, sub in samples.items():
        if sub.empty:
            continue
        cfg = POI_RULES[label]
        ax.scatter(
            sub.geometry.x,
            sub.geometry.y,
            s=size,
            marker=cfg["marker"],
            color=cfg["color"],
            edgecolors="white",
            linewidth=0.25,
            alpha=alpha,
            zorder=14,
        )
    return counts


def add_poi_legend(ax, counts, loc="lower right"):
    handles = [
        Line2D(
            [],
            [],
            linestyle="None",
            marker=cfg["marker"],
            markersize=7,
            markerfacecolor=cfg["color"],
            markeredgecolor="white",
            label=f"{label}  {counts.get(label, 0):,}个",
        )
        for label, cfg in POI_RULES.items()
    ]
    ax.legend(
        handles=handles,
        title="POI服务类型",
        loc=loc,
        frameon=True,
        framealpha=0.94,
        facecolor="white",
        edgecolor="#d1d5db",
        fontsize=8.0,
        title_fontsize=8.8,
    )


def draw_route_layers(ax, route_edges, traj, route_mode="full"):
    pedestrian = {"footway", "pedestrian", "path", "steps", "cycleway", "living_street"}
    ped = route_edges[route_edges["fclass"].isin(pedestrian)]
    other = route_edges[~route_edges["fclass"].isin(pedestrian)]
    if route_mode == "light":
        if not route_edges.empty:
            route_edges.plot(ax=ax, color="#67e8f9", linewidth=0.24, alpha=0.23, zorder=8)
    else:
        if not other.empty:
            other.plot(ax=ax, color="#67e8f9", linewidth=0.32, alpha=0.32, zorder=8)
        if not ped.empty:
            ped.plot(ax=ax, color="#0891b2", linewidth=0.55, alpha=0.58, zorder=9)
    if len(traj) > 13000:
        sample = traj.iloc[:: max(1, math.ceil(len(traj) / 13000))].copy()
    else:
        sample = traj.copy()
    ax.scatter(sample.geometry.x, sample.geometry.y, s=2.2, color="#f59e0b", alpha=0.46, linewidth=0, zorder=12)
    return sample


def add_route_legend(ax, route_edges, traj):
    pedestrian = {"footway", "pedestrian", "path", "steps", "cycleway", "living_street"}
    ped_n = int(route_edges["fclass"].isin(pedestrian).sum())
    other_n = int((~route_edges["fclass"].isin(pedestrian)).sum())
    handles = [
        Line2D([], [], color="#0891b2", lw=3.0, label=f"慢行/步行边  {ped_n:,}条"),
        Line2D([], [], color="#67e8f9", lw=3.0, label=f"其他可行边  {other_n:,}条"),
        Line2D([], [], color="#f59e0b", marker="o", linestyle="None", markersize=5, label=f"街景20m采样  {len(traj):,}点"),
    ]
    ax.legend(
        handles=handles,
        title="路径证据层",
        loc="lower right",
        frameon=True,
        framealpha=0.94,
        facecolor="white",
        edgecolor="#d1d5db",
        fontsize=8.0,
        title_fontsize=8.8,
    )


def draw_saii(ax, comm, max_size=120, label_top=8):
    sizes = total.normalize_sizes(comm["population"], 18, max_size)
    norm = mcolors.Normalize(vmin=comm["SAII"].quantile(0.02), vmax=comm["SAII"].quantile(0.98))
    ax.scatter(
        comm.geometry.x,
        comm.geometry.y,
        c=comm["SAII"],
        cmap="YlOrRd",
        norm=norm,
        s=sizes,
        alpha=0.84,
        edgecolors="#111827",
        linewidth=0.32,
        zorder=18,
    )
    high = comm.sort_values("SAII", ascending=False).head(label_top)
    offsets = [(8, 7), (8, -12), (-8, 7), (-8, -12), (10, 14), (-10, 14), (10, -18), (-10, -18)]
    for i, ((_, row), offset) in enumerate(zip(high.iterrows(), offsets), start=1):
        x, y = row.geometry.x, row.geometry.y
        ax.scatter([x], [y], s=max_size * 1.45, facecolor="none", edgecolor="#111827", linewidth=1.1, zorder=23)
        label = str(row.get("housetitle") or f"社区{int(row['community_id'])}")
        if len(label) > 8:
            label = label[:8]
        ax.annotate(
            f"{i}. {label}",
            xy=(x, y),
            xytext=offset,
            textcoords="offset points",
            fontsize=7.8,
            fontweight="bold",
            color="#111827",
            zorder=26,
            path_effects=[pe.withStroke(linewidth=3.2, foreground="white")],
        )
    return norm


def add_saii_colorbar(fig, ax, norm, label="SAII可达性幻觉强度"):
    box = ax.get_position()
    cax = fig.add_axes([box.x0 + box.width * 0.48, box.y0 + box.height * 0.035, box.width * 0.32, 0.018])
    sm = cm.ScalarMappable(norm=norm, cmap=cm.get_cmap("YlOrRd"))
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cax, orientation="horizontal")
    cbar.set_label(label, fontsize=8.2, labelpad=2)
    cbar.ax.tick_params(labelsize=7.5, length=2)


def add_population_legend(ax, comm, max_size=120):
    pop_levels = [comm["population"].quantile(q) for q in [0.25, 0.5, 0.9]]
    sizes = total.normalize_sizes(pd.Series(pop_levels), 18, max_size)
    handles = [
        Line2D(
            [],
            [],
            linestyle="None",
            marker="o",
            markersize=math.sqrt(size) / 1.35,
            markerfacecolor="#f97316",
            markeredgecolor="#111827",
            alpha=0.84,
            label=f"{int(pop):,}人",
        )
        for pop, size in zip(pop_levels, sizes)
    ]
    ax.legend(
        handles=handles,
        title="社区人口规模",
        loc="lower right",
        frameon=True,
        framealpha=0.94,
        facecolor="white",
        edgecolor="#d1d5db",
        fontsize=8.0,
        title_fontsize=8.8,
    )


def figure_01_base(boundary, roads, buildings, bounds):
    fig, ax = setup_map(
        "图层01 研究范围与道路层级",
        "先把空间骨架讲清楚：区界、建筑/AOI、主干路、居住服务道路与慢行设施分层呈现。",
    )
    draw_boundary(ax, boundary)
    draw_buildings(ax, buildings, alpha=0.18)
    draw_roads(ax, roads, mode="full")
    draw_road_labels(ax, roads, max_labels=12)
    add_road_legend(ax, roads)
    finish_map(fig, ax, boundary, bounds, "说明：紫色线表示步行道、台阶、绿道与自行车道，是后续慢行可达性分析的基础。")
    save(fig, "fig_total_layer_01_base_road_hierarchy")


def figure_02_poi(boundary, roads, poi, bounds):
    fig, ax = setup_map(
        "图层02 POI服务供给与热点",
        "把服务供给单独拆出：底层为POI密度热区，上层仅抽样显示主要设施类型，避免点位互相遮挡。",
    )
    draw_boundary(ax, boundary)
    draw_roads(ax, roads, mode="light", zorder=4)
    hb = ax.hexbin(
        poi.geometry.x,
        poi.geometry.y,
        gridsize=78,
        mincnt=1,
        cmap=mcolors.LinearSegmentedColormap.from_list("poi_density", ["#fff7ed", "#fdba74", "#ea580c"]),
        linewidths=0,
        alpha=0.56,
        zorder=5,
    )
    counts = draw_poi_samples(ax, poi, per_group=720, size=13, alpha=0.74)
    add_poi_legend(ax, counts)
    box = ax.get_position()
    cax = fig.add_axes([box.x0 + box.width * 0.48, box.y0 + box.height * 0.035, box.width * 0.31, 0.018])
    cbar = fig.colorbar(hb, cax=cax, orientation="horizontal")
    cbar.set_label("POI网格计数密度", fontsize=8.2, labelpad=2)
    cbar.ax.tick_params(labelsize=7.5, length=2)
    finish_map(fig, ax, boundary, bounds, "说明：密度越高代表服务供给越集中；不同颜色和符号表示医疗、教育、交通、购物、餐饮与公共/生活服务。")
    save(fig, "fig_total_layer_02_poi_service_supply")


def figure_03_routes(boundary, roads, route_edges, traj, bounds):
    fig, ax = setup_map(
        "图层03 步行路由网络与街景采样轨迹",
        "把路径证据单独呈现：青色为可步行路由图，橙色为20m间隔街景采样点，用于解释模型观测覆盖。",
    )
    draw_boundary(ax, boundary)
    draw_roads(ax, roads, mode="major", zorder=5)
    sample = draw_route_layers(ax, route_edges, traj)
    add_route_legend(ax, route_edges, traj)
    draw_road_labels(ax, roads, max_labels=9)
    finish_map(fig, ax, boundary, bounds, f"说明：本图实际绘制街景采样点 {len(sample):,} 个作为可视化抽样，完整采样点数量见图例。")
    save(fig, "fig_total_layer_03_walk_route_streetview_sampling")


def figure_04_saii(boundary, roads, buildings, poi, comm, bounds):
    fig, ax = setup_map(
        "图层04 社区/AOI与SAII时间贫困风险",
        "把解释变量聚焦到居住单元：社区点按人口缩放、按SAII着色，黑圈标记高风险社区。",
    )
    draw_boundary(ax, boundary)
    draw_buildings(ax, buildings, alpha=0.16)
    draw_roads(ax, roads, mode="light", zorder=5)
    # Use density only here; full POI symbols would obscure community risk.
    ax.hexbin(
        poi.geometry.x,
        poi.geometry.y,
        gridsize=74,
        mincnt=1,
        cmap=mcolors.LinearSegmentedColormap.from_list("poi_soft", ["#ffffff00", "#fbbf24", "#fb923c"]),
        linewidths=0,
        alpha=0.22,
        zorder=6,
    )
    norm = draw_saii(ax, comm, max_size=122, label_top=5)
    add_saii_colorbar(fig, ax, norm, "SAII可达性幻觉强度（昼夜服务可达性落差）")
    add_population_legend(ax, comm, max_size=122)
    finish_map(fig, ax, boundary, bounds, "说明：若高SAII社区与高POI密度共存，说明服务虽然空间上接近，但夜间、慢行或环境阻抗使实际到达成本上升。")
    save(fig, "fig_total_layer_04_community_aoi_saii_risk")


def figure_05_synthesis(boundary, roads, poi, route_edges, traj, comm, bounds):
    fig, ax = setup_map(
        "图层05 低密度综合判读图",
        "只保留必要符号：道路骨架、POI热度、街景轨迹和高风险社区，用作论文中的总体索引图。",
    )
    draw_boundary(ax, boundary)
    draw_roads(ax, roads, mode="major", zorder=6)
    ax.hexbin(
        poi.geometry.x,
        poi.geometry.y,
        gridsize=70,
        mincnt=1,
        cmap=mcolors.LinearSegmentedColormap.from_list("poi_summary", ["#fff7ed", "#fdba74", "#ea580c"]),
        linewidths=0,
        alpha=0.32,
        zorder=4,
    )
    draw_route_layers(ax, route_edges, traj, route_mode="light")
    high = comm.sort_values("SAII", ascending=False).head(40).copy()
    norm = draw_saii(ax, high, max_size=115, label_top=5)
    add_saii_colorbar(fig, ax, norm, "高风险社区SAII强度")
    finish_map(fig, ax, boundary, bounds, "说明：该图用于总览，不展示全部社区点和全部POI符号，避免再次形成视觉拥挤。")
    save(fig, "fig_total_layer_05_low_density_synthesis")


def figure_06_panel(boundary, roads, buildings, poi, comm, route_edges, traj, bounds):
    fig, axes = plt.subplots(2, 2, figsize=(15.8, 11.0), dpi=300)
    fig.subplots_adjust(left=0.035, right=0.985, top=0.835, bottom=0.05, wspace=0.05, hspace=0.18)
    fig.text(0.035, 0.965, "南山区15分钟城市时间贫困：四类证据分层拼版", fontsize=17, fontweight="bold", ha="left", va="top", color="#111827")
    fig.text(0.035, 0.928, "从空间骨架、服务供给、路径观测到社区风险逐层展开，减少总图混乱与文字重叠。", fontsize=9.8, ha="left", va="top", color="#374151")

    titles = [
        "A. 道路与建筑/AOI",
        "B. POI服务供给",
        "C. 步行路由与街景采样",
        "D. 社区SAII风险",
    ]
    for ax, title in zip(axes.ravel(), titles):
        ax.set_facecolor("#f8fafc")
        ax.set_aspect("equal")
        ax.set_xlim(bounds[0], bounds[2])
        ax.set_ylim(bounds[1], bounds[3])
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(title, loc="left", fontsize=10.6, fontweight="bold", color="#111827", pad=4)
        for spine in ax.spines.values():
            spine.set_color("#111827")
            spine.set_linewidth(0.75)
        draw_boundary(ax, boundary)

    ax = axes[0, 0]
    draw_buildings(ax, buildings, alpha=0.16)
    draw_roads(ax, roads, mode="full")
    add_road_legend(ax, roads)

    ax = axes[0, 1]
    draw_roads(ax, roads, mode="light", zorder=4)
    ax.hexbin(
        poi.geometry.x,
        poi.geometry.y,
        gridsize=68,
        mincnt=1,
        cmap=mcolors.LinearSegmentedColormap.from_list("poi_panel", ["#fff7ed", "#fdba74", "#ea580c"]),
        linewidths=0,
        alpha=0.50,
        zorder=5,
    )
    counts = draw_poi_samples(ax, poi, per_group=420, size=10, alpha=0.70)
    add_poi_legend(ax, counts, loc="lower right")

    ax = axes[1, 0]
    draw_roads(ax, roads, mode="major", zorder=5)
    draw_route_layers(ax, route_edges, traj)
    add_route_legend(ax, route_edges, traj)

    ax = axes[1, 1]
    draw_buildings(ax, buildings, alpha=0.13)
    draw_roads(ax, roads, mode="light", zorder=4)
    norm = draw_saii(ax, comm, max_size=82, label_top=5)
    box = ax.get_position()
    cax = fig.add_axes([box.x0 + box.width * 0.46, box.y0 + box.height * 0.04, box.width * 0.34, 0.014])
    sm = cm.ScalarMappable(norm=norm, cmap=cm.get_cmap("YlOrRd"))
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cax, orientation="horizontal")
    cbar.set_label("SAII", fontsize=7.8, labelpad=1)
    cbar.ax.tick_params(labelsize=7.0, length=2)

    save(fig, "fig_total_layer_06_four_panel_evidence_chain")


def main():
    boundary, roads, buildings, poi, comm, route_edges, traj = load_layers()
    bounds = main_bounds(roads)

    print("Loaded layers:")
    print(f"  roads={len(roads):,}, route_edges={len(route_edges):,}, trajectory={len(traj):,}")
    print(f"  pois={len(poi):,}, communities={len(comm):,}, buildings={len(buildings):,}")

    figure_01_base(boundary, roads, buildings, bounds)
    figure_02_poi(boundary, roads, poi, bounds)
    figure_03_routes(boundary, roads, route_edges, traj, bounds)
    figure_04_saii(boundary, roads, buildings, poi, comm, bounds)
    figure_05_synthesis(boundary, roads, poi, route_edges, traj, comm, bounds)
    figure_06_panel(boundary, roads, buildings, poi, comm, route_edges, traj, bounds)

    summary = {
        "outputs": sorted(str(p.relative_to(ROOT)) for p in OUT_DIR.glob("*.png")),
        "layers": {
            "roads": int(len(roads)),
            "route_edges": int(len(route_edges)),
            "trajectory": int(len(traj)),
            "pois": int(len(poi)),
            "communities": int(len(comm)),
            "buildings": int(len(buildings)),
        },
        "road_counts": road_counts(roads),
        "poi_counts": sample_pois(poi, per_group=1_000_000)[1],
        "main_bounds_epsg3857": [float(v) for v in bounds],
    }
    out_json = OUT_DIR / "layered_total_map_summary.json"
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {out_json}")


if __name__ == "__main__":
    main()
