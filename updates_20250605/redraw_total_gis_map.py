# -*- coding: utf-8 -*-
"""
Redraw the project-wide GIS overview map with real project layers.

Outputs:
  - projects/15min-urban-accessibility/paper/figures/fig_total_time_poverty_map_optimized.png
  - projects/15min-urban-accessibility/paper/figures/fig_total_time_poverty_map_optimized.pdf
  - projects/15min-urban-accessibility/paper/figures/fig_total_time_poverty_map_optimized_layers.json
"""

from __future__ import annotations

import json
import math
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Rectangle
from shapely.geometry import LineString, Point

warnings.filterwarnings("ignore")


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "projects" / "15min-urban-accessibility"
OUT_DIR = PROJECT / "paper" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_PNG = OUT_DIR / "fig_total_time_poverty_map_optimized.png"
OUT_PDF = OUT_DIR / "fig_total_time_poverty_map_optimized.pdf"
OUT_JSON = OUT_DIR / "fig_total_time_poverty_map_optimized_layers.json"

TARGET_CRS = "EPSG:3857"


def choose_font() -> None:
    font_candidates = [
        ROOT / "C:/Windows/Fonts/msyh.ttc",
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/STSONG.TTF"),
    ]
    for font_path in font_candidates:
        if font_path.exists():
            mpl.font_manager.fontManager.addfont(str(font_path))
            name = mpl.font_manager.FontProperties(fname=str(font_path)).get_name()
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams.update(
        {
            "font.size": 9.5,
            "axes.titleweight": "bold",
            "axes.edgecolor": "#1f2937",
            "axes.linewidth": 0.8,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
        }
    )


def first_file(pattern: str) -> Path | None:
    matches = sorted(ROOT.rglob(pattern), key=lambda p: (len(str(p)), str(p)))
    return matches[0] if matches else None


def read_boundary() -> gpd.GeoDataFrame:
    boundary_path = None
    gdata2 = ROOT / "data" / "GData2"
    if gdata2.exists():
        for candidate in gdata2.glob("*.shp"):
            if "New" in candidate.stem:
                boundary_path = candidate
                break

    if boundary_path is None:
        for candidate in ROOT.rglob("*.shp"):
            if "GData2" in str(candidate) and "New" in candidate.stem:
                boundary_path = candidate
                break

    if boundary_path is None:
        raise FileNotFoundError("No district boundary shapefile found under data/GData2.")

    boundary = gpd.read_file(boundary_path, engine="pyogrio")
    if boundary.crs is None:
        boundary = boundary.set_crs(TARGET_CRS)
    boundary = boundary.to_crs(TARGET_CRS)
    nanshan = boundary[boundary["sname"].astype(str).str.contains("南山", na=False)].copy()
    if nanshan.empty:
        raise RuntimeError(f"Cannot find 南山区 in {boundary_path}.")
    nanshan["layer_source"] = str(boundary_path.relative_to(ROOT))
    return nanshan


def read_roads(boundary_geom) -> gpd.GeoDataFrame:
    path = PROJECT / "osm_data" / "nanshan_road_network.shp"
    roads = gpd.read_file(path, engine="pyogrio")
    roads = roads[roads.geometry.notna()].copy()
    roads = roads.to_crs(TARGET_CRS)
    roads = roads[roads.intersects(boundary_geom)].copy()
    return roads


def read_buildings(boundary_geom) -> gpd.GeoDataFrame:
    path = PROJECT / "building_data" / "nanshan_buildings_v2.geojson"
    buildings = gpd.read_file(path, engine="pyogrio")
    buildings = buildings[buildings.geometry.notna()].copy()
    buildings = buildings.to_crs(TARGET_CRS)
    buildings = buildings[buildings.intersects(boundary_geom)].copy()
    return buildings


def read_pois(boundary_geom) -> gpd.GeoDataFrame:
    path = first_file("facility_locations.json")
    if path is None:
        raise FileNotFoundError("facility_locations.json not found.")
    records = json.loads(path.read_text(encoding="utf-8"))
    df = pd.DataFrame(records)
    df = df.dropna(subset=["lon", "lat"]).copy()
    poi = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326",
    ).to_crs(TARGET_CRS)
    poi = poi[poi.within(boundary_geom)].copy()
    poi["layer_source"] = str(path.relative_to(ROOT))
    return poi


