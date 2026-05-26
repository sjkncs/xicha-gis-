# -*- coding: utf-8 -*-
"""检查已有路网文件内容"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os
graphml = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\osm_data\road_network.graphml"
print(f"File size: {os.path.getsize(graphml) / 1e6:.1f} MB")

# Quick check with osmnx
try:
    import osmnx as ox
    print("Loading graphml...")
    G = ox.load_graphml(graphml)
    print(f"  Nodes: {len(G.nodes)}")
    print(f"  Edges: {len(G.edges)}")
    # Check if it's in Nanshan area
    lons = [d.get('x', 0) for _, d in G.nodes(data=True)]
    lats = [d.get('y', 0) for _, d in G.nodes(data=True)]
    if lons:
        print(f"  Lon range: {min(lons):.4f} - {max(lons):.4f}")
        print(f"  Lat range: {min(lats):.4f} - {max(lats):.4f}")
        # Nanshan approx: lon 113.85-113.98, lat 22.45-22.62
        ns_nodes = sum(1 for lon, lat in zip(lons, lats) if 113.85 < lon < 113.98 and 22.45 < lat < 22.62)
        print(f"  Nanshan-area nodes: ~{ns_nodes}")
    print("  First 3 nodes:", list(G.nodes(data=True))[:3])
except Exception as e:
    print(f"  Error loading: {e}")
