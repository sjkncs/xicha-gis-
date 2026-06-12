# -*- coding: utf-8 -*-
"""打包 3D 可视化部署包"""
import zipfile, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

VIS = r"E:\xicha gis 智能定位\projects\15min-urban-accessibility\city_visualization"
OUT = r"E:\xicha gis 智能定位\自选年份\deploy_3d.zip"

FILES = [
    os.path.join(VIS, "city_visualization_3d.html"),
    os.path.join(VIS, "connected_roads.geojson"),
    os.path.join(VIS, "network_nodes.geojson"),
    os.path.join(VIS, "routing_graph.json"),
    os.path.join(VIS, "city_cesium.geojson"),
    os.path.join(VIS, "city_visualization.html"),   # 旧版 2D
]

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_STORED) as zf:
    for fp in FILES:
        if os.path.exists(fp):
            name = os.path.basename(fp)
            sz = os.path.getsize(fp)
            print(f"  + {name} ({sz/1024/1024:.1f} MB)")
            zf.write(fp, name)
        else:
            print(f"  ! NOT FOUND: {fp}")

out_size = os.path.getsize(OUT)
print(f"\nZIP 大小: {out_size/1024/1024:.1f} MB")
print(f"输出: {OUT}")
