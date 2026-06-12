"""
Enhanced embed script: embed real building white models + road network + obstacle markers
into tesla_world_3d.html for Tesla-style 3D cityscape visualization.
"""
import json, math, re
from pathlib import Path

# Paths
SRC_JSON   = Path(__file__).parent / "world_model_output" / "bev_voxel_3d.json"
SRC_BUILD  = Path(__file__).parent / "city_twin_output" / "buildings_white_model.json"
SRC_HTML   = Path(__file__).parent / "world_model_output" / "tesla_world_3d.html"
DST_HTML   = SRC_HTML

SCALE_FACTOR = 5000  # must match tesla_world_3d.html SCALE_FACTOR


# =============================================================================
# Haversine helpers
# =============================================================================
def haversine_km(l1, L1, l2, L2):
    R = 6371
    dlat = math.radians(L2 - L1)
    dlon = math.radians(l2 - l1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(L1)) * math.cos(math.radians(L2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def haversine_m(l1, L1, l2, L2):
    return haversine_km(l1, L1, l2, L2) * 1000


# =============================================================================
# 1. 加载体素网格数据
# =============================================================================
def load_voxel_cells():
    with open(SRC_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    cells = data["cells"]
    bounds = data["bounds"]
    grid_res = data["grid_resolution_deg"]
    return cells, bounds, grid_res


# =============================================================================
# 2. 加载真实建筑白模（只取落在范围内的）
# =============================================================================
def load_buildings(bounds):
    min_lng, min_lat, max_lng, max_lat = bounds
    margin = 0.002  # degrees margin

    with open(SRC_BUILD, "r", encoding="utf-8") as f:
        fc = json.load(f)

    buildings = []
    for feat in fc["features"]:
        props = feat["properties"]
        geom = feat["geometry"]

        lon = props.get("lon", props.get("lng"))
        lat = props.get("lat")
        if lon is None or lat is None:
            continue
        if not (min_lng - margin <= lon <= max_lng + margin
                and min_lat - margin <= lat <= max_lat + margin):
            continue

        height_m = float(props.get("height_m", 6.0) or 6.0)
        floors = int(props.get("floors", 1) or 1)
        use_name = props.get("use_name", "未知") or "未知"
        w = props.get("walkability")
        walkability = float(w) if w is not None and w != "" else 5.0

        # Extract polygon coordinates (outer ring only for simplicity)
        coords = None
        if geom["type"] == "Polygon":
            coords = geom["coordinates"][0]  # outer ring
        elif geom["type"] == "MultiPolygon":
            # pick largest polygon by area
            best = max(geom["coordinates"],
                       key=lambda r: abs(
                           max(c[0] for c in r[0]) - min(c[0] for c in r[0])
                           + max(c[1] for c in r[0]) - min(c[1] for c in r[0])
                       ))
            coords = best[0]

        if coords is None:
            continue

        # Compute centroid
        cx = sum(c[0] for c in coords) / len(coords)
        cy = sum(c[1] for c in coords) / len(coords)

        # Compute footprint area in sq meters (approximate)
        area_m2 = 0.0
        for i in range(len(coords)):
            x0, y0 = coords[i]
            x1, y1 = coords[(i + 1) % len(coords)]
            area_m2 += x0 * y1 - x1 * y0
        area_m2 = abs(area_m2) / 2 * 111000 * 111000  # rough conversion

        # Skip tiny buildings
        if area_m2 < 20:
            continue

        # Convert polygon to {x,z} world coords (local, relative to bounds)
        poly_wxwz = []
        for pt in coords:
            wx = (pt[0] - bounds[0]) * SCALE_FACTOR
            wz = (pt[1] - bounds[1]) * SCALE_FACTOR
            poly_wxwz.append((wx, wz))

        buildings.append({
            "lon": float(lon),
            "lat": float(lat),
            "wx": float(cx - bounds[0]) * SCALE_FACTOR,
            "wz": float(cy - bounds[1]) * SCALE_FACTOR,
            "height_m": height_m,
            "floors": floors,
            "use_name": use_name,
            "walkability": walkability,
            "poly": poly_wxwz,
            "area_m2": area_m2,
        })

    print(f"Loaded {len(buildings):,} buildings within bounds")
    return buildings


# =============================================================================
# 3.  生成合成道路网（基于街景点连通性）
# =============================================================================
def generate_roads_from_cells(cells):
    """Connect nearby cells with high walkability into road segments."""
    roads = []
    threshold_km = 0.6
    for i in range(len(cells)):
        for j in range(i + 1, len(cells)):
            c1, c2 = cells[i], cells[j]
            dist = haversine_km(
                c1["center_lng"], c1["center_lat"],
                c2["center_lng"], c2["center_lat"]
            )
            if dist < threshold_km and dist > 0.01:
                w1 = c1.get("walkability", 5.0)
                w2 = c2.get("walkability", 5.0)
                if w1 >= 6.0 and w2 >= 6.0:
                    road_class = "primary" if (w1 + w2) / 2 > 7.0 else "secondary"
                    digital_occ = (c1.get("digital_occ", 0.22) + c2.get("digital_occ", 0.22)) / 2
                    width_m = 14 if road_class == "primary" else 8
                    # Convert to world coords
                    wx_start = (c1["center_lng"] - c1.get("_bounds_lng", 113.883)) * SCALE_FACTOR
                    wz_start = (c1["center_lat"] - c1.get("_bounds_lat", 22.479)) * SCALE_FACTOR
                    wx_end   = (c2["center_lng"] - c2.get("_bounds_lng", 113.883)) * SCALE_FACTOR
                    wz_end   = (c2["center_lat"] - c2.get("_bounds_lat", 22.479)) * SCALE_FACTOR

                    # Use bounds from cells
                    b_lng = cells[0].get("center_lng", 113.883)
                    b_lat = cells[0].get("center_lat", 22.479)
                    # Re-derive bounds from cell data
                    lngs = [c["center_lng"] for c in cells]
                    lats = [c["center_lat"] for c in cells]
                    min_lng_b = min(lngs); max_lng_b = max(lngs)
                    min_lat_b = min(lats); max_lat_b = max(lats)

                    wx_start = (c1["center_lng"] - min_lng_b) * SCALE_FACTOR
                    wz_start = (c1["center_lat"] - min_lat_b) * SCALE_FACTOR
                    wx_end   = (c2["center_lng"] - min_lng_b) * SCALE_FACTOR
                    wz_end   = (c2["center_lat"] - min_lat_b) * SCALE_FACTOR

                    roads.append({
                        "wx_start": round(wx_start, 2),
                        "wz_start": round(wz_start, 2),
                        "wx_end": round(wx_end, 2),
                        "wz_end": round(wz_end, 2),
                        "road_class": road_class,
                        "digital_occ": round(float(digital_occ), 4),
                        "width_m": width_m,
                    })

    print(f"Generated {len(roads)} road segments")
    return roads


# =============================================================================
# 4.  生成障碍物热点标记
# =============================================================================
def generate_obstacle_markers(cells, threshold_occ=0.45):
    """Mark cells with high physical occupancy as obstacle hotspots."""
    markers = []
    for c in cells:
        if c.get("p_occ", 0) >= threshold_occ:
            wx = (c["center_lng"] - cells[0]["center_lng"]) * SCALE_FACTOR
            wz = (c["center_lat"] - cells[0]["center_lat"]) * SCALE_FACTOR
            markers.append({
                "wx": round(wx, 2),
                "wz": round(wz, 2),
                "p_occ": round(float(c["p_occ"]), 4),
                "walkability": round(float(c.get("walkability", 5)), 1),
                "canyon": round(float(c.get("canyon", 0)), 1),
                "urban_form": c.get("urban_form", "unknown"),
            })
    print(f"Generated {len(markers)} obstacle markers (p_occ >= {threshold_occ})")
    return markers


# =============================================================================
# 5.  计算幻觉评分汇总
# =============================================================================
def compute_summary(cells):
    if not cells:
        return {"illusion_score": 0, "n_cells": 0,
                "mean_physical_occ": 0, "mean_digital_occ": 0, "n_hotspots": 0}
    phys = [c["p_occ"] for c in cells]
    digi = [c["digital_occ"] for c in cells]
    illusion = sum(abs(p - d) for p, d in zip(phys, digi)) / len(cells)
    hotspots = sum(1 for c in cells if abs(c["p_occ"] - c["digital_occ"]) > 0.15)
    return {
        "illusion_score": round(illusion, 4),
        "n_cells": len(cells),
        "mean_physical_occ": round(sum(phys) / len(phys), 3),
        "mean_digital_occ": round(sum(digi) / len(digi), 3),
        "n_hotspots": hotspots,
        "n_buildings": 0,
        "n_roads": 0,
        "n_obstacle_markers": 0,
    }


# =============================================================================
# 6.  生成 JS 字符串
# =============================================================================
def cells_to_js(cells):
    lines = []
    for c in cells:
        lines.append(
            f'{{lng:{c["lng"]},lat:{c["lat"]},'
            f'height_layers:[{c["height_layers"][0]},{c["height_layers"][1]},'
            f'{c["height_layers"][2]},{c["height_layers"][3]}],'
            f'total_occupancy:{c["total_occupancy"]},'
            f'physical_flow:[{c["physical_flow"][0]},{c["physical_flow"][1]}],'
            f'p_occ:{c["p_occ"]},digital_occ:{c["digital_occ"]},'
            f'road_type:"{c.get("road_type","unknown")}",'
            f'urban_form:"{c.get("urban_form","unknown")}",'
            f'openness:{c["openness"]},walkability:{c["walkability"]},canyon:{c["canyon"]}}}'
        )
    return ",\n    ".join(lines)


def buildings_to_js(buildings):
    """Convert buildings to JS array string (compact)."""
    lines = []
    for b in buildings:
        # stringify polygon as [[wx,wz],...]
        poly_str = ",".join(f"[{wx:.1f},{wz:.1f}]" for wx, wz in b["poly"])
        lines.append(
            f'{{wx:{b["wx"]:.1f},wz:{b["wz"]:.1f},'
            f'h:{b["height_m"]:.1f},fl:{b["floors"]},'
            f'use:"{b["use_name"]}",w:{b["walkability"]:.1f},'
            f'poly:[[{poly_str}]],a:{b["area_m2"]:.0f}}}'
        )
    return ",\n      ".join(lines)


def roads_to_js(roads):
    lines = []
    for r in roads:
        lines.append(
            f'{{ws:{r["wx_start"]:.1f},wz_s:{r["wz_start"]:.1f},'
            f'we:{r["wx_end"]:.1f},wz_e:{r["wz_end"]:.1f},'
            f'cls:"{r["road_class"]}",occ:{r["digital_occ"]:.4f},wm:{r["width_m"]}}}'
        )
    return ",\n    ".join(lines)


def markers_to_js(markers):
    lines = []
    for m in markers:
        lines.append(
            f'{{wx:{m["wx"]:.1f},wz:{m["wz"]:.1f},'
            f'occ:{m["p_occ"]:.4f},w:{m["walkability"]:.1f},'
            f'canyon:{m["canyon"]:.1f},form:"{m["urban_form"]}"}}'
        )
    return ",\n    ".join(lines)


# =============================================================================
# 7.  主流程
# =============================================================================
def main():
    print("=" * 60)
    print("Tesla-Style 3D World Model — Enhanced Embed Script")
    print("=" * 60)

    # Load voxel data
    cells, bounds, grid_res = load_voxel_cells()
    print(f"Voxel cells: {len(cells)}, bounds: {bounds}")

    # Load buildings
    buildings = load_buildings(bounds)

    # Generate roads from cells
    roads = generate_roads_from_cells(cells)

    # Generate obstacle markers
    markers = generate_obstacle_markers(cells)

    # Compute summary
    summary = compute_summary(cells)
    summary["n_buildings"] = len(buildings)
    summary["n_roads"] = len(roads)
    summary["n_obstacle_markers"] = len(markers)
    print(f"Summary: {summary}")

    # Build JS arrays
    js_cells    = cells_to_js(cells)
    js_buildings = buildings_to_js(buildings)
    js_roads    = roads_to_js(roads)
    js_markers  = markers_to_js(markers)

    # Build replacement block
    replacement = (
        "window.WORLD_DATA = {\n"
        f"  bounds: [{bounds[0]}, {bounds[1]}, {bounds[2]}, {bounds[3]}],\n"
        f"  grid_res: {grid_res},\n"
        f"  cellOrigin: [{cells[0]['center_lng']}, {cells[0]['center_lat']}],\n"
        "  cells: [\n    " + js_cells + "\n  ],\n"
        "  buildings: [\n      " + js_buildings + "\n  ],\n"
        "  road_segments: [\n    " + js_roads + "\n  ],\n"
        "  obstacle_markers: [\n    " + js_markers + "\n  ],\n"
        f"  summary: {json.dumps(summary, ensure_ascii=False)}\n"
        "};"
    )

    # Patch HTML — find WORLD_DATA block by line numbers and replace it
    with open(SRC_HTML, "r", encoding="utf-8") as f:
        content = f.read()
        lines = content.splitlines(keepends=True)

    start_line = None
    end_line = None
    for i, line in enumerate(lines):
        if 'window.WORLD_DATA' in line and '=' in line:
            start_line = i
        if start_line is not None and end_line is None:
            stripped = line.strip()
            if stripped == '};':
                end_line = i
                break

    if start_line is not None and end_line is not None:
        replacement_lines = replacement.replace('\\n', '\n').split('\n')
        new_lines = lines[:start_line] + [l + '\n' for l in replacement_lines[:-1]] + [replacement_lines[-1]] + lines[end_line + 1:]
        new_html = ''.join(new_lines)
        print(f"WORLD_DATA replaced in {SRC_HTML} (lines {start_line+1}-{end_line+1})")
    else:
        print(f"WARNING: Could not find WORLD_DATA block boundaries (start={start_line}, end={end_line})")
        print("Trying regex fallback...")
        pattern = r'window\.WORLD_DATA\s*=\s*\{[\s\S]*?\};'
        new_html = re.sub(pattern, replacement, content, flags=re.DOTALL)
        if new_html == content:
            print("ERROR: Both methods failed — WORLD_DATA not replaced!")
        else:
            print(f"WORLD_DATA replaced via regex fallback in {SRC_HTML}")

    with open(DST_HTML, "w", encoding="utf-8") as f:
        f.write(new_html)

    print("=" * 60)
    print(f"Done! Buildings: {len(buildings)}, Roads: {len(roads)}, "
          f"Markers: {len(markers)}, Cells: {len(cells)}")
    print("Open tesla_world_3d.html in browser to view.")
    print("=" * 60)


if __name__ == "__main__":
    main()
