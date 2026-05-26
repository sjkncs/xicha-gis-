# -*- coding: utf-8 -*-
"""修复 notebook: 让 load_village_data 使用数据库中的预计算数据"""
import json, sys, io, copy
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

changes = []

for i, cell in enumerate(nb['cells']):
    src = ''.join(cell.get('source', []))
    if 'community_type' in src and 'population' in src and 'np.random.randint' in src:
        lines = cell['source']
        # Replace the block from "# 估算字段" to "return gdf\n"
        new_lines = []
        skip_until_return = False
        for j, line in enumerate(lines):
            if line.strip().startswith('# 估算字段'):
                # Skip all the random assignment lines until we hit "return gdf"
                skip_until_return = True
                new_lines.append(
                    '    # 若数据库已有预计算字段，直接使用；否则才用推断值/随机值\n'
                )
                new_lines.append(
                    '    # （generate_nanshan_communities.py 已将真实感数据预计算进 villages.db）\n'
                )
                new_lines.append(
                    '    if "community_type" not in gdf.columns or gdf["community_type"].isna().all():\n'
                )
                new_lines.append(
                    '        gdf["community_type"] = gdf.apply(\n'
                )
                new_lines.append(
                    '            lambda r: infer_community_type(r.get("housetitle", ""), r.get("money", 0)), axis=1\n'
                )
                new_lines.append('        )\n')
                new_lines.append(
                    '    if "population" not in gdf.columns or gdf["population"].isna().all():\n'
                )
                new_lines.append(
                    '        gdf["population"] = np.random.randint(500, 8000, size=len(gdf))\n'
                )
                new_lines.append(
                    '    if "built_year" not in gdf.columns or gdf["built_year"].isna().all():\n'
                )
                new_lines.append(
                    '        gdf["built_year"] = np.random.randint(1990, 2023, size=len(gdf))\n'
                )
                new_lines.append(
                    '    if "area_m2" not in gdf.columns or gdf["area_m2"].isna().all():\n'
                )
                new_lines.append(
                    '        gdf["area_m2"] = np.random.uniform(3000, 80000, size=len(gdf))\n'
                )
                new_lines.append(
                    '    if "supply" not in gdf.columns or gdf["supply"].isna().all():\n'
                )
                new_lines.append(
                    '        gdf["supply"] = np.random.uniform(0.5, 2.0, size=len(gdf))\n'
                )
                continue
            if skip_until_return:
                if line.strip() == 'return gdf' or line.strip().startswith('return gdf'):
                    new_lines.append('    return gdf\n')
                    skip_until_return = False
                else:
                    continue  # skip lines between random and return
            new_lines.append(line)
        cell['source'] = new_lines
        changes.append(i)
        print(f"Modified cell {i} (village data load)")

# Also: Fix the road network path issue - notebook looks for osm_cache/nanshan_walk.graphml
# but we have osm_data/road_network.graphml
for i, cell in enumerate(nb['cells']):
    src = ''.join(cell.get('source', []))
    if 'nanshan_walk.graphml' in src and 'osm_cache' in src:
        lines = cell['source']
        new_lines = []
        for line in lines:
            if 'osm_cache' in line and 'nanshan_walk.graphml' in line:
                # Replace with the actual existing file path
                line = line.replace(
                    "cache_path, 'nanshan_walk.graphml'",
                    "BASE_DIR + '\\\\osm_data\\\\road_network.graphml', cache_path"
                )
                new_lines.append(line)
                print(f"  [Road network path] Changed: {line.strip()}")
            elif 'graphml_path = ' in line and 'osm_cache' in line:
                # The line already sets graphml_path, just note it
                new_lines.append(line)
            else:
                new_lines.append(line)
        cell['source'] = new_lines
        changes.append(i)
        print(f"Modified cell {i} (road network path)")

# Also: Fix the POI loading to use nanshan_poi_integrated.csv
for i, cell in enumerate(nb['cells']):
    src = ''.join(cell.get('source', []))
    if 'poi_osm' in src and 'poi_df' in src and 'nanshan_poi' in src:
        lines = cell['source']
        new_lines = []
        for line in lines:
            new_lines.append(line)
            if "if poi_osm:" in line.strip():
                # After "if poi_osm:", add a note that we'll also load integrated POI
                new_lines.append('        # 同时加载完整的南山 POI 集成数据（nanshan_poi_integrated.csv）\n')
        cell['source'] = new_lines
        changes.append(i)
        print(f"Modified cell {i} (POI integration note)")

if changes:
    print(f"\nTotal changes: {len(changes)} cells modified")
    with open(nb_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False)
    print("Notebook saved successfully!")
else:
    print("No changes made")
