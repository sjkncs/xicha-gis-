"""
Build script: embed real bev_voxel_3d.json data into tesla_world_3d.html
and generate synthetic road segments from cell connectivity.
"""
import json
from pathlib import Path

SRC_JSON = Path(__file__).parent / "world_model_output" / "bev_voxel_3d.json"
SRC_HTML = Path(__file__).parent / "world_model_output" / "tesla_world_3d.html"
DST_HTML = SRC_HTML  # overwrite in place

def generate_synthetic_roads(cells, threshold_km=0.5):
    """Generate road segments by connecting nearby cells with high walkability."""
    import math

    def haversine_km(l1, L1, l2, L2):
        R = 6371
        dlat = math.radians(L2 - L1)
        dlon = math.radians(l2 - l1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(L1)) * math.cos(math.radians(L2)) * math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))

    roads = []
    n = len(cells)
    for i in range(n):
        for j in range(i+1, n):
            c1, c2 = cells[i], cells[j]
            dist = haversine_km(c1["center_lng"], c1["center_lat"], c2["center_lng"], c2["center_lat"])
            if dist < threshold_km and dist > 0.01:
                w1 = c1.get("walkability", 5.0)
                w2 = c2.get("walkability", 5.0)
                if w1 >= 6.0 and w2 >= 6.0:
                    road_class = "primary" if (w1 + w2) / 2 > 7.0 else "secondary"
                    digital_occ = (c1.get("digital_occ", 0.22) + c2.get("digital_occ", 0.22)) / 2
                    width_m = 12 if road_class == "primary" else 8
                    roads.append({
                        "lng_start": c1["center_lng"],
                        "lat_start": c1["center_lat"],
                        "lng_end": c2["center_lng"],
                        "lat_end": c2["center_lat"],
                        "road_class": road_class,
                        "digital_occ": round(digital_occ, 4),
                        "width_m": width_m
                    })
    return roads

def compute_summary(cells):
    """Compute illusion score summary from cells."""
    if not cells:
        return {"illusion_score": 0, "n_cells": 0, "mean_physical_occ": 0, "mean_digital_occ": 0, "n_hotspots": 0}
    phys = [c["p_occ"] for c in cells]
    digi = [c["digital_occ"] for c in cells]
    total = [c["total_occupancy"] for c in cells]
    illusion = sum(abs(p - d) for p, d in zip(phys, digi)) / len(cells)
    hotspots = sum(1 for c in cells if abs(c["p_occ"] - c["digital_occ"]) > 0.15)
    return {
        "illusion_score": round(illusion, 4),
        "n_cells": len(cells),
        "mean_physical_occ": round(sum(phys)/len(phys), 3),
        "mean_digital_occ": round(sum(digi)/len(digi), 3),
        "n_hotspots": hotspots
    }

def main():
    # Load real data
    with open(SRC_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    cells = data["cells"]
    bounds = data["bounds"]
    grid_res = data["grid_resolution_deg"]

    # Generate roads
    roads = generate_synthetic_roads(cells)
    print(f"Generated {len(roads)} synthetic road segments")

    # Compute summary
    summary = compute_summary(cells)
    print(f"Summary: {summary}")

    # Build JS cells array
    js_cells = []
    for c in cells:
        js_cells.append(
            f'{{lng:{c["lng"]},lat:{c["lat"]},height_layers:[{c["height_layers"][0]},{c["height_layers"][1]},{c["height_layers"][2]},{c["height_layers"][3]}],'
            f'total_occupancy:{c["total_occupancy"]},physical_flow:[{c["physical_flow"][0]},{c["physical_flow"][1]}],'
            f'p_occ:{c["p_occ"]},digital_occ:{c["digital_occ"]},road_type:"{c.get("road_type","unknown")}",urban_form:"{c.get("urban_form","unknown")}",'
            f'openness:{c["openness"]},walkability:{c["walkability"]},canyon:{c["canyon"]}}}'
        )

    js_roads = []
    for r in roads:
        js_roads.append(
            f'{{lng_start:{r["lng_start"]},lat_start:{r["lat_start"]},lng_end:{r["lng_end"]},lat_end:{r["lat_end"]},'
            f'road_class:"{r["road_class"]}",digital_occ:{r["digital_occ"]},width_m:{r["width_m"]}}}'
        )

    # Build replacement block
    replacement = (
        "window.WORLD_DATA = {\n"
        f"  bounds: [{bounds[0]}, {bounds[1]}, {bounds[2]}, {bounds[3]}],\n"
        f"  grid_res: {grid_res},\n"
        "  cells: [\n    " + ",\n    ".join(js_cells) + "\n  ],\n"
        "  road_segments: [\n    " + ",\n    ".join(js_roads) + "\n  ],\n"
        f"  summary: {json.dumps(summary, ensure_ascii=False)}\n"
        "};"
    )

    # Read HTML and replace WORLD_DATA block
    with open(SRC_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    import re
    # Find and replace window.WORLD_DATA = { ... };
    pattern = r'window\.WORLD_DATA\s*=\s*\{[^;]*\};'
    new_html = re.sub(pattern, replacement, html, flags=re.DOTALL)

    with open(DST_HTML, "w", encoding="utf-8") as f:
        f.write(new_html)

    print(f"Updated {DST_HTML} with {len(cells)} cells and {len(roads)} roads")

if __name__ == "__main__":
    main()
