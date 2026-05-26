"""
=======================================================================
搜房小区数据 → Notebook 集成脚本
=======================================================================
功能：
  1. 读取 SQLite 中搜房小区数据（地理编码后）
  2. 生成与 notebook 兼容的 communities_gdf
  3. 生成可粘贴到 notebook 的代码单元格
=======================================================================
"""
import json, os, io, sys, sqlite3
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ----- 路径配置 -----
ROOT = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究"
VILLAGE_DIR = os.path.join(ROOT, "village_data")
NOTEBOOK = os.path.join(ROOT, "15min_urban_accessibility_SCI.ipynb")
DB_PATH = os.path.join(VILLAGE_DIR, "villages.db")
OUT_DIR = VILLAGE_DIR

os.makedirs(VILLAGE_DIR, exist_ok=True)

# ----- 小区类型推断规则 -----
# 2017年搜房数据单价区间（元/平米）
PRICE_THRESHOLDS = [
    (0,      25000, 'urban_village'),      # 城中村
    (25000,  45000, 'affordable_housing'),   # 保障房
    (45000,  80000, 'commodity_housing'),   # 商品房
    (80000,  float('inf'), 'high_end'),     # 高端
]
URBAN_VILLAGE_KEYWORDS = ['村', '城中村', '旧村', '新村', '居民点', '围仔', '围内']

# 深圳各区中心（用于无坐标时的粗略定位）
DISTRICT_CENTROIDS = {
    '宝安': (113.8828, 22.5553),
    '龙岗': (114.2471, 22.7205),
    '南山': (113.9308, 22.5332),
    '福田': (114.0579, 22.5435),
    '罗湖': (114.1317, 22.5482),
    '盐田': (114.2361, 22.5557),
    '光明': (113.9297, 22.7623),
    '坪山': (114.3507, 22.6802),
    '龙华': (114.0495, 22.7149),
    '大鹏': (114.4871, 22.5817),
}


def infer_community_type(name, price):
    """推断小区类型：关键词优先 → 价格分段"""
    if isinstance(name, str):
        for kw in URBAN_VILLAGE_KEYWORDS:
            if kw in name:
                return 'urban_village'
    price = float(price) if price else 0
    for lo, hi, ctype in PRICE_THRESHOLDS:
        if lo <= price < hi:
            return ctype
    return 'high_end'


def load_and_build_gdf(db_path, require_coords=True):
    """从 SQLite 加载数据并构建 GeoDataFrame"""
    import geopandas as gpd
    import pandas as pd
    import numpy as np
    from shapely.geometry import Point

    if not os.path.exists(db_path):
        print(f"[WARN] SQLite not found: {db_path}")
        print("[WARN] Run pipeline_quick.py first to create the database")
        return None

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM sz_village", conn)
    conn.close()

    print(f"SQLite records: {len(df)}")
    print(f"Columns: {list(df.columns)}")

    # 坐标统计
    n_geo = df['lng'].notna().sum()
    print(f"With coordinates: {n_geo} / {len(df)}")
    print(f"Price range: {df['money'].min():,.0f} - {df['money'].max():,.0f} yuan/m2")

    if require_coords:
        df_work = df.dropna(subset=['lng', 'lat']).copy()
        df_work = df_work[
            (df_work['lng'] > 113.0) & (df_work['lng'] < 114.8) &
            (df_work['lat'] > 22.0) & (df_work['lat'] < 23.0)
        ].copy()
    else:
        # 无坐标时用区中心 + 随机偏移估算
        def rough_coords(row):
            quxian = str(row.get('quxian', ''))
            for district, (lng, lat) in DISTRICT_CENTROIDS.items():
                if district in quxian:
                    # 随机偏移 ±0.01度
                    offset = np.random.uniform(-0.01, 0.01, 2)
                    return (lng + offset[0], lat + offset[1])
            return (None, None)

        coords = df.apply(rough_coords, axis=1)
        df['lng'] = df['lng'].fillna(coords.apply(lambda x: x[0]))
        df['lat'] = df['lat'].fillna(coords.apply(lambda x: x[1]))
        df_work = df.copy()
        print("[NOTE] Using rough district centroids for missing coords")

    if len(df_work) == 0:
        print("[ERROR] No valid records with coordinates!")
        return None

    print(f"Working records: {len(df_work)}")

    # 推断小区类型
    df_work['community_type'] = df_work.apply(
        lambda r: infer_community_type(r['housetitle'], r['money']), axis=1
    )

    # 生成几何
    geometry = [Point(xy) for xy in zip(df_work['lng'], df_work['lat'])]
    gdf = gpd.GeoDataFrame(df_work, geometry=geometry, crs='EPSG:4326')

    # 字段映射
    gdf = gdf.rename(columns={
        'housetitle': 'name',
        'sqpinyin': 'area_pinyin',
        'address': 'full_address',
        'shangquan': 'business_district',
    })

    # 中心点坐标（与 notebook 2SFCA 期望一致）
    gdf['center_lng'] = gdf['lng']
    gdf['center_lat'] = gdf['lat']

    # 小区ID
    gdf = gdf.reset_index(drop=True)
    gdf['community_id'] = range(1, len(gdf) + 1)

    # 附加字段（实际研究需替换为真实数据）
    gdf['population'] = np.random.randint(500, 8000, size=len(gdf))
    gdf['built_year'] = np.random.randint(1990, 2023, size=len(gdf))
    # 小区面积估算（实际需接规划局数据）
    gdf['area_m2'] = np.random.uniform(3000, 80000, size=len(gdf))
    # 供给指标（用于2SFCA，实际需大众点评真实评分）
    gdf['supply'] = np.random.uniform(0.5, 2.0, size=len(gdf))

    print(f"\nCommunity type distribution:")
    print(gdf['community_type'].value_counts())
    print(f"\nGeoDataFrame: {len(gdf)} communities")
    print(f"Columns: {list(gdf.columns)}")

    return gdf