def read_communities(boundary_geom) -> gpd.GeoDataFrame:
    access = pd.read_csv(PROJECT / "accessibility_results.csv")
    env = pd.read_csv(PROJECT / "v2_real_data" / "section13_community_accessibility_illusion.csv")
    names = pd.read_csv(PROJECT / "osm_data" / "nanshan_communities_real_population.csv")
    names = names[["id", "housetitle", "shangquan", "address"]].rename(columns={"id": "community_id"})

    keep_env = [
        "community_id",
        "AI_star_elderly",
        "AI_star_wheelchair",
        "WES",
        "EWW",
        "SCR",
        "BFD",
        "illusion_level",
        "building_density_500m",
        "sidewalk_width_proxy",
    ]
    df = access.merge(env[keep_env], on="community_id", how="left").merge(names, on="community_id", how="left")
    comm = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lng"], df["lat"]),
        crs="EPSG:4326",
    ).to_crs(TARGET_CRS)
    comm = comm[comm.within(boundary_geom)].copy()
    return comm


def read_trajectory(boundary_geom) -> gpd.GeoDataFrame:
    path = first_file("trajectory_preview_20m.csv.geojson")
    if path is None:
        raise FileNotFoundError("trajectory_preview_20m.csv.geojson not found.")
    traj = gpd.read_file(path, engine="pyogrio")
    traj = traj[traj.geometry.notna()].copy().to_crs(TARGET_CRS)
    traj = traj[traj.within(boundary_geom)].copy()
    traj["layer_source"] = str(path.relative_to(ROOT))
    return traj


def read_route_edges(boundary_geom) -> gpd.GeoDataFrame:
    node_path = first_file("network_nodes.json")
    edge_path = first_file("network_edges.json")
    if node_path is None or edge_path is None:
        raise FileNotFoundError("network_nodes.json or network_edges.json not found.")

    nodes = json.loads(node_path.read_text(encoding="utf-8"))
    edges = json.loads(edge_path.read_text(encoding="utf-8"))
    node_xy = {
        item["node_id"]: (float(item["lon"]), float(item["lat"]))
        for item in nodes
        if item.get("lon") is not None and item.get("lat") is not None
    }

    rows = []
    geoms = []
    for edge in edges:
        u = edge.get("u")
        v = edge.get("v")
        if u not in node_xy or v not in node_xy:
            continue
        x1, y1 = node_xy[u]
        x2, y2 = node_xy[v]
        if abs(x1 - x2) + abs(y1 - y2) <= 1e-10:
            continue
        rows.append(
            {
                "u": u,
                "v": v,
                "fclass": edge.get("fclass", ""),
                "length_m": edge.get("length_m", np.nan),
                "walk_time_s": edge.get("walk_time_s", np.nan),
            }
        )
        geoms.append(LineString([(x1, y1), (x2, y2)]))

    route_edges = gpd.GeoDataFrame(rows, geometry=geoms, crs="EPSG:4326").to_crs(TARGET_CRS)
    route_edges = route_edges[route_edges.intersects(boundary_geom)].copy()
    route_edges["layer_source"] = str(edge_path.relative_to(ROOT))
    return route_edges


def normalize_sizes(values: pd.Series, min_size=20, max_size=185) -> np.ndarray:
    vals = values.fillna(values.median()).astype(float).to_numpy()
    if vals.size == 0:
        return np.array([])
    lo, hi = np.nanquantile(vals, [0.05, 0.95])
    if hi <= lo:
        return np.full(vals.shape, (min_size + max_size) / 2)
    clipped = np.clip(vals, lo, hi)
    return min_size + (clipped - lo) / (hi - lo) * (max_size - min_size)


def add_north_arrow(ax) -> None:
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    dx = x1 - x0
    dy = y1 - y0
    x = x0 + dx * 0.945
    y = y0 + dy * 0.875
    arrow = FancyArrowPatch(
        (x, y - dy * 0.055),
        (x, y + dy * 0.055),
        arrowstyle="-|>",
        mutation_scale=24,
        linewidth=1.6,
        color="#111827",
        zorder=30,
    )
    ax.add_patch(arrow)
    ax.text(
        x,
        y + dy * 0.07,
        "N",
        ha="center",
        va="bottom",
        fontsize=15,
        fontweight="bold",
        color="#111827",
        zorder=31,
        path_effects=[pe.withStroke(linewidth=3, foreground="white")],
    )


