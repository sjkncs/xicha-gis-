"""
分析 notebook 数据结构
"""
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with open(r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

print(f"总单元格数: {len(nb['cells'])}")
print(f"notebook 格式: {nb.get('nbformat', '?')}.{nb.get('nbformat_minor', '?')}")

# 扫描所有 code cells，寻找数据加载/处理相关代码
data_keywords = ['shp', 'geojson', 'gpd', 'read_file', 'shenzhen', '小区', 'village',
                 'import', 'gdf', 'GeoDataFrame', 'load', 'save', 'plot', 'folium']

print()
print("=== 数据相关代码单元 ===")
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    src = ''.join(cell['source'])
    # 检查是否包含数据关键词
    hits = [k for k in data_keywords if k in src]
    if hits:
        print(f"\n--- Cell {i} [tags: {hits}] ---")
        print(src[:500])
        if len(src) > 500:
            print("    ...")