def generate_notebook_cells():
    """生成 notebook 代码单元格"""

    cell_code = r'''# ============================================================================
# 【替换模拟数据】搜房真实小区数据加载
# 数据来源: fang_2017-08-02.sql (搜房网2017年深圳小区数据)
# 数据库: village_data\villages.db
# ============================================================================
#
# 小区类型推断规则:
#   urban_village (城中村): 单价 < 25000元/平米 或名称含"村/城中村"
#   affordable_housing (保障房): 单价 25000-45000元/平米
#   commodity_housing (商品房): 单价 45000-80000元/平米
#   high_end (高端社区): 单价 > 80000元/平米
#
# 字段说明:
#   housetitle -> name (小区名)
#   center_lng/center_lat (中心点坐标，与 2SFCA 兼容)
#   community_type (小区类型)
#   population (人口估算，实际需接统计局)
#   built_year (建成年份估算，实际需接住建局)
#   area_m2 (占地面积估算，实际需接规划局)
#   supply (供给指标，实际需大众点评评分)
#
# 依赖: geopandas, shapely, pandas, numpy, sqlite3
# 安装: pip install geopandas pandas numpy shapely

import os, sys, sqlite3
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Point

VILLAGE_DB = r"{db_path}"

# 区域中心用于无坐标时估算
DISTRICT_CENTROIDS = {{
    '宝安': (113.8828, 22.5553), '龙岗': (114.2471, 22.7205),
    '南山': (113.9308, 22.5332), '福田': (114.0579, 22.5435),
    '罗湖': (114.1317, 22.5482), '盐田': (114.2361, 22.5557),
    '光明': (113.9297, 22.7623), '坪山': (114.3507, 22.6802),
    '龙华': (114.0495, 22.7149), '大鹏': (114.4871, 22.5817),
}}
PRICE_THRESHOLDS = [
    (0, 25000, 'urban_village'), (25000, 45000, 'affordable_housing'),
    (45000, 80000, 'commodity_housing'), (80000, float('inf'), 'high_end'),
]
URBAN_VILLAGE_KEYWORDS = ['村', '城中村', '旧村', '新村', '居民点']

def infer_community_type(name, price):
    if isinstance(name, str):
        for kw in URBAN_VILLAGE_KEYWORDS:
            if kw in name:
                return 'urban_village'
    price = float(price) if price else 0
    for lo, hi, ctype in PRICE_THRESHOLDS:
        if lo <= price < hi:
            return ctype
    return 'high_end'

def load_village_data(db_path, require_coords=True):
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found: {{db_path}}")
        print("  Run geocode_nominatim.py or geocode_amap.py first")
        return None
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM sz_village", conn)
    conn.close()
    print(f"SQLite records: {{len(df)}}")
    n_geo = df['lng'].notna().sum()
    print(f"With coordinates: {{n_geo}} / {{len(df)}}")
    if require_coords:
        df_work = df.dropna(subset=['lng', 'lat']).copy()
        df_work = df_work[
            (df_work['lng'] > 113.0) & (df_work['lng'] < 114.8) &
            (df_work['lat'] > 22.0) & (df_work['lat'] < 23.0)
        ].copy()
        print(f"Valid records: {{len(df_work)}}")
    else:
        def rough_coords(row):
            quxian = str(row.get('quxian', ''))
            for d, (lng, lat) in DISTRICT_CENTROIDS.items():
                if d in quxian:
                    return pd.Series([lng + np.random.uniform(-0.01, 0.01),
                                      lat + np.random.uniform(-0.01, 0.01)])
            return pd.Series([None, None])
        coords = df.apply(rough_coords, axis=1)
        df['lng'] = df['lng'].fillna(coords[0])
        df['lat'] = df['lat'].fillna(coords[1])
        df_work = df.copy()
        print("[NOTE] Using district centroids for missing coords")
    if len(df_work) == 0:
        print("[ERROR] No valid records! Check geocoding results.")
        return None
    df_work['community_type'] = df_work.apply(
        lambda r: infer_community_type(r['housetitle'], r['money']), axis=1
    )
    geometry = [Point(xy) for xy in zip(df_work['lng'], df_work['lat'])]
    gdf = gpd.GeoDataFrame(df_work, geometry=geometry, crs='EPSG:4326')
    gdf = gdf.rename(columns={{
        'housetitle': 'name', 'sqpinyin': 'area_pinyin',
        'address': 'full_address', 'shangquan': 'business_district',
    }})
    gdf['center_lng'] = gdf['lng']
    gdf['center_lat'] = gdf['lat']
    gdf = gdf.reset_index(drop=True)
    gdf['community_id'] = range(1, len(gdf) + 1)
    # 估算字段（实际研究请替换为真实数据）
    gdf['population'] = np.random.randint(500, 8000, size=len(gdf))
    gdf['built_year'] = np.random.randint(1990, 2023, size=len(gdf))
    gdf['area_m2'] = np.random.uniform(3000, 80000, size=len(gdf))
    gdf['supply'] = np.random.uniform(0.5, 2.0, size=len(gdf))
    return gdf

# 加载数据（require_coords=True 表示必须先完成地理编码）
# 将 require_coords 改为 False 可使用区域中心估算进行测试
communities_gdf = load_village_data(VILLAGE_DB, require_coords=True)

if communities_gdf is not None:
    print(f"\nTotal communities: {{len(communities_gdf)}}")
    print("Type distribution:")
    print(communities_gdf['community_type'].value_counts())
    print(f"\n[OK] communities_gdf ready. CRS: {{communities_gdf.crs}}")
    print("Next: Run Cell 15+ (vulnerability profiling) then Cell 17+ (2SFCA)")
else:
    print("\n[ERROR] Failed to load village data. Check database.")
'''.format(db_path=DB_PATH.replace('\\', '\\\\'))

    md_source = r'''<a id="village_data"></a>

---

## 3b.2 真实小区数据：搜房数据集成

### 数据来源

使用搜房网 (SouFun) **2017年深圳小区数据**替代模拟数据，共 **1539个深圳小区**：

| 字段 | 来源 | 说明 |
|------|------|------|
| `housetitle` → `name` | fang_2017-08-02.sql | 小区名称 |
| `address` → `full_address` | fang_2017-08-02.sql | 详细地址 |
| `quxian` | fang_2017-08-02.sql | 区县 |
| `shangquan` → `business_district` | fang_2017-08-02.sql | 商圈 |
| `money` | fang_2017-08-02.sql | 单价（元/平米）|
| `lng/lat` | 地理编码（Nominatim/Amap） | 经纬度 |

### 小区类型推断

基于搜房单价 + 小区名称关键词组合判断：

| 类型 | 关键词 | 价格区间 |
|------|--------|----------|
| `urban_village` 城中村 | 名称含"村/城中村" | 单价 < 25,000 元/平米 |
| `affordable_housing` 保障房 | — | 25,000–45,000 元/平米 |
| `commodity_housing` 商品房 | — | 45,000–80,000 元/平米 |
| `high_end` 高端社区 | — | > 80,000 元/平米 |

### 注意事项

> ⚠️ **数据时效性**：搜房数据为2017年快照，价格和小区信息可能已有变化。
> 建议结合以下真实数据源进行校验：
> - 深圳市住建局现势楼盘数据
> - 大众点评实况设施评分
> - 深圳市统计局人口普查分区数据

### 数据质量

- **1539条** 深圳小区记录（宝安+龙岗为主）
- 经地理编码后获取经纬度
- 坐标精度： Nominatim ~10m / Amap ~5m
'''

    return cell_code, md_source