def add_scale_bar(ax, length_km=5) -> None:
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    dx = x1 - x0
    dy = y1 - y0
    length = length_km * 1000
    left = x0 + dx * 0.055
    bottom = y0 + dy * 0.055
    height = dy * 0.012
    segments = 5
    seg = length / segments
    for i in range(segments):
        ax.add_patch(
            Rectangle(
                (left + i * seg, bottom),
                seg,
                height,
                facecolor="#111827" if i % 2 == 0 else "white",
                edgecolor="#111827",
                linewidth=0.8,
                zorder=32,
            )
        )
    ax.text(left, bottom + height * 2.0, "0", ha="center", va="bottom", fontsize=8, zorder=33)
    ax.text(left + length, bottom + height * 2.0, f"{length_km} km", ha="center", va="bottom", fontsize=8, zorder=33)


def plot_road_layers(ax, roads: gpd.GeoDataFrame) -> None:
    road_styles = [
        (["motorway", "trunk", "primary", "primary_link", "trunk_link"], "#3b4252", 1.35, 0.82, "主干/快速路"),
        (["secondary", "secondary_link", "tertiary", "tertiary_link"], "#6b7280", 0.85, 0.78, "次干/支路"),
        (["residential", "living_street", "unclassified", "service"], "#9ca3af", 0.38, 0.54, "居住/服务道路"),
        (["footway", "pedestrian", "path", "steps", "cycleway"], "#7c3aed", 0.36, 0.74, "步行/台阶/绿道"),
    ]
    for classes, color, lw, alpha, _ in road_styles:
        subset = roads[roads["fclass"].isin(classes)]
        if not subset.empty:
            subset.plot(ax=ax, color=color, linewidth=lw, alpha=alpha, zorder=8)


def plot_buildings(ax, buildings: gpd.GeoDataFrame) -> None:
    if buildings.empty:
        return
    group_map = {
        "住宅建筑": ["apartments", "residential", "house", "detached", "dormitory"],
        "商业办公": ["commercial", "retail", "office"],
        "产业仓储": ["industrial", "warehouse"],
        "公共建筑": ["public", "government"],
    }
    colors = {
        "住宅建筑": "#d1d5db",
        "商业办公": "#f1c27d",
        "产业仓储": "#c7d2fe",
        "公共建筑": "#bbf7d0",
    }
    plotted = set()
    for label, classes in group_map.items():
        sub = buildings[buildings["building"].astype(str).str.lower().isin(classes)]
        if not sub.empty:
            sub.plot(ax=ax, facecolor=colors[label], edgecolor="none", alpha=0.27, zorder=2)
            plotted.update(sub.index)
    other = buildings.drop(index=list(plotted), errors="ignore")
    if not other.empty:
        other.plot(ax=ax, facecolor="#e5e7eb", edgecolor="none", alpha=0.18, zorder=1)


def plot_pois(ax, poi: gpd.GeoDataFrame) -> dict[str, int]:
    group_rules = {
        "医疗": ["医疗保健"],
        "教育": ["教育培训"],
        "交通": ["交通设施"],
        "购物": ["购物服务"],
        "餐饮": ["餐饮服务"],
        "公共/生活": ["公共设施", "生活服务"],
    }
    styles = {
        "医疗": ("#dc2626", "P"),
        "教育": ("#2563eb", "s"),
        "交通": ("#0891b2", "^"),
        "购物": ("#9333ea", "D"),
        "餐饮": ("#f97316", "o"),
        "公共/生活": ("#16a34a", "h"),
    }

    if not poi.empty:
        ax.hexbin(
            poi.geometry.x,
            poi.geometry.y,
            gridsize=70,
            mincnt=1,
            cmap=mcolors.LinearSegmentedColormap.from_list("poi_density", ["#fff7ed", "#fdba74", "#ea580c"]),
            linewidths=0,
            alpha=0.22,
            zorder=3,
        )

    counts: dict[str, int] = {}
    rng = np.random.default_rng(20260602)
    for label, cats in group_rules.items():
        sub = poi[poi["facility_type"].isin(cats)].copy()
        counts[label] = int(len(sub))
        if sub.empty:
            continue
        max_n = 520 if label in {"医疗", "教育", "交通", "公共/生活"} else 760
        if len(sub) > max_n:
            sub = sub.iloc[rng.choice(len(sub), size=max_n, replace=False)]
        color, marker = styles[label]
        ax.scatter(
            sub.geometry.x,
            sub.geometry.y,
            s=12,
            marker=marker,
            facecolor=color,
            edgecolor="white",
            linewidth=0.25,
            alpha=0.72,
            zorder=14,
        )
    return counts


