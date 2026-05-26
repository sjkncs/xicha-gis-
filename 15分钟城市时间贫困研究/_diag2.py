# -*- coding: utf-8 -*-
# Diagnostic script to inspect GraphML structure

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

base = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
graphml_path = base + r"\osm_data\road_network.graphml"

print(f"Loading: {graphml_path}")
import networkx as nx
G = nx.read_graphml(graphml_path)
print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, type={type(G)}")

# Sample nodes
print("\nFirst 3 nodes:")
for i, (n, data) in enumerate(G.nodes(data=True)):
    if i >= 3: break
    print(f"  {str(n)[:40]}: {data}")

# Sample edges
print("\nFirst 3 edges:")
for i, (u, v, data) in enumerate(G.edges(data=True)):
    if i >= 3: break
    print(f"  {str(u)[:20]} -> {str(v)[:20]}: {list(data.keys())}")

# Try building edges_list with geometry extraction
from shapely.geometry import LineString
import geopandas as gpd

edges_list = []
missing_geom = 0
exc_count = 0
partial_count = 0
has_geom_attr = 0
has_wkt_attr = 0
rebuilt = 0

for i, (u, v, data) in enumerate(G.edges(data=True)):
    if i >= 20:
        break
    geom = None
    reason = "unknown"
    try:
        if 'geometry' in data and data['geometry'] is not None:
            geom = data['geometry']
            reason = "geometry_attr"
            has_geom_attr += 1
        elif 'wkt' in data:
            from shapely import wkt as shapely_wkt
            geom = shapely_wkt.loads(data['wkt'])
            reason = "wkt"
            has_wkt_attr += 1
        else:
            try:
                u_data = G.nodes[u]
                v_data = G.nodes[v]
                x1 = u_data.get('x')
                y1 = u_data.get('y')
                x2 = v_data.get('x')
                y2 = v_data.get('y')
                if x1 is not None and x2 is not None and y1 is not None and y2 is not None:
                    geom = LineString([(x1, y1), (x2, y2)])
                    reason = "rebuilt_from_coords"
                    rebuilt += 1
                else:
                    reason = f"partial_coords(x1={x1},x2={x2},y1={y1},y2={y2})"
                    partial_count += 1
            except Exception as e:
                reason = f"exc:{e}"
                exc_count += 1
    except Exception as e:
        reason = f"outer_exc:{e}"
        exc_count += 1

    print(f"  Edge {i}: reason={reason}, geom_type={type(geom).__name__ if geom else 'None'}")
    if geom is not None:
        edges_list.append({'geometry': geom, **data})
    else:
        missing_geom += 1

print(f"\nFirst 20 edges summary: {has_geom_attr} has_geom, {has_wkt_attr} has_wkt, {rebuilt} rebuilt, {partial_count} partial, {exc_count} exc, {missing_geom} still missing")
print(f"edges_list has {len(edges_list)} items")