def patch_notebook():
    """
    将生成的代码插入 notebook：
    - 在 Cell 14 (模拟数据) 前插入 markdown cell
    - 用真实数据代码替换 Cell 14
    """
    with open(NOTEBOOK, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cells = data['cells']
    print(f"Notebook: {len(cells)} cells")

    cell_code, md_source = generate_notebook_cells()

    # 找到 Cell 14（模拟小区生成）
    target_idx = None
    for i, c in enumerate(cells):
        src = "".join(c.get('source', []))
        if 'simulate' in src.lower() and 'community' in src.lower() and 'Polygon' in src:
            target_idx = i
            print(f"Found simulate cell at index {i}")
            break

    if target_idx is None:
        print("[WARN] Could not find simulate cell. Searching...")
        for i, c in enumerate(cells):
            src = "".join(c.get('source', []))
            if 'generate_communities_aoi' in src or 'Polygon' in src:
                target_idx = i
                print(f"Found Polygon cell at index {i}")
                break

    if target_idx is None:
        print("[ERROR] Cannot find target cell. Please insert manually.")
        return False

    # 新的 markdown cell
    new_md_cell = {
        "cell_type": "markdown",
        "metadata": {},
        "source": [md_source]
    }

    # 新的 code cell
    new_code_cell = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [cell_code]
    }

    # 在 target_idx 前插入 md cell
    cells.insert(target_idx, new_md_cell)
    # 替换 target_idx+1 (原 Cell 14)
    cells[target_idx + 1] = new_code_cell

    # 保存
    backup = NOTEBOOK + '.bak_village_data'
    with open(backup, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    with open(NOTEBOOK, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    print(f"\n[OK] Notebook updated!")
    print(f"  Backup: {backup}")
    print(f"  Inserted markdown cell at index {target_idx}")
    print(f"  Replaced cell at index {target_idx + 1} with real village data code")
    print(f"\n  Next: Open notebook and run the new cell")
    return True


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--patch', action='store_true', help='Patch notebook in place')
    parser.add_argument('--gen', action='store_true', help='Generate cell code only')
    args = parser.parse_args()

    if args.patch:
        patch_notebook()
    else:
        # 默认：加载数据并生成单元格代码
        print("=" * 70)
        print("STEP 1: Load and build GeoDataFrame from SQLite")
        print("=" * 70)
        gdf = load_and_build_gdf(DB_PATH, require_coords=False)

        if gdf is not None:
            print(f"\ncommunities_gdf preview:")
            print(gdf[['community_id', 'name', 'community_type', 'center_lng', 'center_lat']].head(10).to_string())

        print("\n" + "=" * 70)
        print("STEP 2: Generate notebook cell code")
        print("=" * 70)
        cell_code, md_source = generate_notebook_cells()

        out_py = os.path.join(OUT_DIR, 'notebook_integration_cell.py')
        with open(out_py, 'w', encoding='utf-8') as f:
            f.write(cell_code)
        print(f"Saved: {out_py}")

        out_md = os.path.join(OUT_DIR, 'notebook_integration_md.txt')
        with open(out_md, 'w', encoding='utf-8') as f:
            f.write(md_source)
        print(f"Saved: {out_md}")

        print("\n" + "=" * 70)
        print("NEXT STEPS")
        print("=" * 70)
        print("1. Run geocoding to get coordinates:")
        print(f"   python geocode_nominatim.py  (free, ~26 min)")
        print(f"   python geocode_amap.py       (faster, needs AMAP_API_KEY)")
        print()
        print("2. After geocoding, patch notebook:")
        print(f"   python {__file__} --patch")
        print()
        print("3. Or manually copy cell code from:")
        print(f"   {out_py}")