def plot_route_edges(ax, route_edges: gpd.GeoDataFrame) -> None:
    if route_edges.empty:
        return
    pedestrian = {"footway", "pedestrian", "path", "steps", "cycleway", "living_street"}
    ped = route_edges[route_edges["fclass"].isin(pedestrian)]
    other = route_edges[~route_edges["fclass"].isin(pedestrian)]
    if not other.empty:
        other.plot(ax=ax, color="#22d3ee", linewidth=0.26, alpha=0.18, zorder=6)
    if not ped.empty:
        ped.plot(ax=ax, color="#06b6d4", linewidth=0.42, alpha=0.38, zorder=7)


def plot_trajectory(ax, traj: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if traj.empty:
        return traj
    max_points = 15000
    if len(traj) > max_points:
        step = max(1, math.ceil(len(traj) / max_points))
        sample = traj.iloc[::step].copy()
    else:
        sample = traj.copy()
    ax.scatter(
        sample.geometry.x,
        sample.geometry.y,
        s=2.1,
        color="#f59e0b",
        alpha=0.42,
        linewidth=0,
        zorder=15,
    )
    return sample


def plot_communities(
    ax,
    comm: gpd.GeoDataFrame,
    min_size: float = 18,
    max_size: float = 105,
    alpha: float = 0.80,
    label_top: int = 8,
) -> None:
    if comm.empty:
        return
    sizes = normalize_sizes(comm["population"], min_size=min_size, max_size=max_size)
    norm = mcolors.Normalize(vmin=comm["SAII"].quantile(0.02), vmax=comm["SAII"].quantile(0.98))
    cmap = cm.get_cmap("YlOrRd")
    ax.scatter(
        comm.geometry.x,
        comm.geometry.y,
        c=comm["SAII"],
        cmap=cmap,
        norm=norm,
        s=sizes,
        alpha=alpha,
        edgecolors="#111827",
        linewidth=0.30,
        zorder=18,
    )

    high = comm.sort_values("SAII", ascending=False).head(label_top).copy()
    for i, (_, row) in enumerate(high.iterrows(), start=1):
        x, y = row.geometry.x, row.geometry.y
        ax.scatter([x], [y], s=max_size * 1.45, facecolor="none", edgecolor="#111827", linewidth=1.1, zorder=21)
        label = str(row.get("housetitle") or f"社区{int(row['community_id'])}")
        if len(label) > 8:
            label = label[:8]
        ax.annotate(
            f"{i}. {label}",
            xy=(x, y),
            xytext=(6, 6),
            textcoords="offset points",
            fontsize=7.4,
            color="#111827",
            fontweight="bold",
            zorder=25,
            path_effects=[pe.withStroke(linewidth=3.2, foreground="white")],
        )


def label_major_roads(ax, roads: gpd.GeoDataFrame) -> None:
    major_classes = ["trunk", "primary", "secondary", "tertiary"]
    named = roads[roads["fclass"].isin(major_classes) & roads["name"].notna()].copy()
    if named.empty:
        return
    named["plot_len"] = named.geometry.length
    top_names = named.groupby("name")["plot_len"].sum().sort_values(ascending=False).head(18).index
    chosen = []
    used = []
    for name in top_names:
        sub = named[named["name"] == name].sort_values("plot_len", ascending=False)
        geom = sub.iloc[0].geometry
        p = geom.interpolate(0.52, normalized=True) if geom.length > 0 else geom.centroid
        if any(p.distance(q) < 2600 for q in used):
            continue
        used.append(p)
        chosen.append((name, p))
    for name, p in chosen[:12]:
        ax.text(
            p.x,
            p.y,
            str(name)[:12],
            fontsize=7.2,
            color="#374151",
            ha="center",
            va="center",
            zorder=24,
            path_effects=[pe.withStroke(linewidth=3.0, foreground="white")],
        )


def add_detail_inset(
    ax_main,
    roads,
    route_edges,
    traj_sample,
    comm,
    poi,
    buildings,
    focus_bounds,
) -> None:
    inset = ax_main.inset_axes([0.026, 0.032, 0.34, 0.31])
    inset.set_facecolor("#fffaf0")
    xmin, ymin, xmax, ymax = focus_bounds
    inset.set_xlim(xmin, xmax)
    inset.set_ylim(ymin, ymax)
    inset.set_aspect("equal")
    for spine in inset.spines.values():
        spine.set_linewidth(1.0)
        spine.set_color("#111827")

    box = Rectangle(
        (xmin, ymin),
        xmax - xmin,
        ymax - ymin,
        facecolor="none",
        edgecolor="#111827",
        linewidth=1.0,
        linestyle="--",
        zorder=35,
    )
    ax_main.add_patch(box)

    clip_rect = (xmin, ymin, xmax, ymax)
    sub_buildings = buildings.cx[xmin:xmax, ymin:ymax]
    if not sub_buildings.empty:
        sub_buildings.plot(ax=inset, facecolor="#d1d5db", edgecolor="none", alpha=0.34, zorder=1)
    plot_route_edges(inset, route_edges.cx[xmin:xmax, ymin:ymax])
    plot_road_layers(inset, roads.cx[xmin:xmax, ymin:ymax])
    if not traj_sample.empty:
        ts = traj_sample.cx[xmin:xmax, ymin:ymax]
        if not ts.empty:
            inset.scatter(ts.geometry.x, ts.geometry.y, s=3.2, color="#f59e0b", alpha=0.55, linewidth=0, zorder=15)
    sub_poi = poi.cx[xmin:xmax, ymin:ymax]
    if len(sub_poi) > 900:
        sub_poi = sub_poi.sample(900, random_state=2026)
    if not sub_poi.empty:
        inset.scatter(sub_poi.geometry.x, sub_poi.geometry.y, s=8, color="#9333ea", alpha=0.38, linewidth=0, zorder=16)
    sub_comm = comm.cx[xmin:xmax, ymin:ymax]
    if not sub_comm.empty:
        inset.scatter(
            sub_comm.geometry.x,
            sub_comm.geometry.y,
            s=normalize_sizes(sub_comm["population"], 26, 115),
            c=sub_comm["SAII"],
            cmap="YlOrRd",
            edgecolors="#111827",
            linewidth=0.35,
            alpha=0.90,
            zorder=19,
        )
    inset.set_xticks([])
    inset.set_yticks([])
    inset.text(
        0.02,
        0.98,
        "核心区放大：科技园-后海-粤海片区",
        transform=inset.transAxes,
        ha="left",
        va="top",
        fontsize=8.4,
        fontweight="bold",
        color="#111827",
        bbox=dict(facecolor="white", edgecolor="#111827", linewidth=0.6, alpha=0.88, pad=2.5),
        zorder=30,
    )
    _ = clip_rect


def add_locator_inset(ax_main, boundary: gpd.GeoDataFrame, main_bounds) -> None:
    inset = ax_main.inset_axes([0.022, 0.73, 0.20, 0.22])
    inset.set_facecolor("#f8fafc")
    boundary.plot(ax=inset, facecolor="#fef3c7", edgecolor="#111827", linewidth=0.8, alpha=0.68, zorder=1)
    xmin, ymin, xmax, ymax = boundary.total_bounds
    dx = xmax - xmin
    dy = ymax - ymin
    inset.set_xlim(xmin - dx * 0.05, xmax + dx * 0.05)
    inset.set_ylim(ymin - dy * 0.05, ymax + dy * 0.05)
    inset.set_aspect("equal")

    bx0, by0, bx1, by1 = main_bounds
    inset.add_patch(
        Rectangle(
            (bx0, by0),
            bx1 - bx0,
            by1 - by0,
            facecolor="none",
            edgecolor="#dc2626",
            linewidth=1.1,
            zorder=5,
        )
    )
    inset.text(
        0.04,
        0.95,
        "全域定位",
        transform=inset.transAxes,
        ha="left",
        va="top",
        fontsize=7.6,
        fontweight="bold",
        color="#111827",
        bbox=dict(facecolor="white", edgecolor="#d1d5db", alpha=0.86, pad=1.8),
    )
    inset.set_xticks([])
    inset.set_yticks([])
    for spine in inset.spines.values():
        spine.set_linewidth(0.75)
        spine.set_color("#111827")


def draw_side_panel(ax, stats: dict, poi_counts: dict, comm: gpd.GeoDataFrame) -> None:
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    ax.text(0.02, 0.985, "图层与判读说明", fontsize=15, fontweight="bold", ha="left", va="top", color="#111827")
    ax.text(
        0.02,
        0.948,
        "这版总图不再只展示点和线，而是把“可达性幻觉”拆成底层空间结构、服务供给、步行路径和社区风险四类证据。",
        fontsize=8.7,
        ha="left",
        va="top",
        color="#374151",
        wrap=True,
    )

    y = 0.885
    layer_items = [
        ("#3b4252", "主干/快速路", "表达跨区通达骨架"),
        ("#9ca3af", "居住/服务道路", "表达街区内部连接"),
        ("#7c3aed", "步行/台阶/绿道", "表达慢行可达性基础"),
        ("#06b6d4", "步行路由网络", "由 network_edges 重构"),
        ("#f59e0b", "街景采样轨迹", "20 m 间隔路线点"),
        ("#d1d5db", "建筑/AOI", "街区形态与用地强度"),
        ("#dc2626", "社区 SAII 风险点", "颜色越深，时间贫困越强"),
    ]
    ax.text(0.02, y, "一、空间图层", fontsize=10.5, fontweight="bold", ha="left", va="top", color="#111827")
    y -= 0.032
    for color, label, desc in layer_items:
        ax.plot([0.03, 0.105], [y, y], color=color, lw=3.2, solid_capstyle="round")
        ax.text(0.13, y, label, fontsize=8.8, fontweight="bold", va="center", color="#111827")
        ax.text(0.48, y, desc, fontsize=8.2, va="center", color="#4b5563")
        y -= 0.033

    y -= 0.015
    ax.text(0.02, y, "二、POI 服务类型", fontsize=10.5, fontweight="bold", ha="left", va="top", color="#111827")
    y -= 0.033
    poi_style = {
        "医疗": ("#dc2626", "P"),
        "教育": ("#2563eb", "s"),
        "交通": ("#0891b2", "^"),
        "购物": ("#9333ea", "D"),
        "餐饮": ("#f97316", "o"),
        "公共/生活": ("#16a34a", "h"),
    }
    for label, (color, marker) in poi_style.items():
        ax.scatter([0.055], [y], s=60, color=color, marker=marker, edgecolor="white", linewidth=0.4)
        ax.text(0.13, y, f"{label}", fontsize=8.8, fontweight="bold", va="center", color="#111827")
        ax.text(0.48, y, f"{poi_counts.get(label, 0):,} 个", fontsize=8.4, va="center", color="#4b5563")
        y -= 0.031

    y -= 0.012
    ax.text(0.02, y, "三、关键统计", fontsize=10.5, fontweight="bold", ha="left", va="top", color="#111827")
    y -= 0.038
    stat_lines = [
        ("行政范围", "南山区真实区界"),
        ("道路网", f"{stats['roads']:,} 条 OSM 道路段"),
        ("步行路由", f"{stats['route_edges']:,} 条可步行边"),
        ("POI", f"{stats['pois']:,} 个设施点"),
        ("社区/AOI", f"{stats['communities']:,} 个居住单元"),
        ("建筑轮廓", f"{stats['buildings']:,} 个建筑面"),
        ("街景采样", f"{stats['trajectory']:,} 个 20 m 采样点"),
    ]
    for k, v in stat_lines:
        ax.text(0.04, y, k, fontsize=8.6, fontweight="bold", ha="left", color="#111827")
        ax.text(0.39, y, v, fontsize=8.6, ha="left", color="#374151")
        y -= 0.029

    y -= 0.016
    ax.text(0.02, y, "四、主题变量解释", fontsize=10.5, fontweight="bold", ha="left", va="top", color="#111827")
    y -= 0.035
    saii_q = comm["SAII"].quantile([0.25, 0.5, 0.75, 0.95]).to_dict()
    paragraphs = [
        f"SAII 表示昼夜公共服务可达性的落差，圆点越红代表居民在夜间或慢行条件下越容易陷入时间贫困。",
        f"本图中 SAII 四分位为 Q1={saii_q[0.25]:.3f}、中位数={saii_q[0.5]:.3f}、Q3={saii_q[0.75]:.3f}，高风险点采用黑色外圈标出。",
        "POI 背景热度反映服务供给密度，若高密度 POI 与高 SAII 社区并存，说明“看似近、实际难达”的可达性幻觉更突出。",
    ]
    for text in paragraphs:
        ax.text(0.04, y, text, fontsize=8.2, ha="left", va="top", color="#374151", wrap=True)
        y -= 0.069

    ax.text(
        0.02,
        0.035,
        "数据源：OSM 路网、network_output 路由图、facility_locations POI、社区可达性结果、街景 20m 轨迹采样。",
        fontsize=7.6,
        color="#6b7280",
        ha="left",
        va="bottom",
        wrap=True,
    )


def main() -> None:
    choose_font()

    boundary = read_boundary()
    boundary_geom = boundary.geometry.unary_union

    roads = read_roads(boundary_geom)
    buildings = read_buildings(boundary_geom)
    poi = read_pois(boundary_geom)
    comm = read_communities(boundary_geom)
    route_edges = read_route_edges(boundary_geom)
    traj = read_trajectory(boundary_geom)

    print(f"boundary: {len(boundary)}")
    print(f"roads: {len(roads):,}")
    print(f"buildings: {len(buildings):,}")
    print(f"pois: {len(poi):,}")
    print(f"communities: {len(comm):,}")
    print(f"route_edges: {len(route_edges):,}")
    print(f"trajectory: {len(traj):,}")

    fig = plt.figure(figsize=(16.2, 10.1), dpi=300)
    gs = fig.add_gridspec(1, 2, width_ratios=[3.65, 1.13], wspace=0.025)
    ax = fig.add_subplot(gs[0, 0])
    side = fig.add_subplot(gs[0, 1])
    fig.subplots_adjust(left=0.035, right=0.986, top=0.89, bottom=0.088, wspace=0.02)
    ax.set_facecolor("#f8fafc")
    ax.set_aspect("equal")

    # The administrative polygon includes outlying islands. The main map focuses
    # on the built-up Nanshan road body, while a locator inset keeps the full
    # district boundary visible.
    xmin, ymin, xmax, ymax = roads.total_bounds
    pad_x = (xmax - xmin) * 0.035
    pad_y = (ymax - ymin) * 0.035
    main_bounds = (xmin - pad_x, ymin - pad_y, xmax + pad_x, ymax + pad_y)
    ax.set_xlim(main_bounds[0], main_bounds[2])
    ax.set_ylim(main_bounds[1], main_bounds[3])

    boundary.plot(ax=ax, facecolor="#fef3c7", edgecolor="#111827", linewidth=1.25, alpha=0.55, zorder=1)
    plot_buildings(ax, buildings)
    plot_route_edges(ax, route_edges)
    plot_road_layers(ax, roads)
    poi_counts = plot_pois(ax, poi)
    traj_sample = plot_trajectory(ax, traj)
    plot_communities(ax, comm, min_size=16, max_size=96, alpha=0.77, label_top=8)
    label_major_roads(ax, roads)
    boundary.boundary.plot(ax=ax, color="#111827", linewidth=1.45, zorder=28)

    ax.set_xticks([])
    ax.set_yticks([])
    fig.text(
        0.035,
        0.963,
        "15分钟城市陷阱：公共服务可达性幻觉下的时间贫困综合总图",
        ha="left",
        va="top",
        fontsize=17.5,
        fontweight="bold",
        color="#111827",
    )
    fig.text(
        0.035,
        0.925,
        "南山区真实区界 + 道路层级 + 步行路由 + 街景采样轨迹 + POI服务密度 + 社区SAII风险",
        ha="left",
        va="top",
        fontsize=10.5,
        color="#374151",
    )

    add_locator_inset(ax, boundary, main_bounds)
    add_north_arrow(ax)
    add_scale_bar(ax, length_km=5)

    # Focus on the dense Yuehai / Shenzhen Bay / Science Park cluster.
    focus = comm.copy()
    if not focus.empty:
        center = focus.sort_values("SAII", ascending=False).head(25)
        fxmin, fymin, fxmax, fymax = center.total_bounds
        fpad_x = max(3600, (fxmax - fxmin) * 0.42)
        fpad_y = max(3000, (fymax - fymin) * 0.42)
        focus_bounds = (fxmin - fpad_x, fymin - fpad_y, fxmax + fpad_x, fymax + fpad_y)
        add_detail_inset(ax, roads, route_edges, traj_sample, comm, poi, buildings, focus_bounds)

    # Dedicated SAII colorbar.
    norm = mcolors.Normalize(vmin=comm["SAII"].quantile(0.02), vmax=comm["SAII"].quantile(0.98))
    sm = cm.ScalarMappable(norm=norm, cmap=cm.get_cmap("YlOrRd"))
    sm.set_array([])
    map_box = ax.get_position()
    cax = fig.add_axes(
        [
            map_box.x0 + map_box.width * 0.50,
            map_box.y0 + map_box.height * 0.035,
            map_box.width * 0.34,
            0.016,
        ]
    )
    cbar = fig.colorbar(sm, cax=cax, orientation="horizontal")
    cbar.set_label("SAII 可达性幻觉强度（昼夜服务可达性落差）", fontsize=8.2, labelpad=2)
    cbar.ax.tick_params(labelsize=7.2, length=2)

    # Compact symbol legend for population size.
    pop_levels = [comm["population"].quantile(q) for q in [0.25, 0.5, 0.9]]
    pop_sizes = normalize_sizes(pd.Series(pop_levels), 16, 96)
    handles = [
        Line2D(
            [],
            [],
            marker="o",
            linestyle="None",
            markersize=math.sqrt(s) / 1.35,
            markerfacecolor="#f97316",
            markeredgecolor="#111827",
            alpha=0.84,
            label=f"{int(p):,}人",
        )
        for p, s in zip(pop_levels, pop_sizes)
    ]
    leg = ax.legend(
        handles=handles,
        title="社区人口规模",
        loc="lower right",
        bbox_to_anchor=(0.984, 0.022),
        frameon=True,
        framealpha=0.92,
        facecolor="white",
        edgecolor="#d1d5db",
        fontsize=7.8,
        title_fontsize=8.4,
    )
    leg.set_zorder(40)

    stats = {
        "roads": int(len(roads)),
        "route_edges": int(len(route_edges)),
        "pois": int(len(poi)),
        "communities": int(len(comm)),
        "buildings": int(len(buildings)),
        "trajectory": int(len(traj)),
        "trajectory_sample_plotted": int(len(traj_sample)),
        "main_map_bounds_epsg3857": [float(v) for v in main_bounds],
        "boundary_source": str(boundary["layer_source"].iloc[0]),
        "road_classes": roads["fclass"].value_counts().to_dict(),
        "poi_counts": poi_counts,
        "saii_quantiles": {str(k): float(v) for k, v in comm["SAII"].quantile([0.05, 0.25, 0.5, 0.75, 0.95]).items()},
    }
    draw_side_panel(side, stats, poi_counts, comm)

    fig.text(
        0.055,
        0.018,
        "制图说明：灰色建筑/AOI展示街区形态，紫色强调慢行设施，青色为可步行路由图，橙色为街景采样路线，POI颜色表示服务类型，社区圆点颜色表示SAII风险。",
        fontsize=8,
        color="#4b5563",
        ha="left",
    )

    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight", pad_inches=0.12)
    fig.savefig(OUT_PDF, bbox_inches="tight", pad_inches=0.12)
    OUT_JSON.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {OUT_PNG}")
    print(f"saved: {OUT_PDF}")
    print(f"saved: {OUT_JSON}")


if __name__ == "__main__":
    main()
