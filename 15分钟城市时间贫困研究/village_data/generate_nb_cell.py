"""
=======================================================================
生成 Notebook 小区数据集成单元格
将 fang SQL 数据映射为 notebook 所需的格式
=======================================================================
"""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

VILLAGE_NB = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
OUT_DIR = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\village_data"
NB_OUT = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\village_data\replace_village_cell.py"

# 小区类型推断逻辑（基于搜房单价）
# 搜房价格(元/平米) -> 小区类型
PRICE_TYPE_MAP = """
# 小区类型推断规则（基于安居客历史单价数据）
#
# urban_village (城中村): 单价 < 25000 元/平米
#   特征: 建筑密度高, 无正规物业管理, 价格最低
#
# affordable_housing (保障房): 单价 25000-45000 元/平米
#   特征: 政府定价, 有限产权, 社会保障性质
#
# commodity_housing (商品房): 单价 45000-80000 元/平米
#   特征: 正规商品小区, 商业开发, 有物业管理
#
# high_end (高端社区): 单价 > 80000 元/平米
#   特征: 豪宅/大平层, 品牌物业, 配套完善
#
# 注意: 深圳南山/宝安区单价普遍较高, 需结合区域基准调整
"""

# 深圳南山/宝安区价格基准（2017年搜房数据）
PRICE_QUANTILES = {
    'urban_village': 35000,      # < 35000 -> 城中村
    'affordable_housing': 55000,  # 35000-55000 -> 保障房
    'commodity_housing': 100000, # 55000-100000 -> 商品房
    'high_end': float('inf'),    # > 100000 -> 高端
}

# 城中村关键词（直接匹配）
URBAN_VILLAGE_KEYWORDS = ['村', '城中村', '旧村', '新村', '居民点']

# 南山区近似范围（用于过滤）
NANSHAN_BBOX = {
    'north': 22.545,
    'south': 22.475,
    'east': 113.975,
    'west': 113.845
}


def infer_community_type(name, price):
    """根据小区名称和价格推断类型"""
    # 关键词优先
    for kw in URBAN_VILLAGE_KEYWORDS:
        if kw in name:
            return 'urban_village'

    # 按价格区间
    if price < PRICE_QUANTILES['urban_village']:
        return 'urban_village'
    elif price < PRICE_QUANTILES['affordable_housing']:
        return 'affordable_housing'
    elif price < PRICE_QUANTILES['commodity_housing']:
        return 'commodity_housing'
    else:
        return 'high_end'


def generate_notebook_cell():
    """
    生成可粘贴到 notebook 的代码单元格
    这个单元格替换 simulate 单元格，实现:
    1. 从 SQLite 加载搜房小区数据
    2. 价格推断小区类型
    3. 生成 Point 几何用于 GIS 分析
    4. 合并到 POI 路网分析框架
    """

    cell_code = r'''
# ============================================================================
# 【替换模拟数据】搜房真实小区数据加载
# 数据来源: fang_2017-08-02.sql (搜房网社区数据)
# ============================================================================
#
# 真实小区数据说明:
# - 数据表: t_sz_village (深圳)
# - 字段: housetitle(小区名), address(地址), quxian(区县), 
#         shangquan(商圈), money(单价元/平米), lng/lat(经纬度)
# - 数据量: 1539 个深圳小区 (宝安+龙岗为主)
#
# 小区类型推断:
#   城中村: 单价 < 35000 元/平米 或名称含"村/城中村"
#   保障房: 单价 35000-55000 元/平米
#   商品房: 单价 55000-100000 元/平米
#   高端:   单价 > 100000 元/平米

import sqlite3
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import numpy as np

VILLAGE_DB = r"{db_path}"
PRICE_QUANTILES = {{35000: 'urban_village', 55000: 'affordable_housing', 100000: 'commodity_housing'}}
URBAN_VILLAGE_KEYWORDS = ['村', '城中村', '旧村', '新村', '居民点']

def infer_community_type(name, price):
    for kw in URBAN_VILLAGE_KEYWORDS:
        if kw in str(name):
            return 'urban_village'
    for threshold, ctype in sorted(PRICE_QUANTILES.items()):
        if price < threshold:
            return ctype
    return 'high_end'

# 加载数据
print("Loading village data from SQLite...")
conn = sqlite3.connect(VILLAGE_DB)
df = pd.read_sql_query("SELECT * FROM sz_village", conn)
conn.close()

print(f"Total villages: {{len(df)}}")
print(f"With coordinates: {{df['lng'].notna().sum()}}")
print(f"Price range: {{df['money'].min():,.0f} - {{df['money'].max():,.0f}} yuan/m2")

# 过滤有坐标的记录
df_geo = df.dropna(subset=["lng", "lat"]).copy()
df_geo = df_geo[
    (df_geo["lng"] > 113.5) & (df_geo["lng"] < 114.6) &
    (df_geo["lat"] > 22.2) & (df_geo["lat"] < 22.9)
].copy()
print(f"In Shenzhen bounds: {{len(df_geo)}}")

# 推断小区类型
df_geo["community_type"] = df_geo.apply(
    lambda r: infer_community_type(r["housetitle"], r["money"]), axis=1
)

# 生成 GeoDataFrame
geometry = [Point(xy) for xy in zip(df_geo["lng"], df_geo["lat"])]
communities_gdf = gpd.GeoDataFrame(df_geo, geometry=geometry, crs="EPSG:4326")

# 生成 community_id (用 SQLite rowid)
communities_gdf = communities_gdf.reset_index(drop=True)
communities_gdf["community_id"] = range(1, len(communities_gdf) + 1)

# 重命名字段匹配 notebook 期望
communities_gdf = communities_gdf.rename(columns={{
    "housetitle": "name",
    "sqpinyin": "area_pinyin",
}})

# 添加模拟字段（如果需要）
# 实际研究应替换为真实人口/建成年份数据
communities_gdf["population"] = np.random.randint(500, 5000, size=len(communities_gdf))
communities_gdf["built_year"] = np.random.randint(2000, 2023, size=len(communities_gdf))
communities_gdf["area_m2"] = np.random.uniform(5000, 50000, size=len(communities_gdf))

# 中心点坐标
communities_gdf["center_lng"] = communities_gdf["lng"]
communities_gdf["center_lat"] = communities_gdf["lat"]

print("\nCommunity type distribution:")
print(communities_gdf["community_type"].value_counts())
print(f"\nTotal population: {{communities_gdf['population'].sum():,}}")
print(f"GeoDataFrame: {{len(communities_gdf)}} communities")
print("\n[OK] Real village data loaded. Ready for 2SFCA analysis.")
print("Next: Run vulnerability profiling, then 2SFCA on this communities_gdf")
'''.format(db_path=OUT_DIR.replace('\\', '\\\\'))

    return cell_code


def generate_nb_cells_for_insert():
    """生成 markdown + code cell 对"""
    md_cell = {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "<a id='village_data'></a>\n",
            "---\n",
            "\n",
            "## 真实小区数据：搜房数据集成\n",
            "\n",
            "### 数据来源\n",
            "\n",
            "使用搜房网 (SouFun) 2017年深圳小区数据替代模拟数据，涵盖：\n",
            "\n",
            "| 字段 | 说明 |\n",
            "|------|------|\n",
            "| `housetitle` | 小区名称 |\n",
            "| `address` | 详细地址 |\n",
            "| `quxian` | 区县（宝安/龙岗/南山等）|\n",
            "| `shangquan` | 商圈 |\n",
            "| `money` | 单价（元/平米）|\n",
            "| `lng/lat` | 经纬度（地理编码后）|\n",
            "\n",
            "**小区类型推断**：基于搜房单价 + 名称关键词组合判断\n",
            "\n",
            "> ⚠️ 注意：搜房数据为2017年快照，价格和部分小区信息可能已有变化。\n",
            "> 建议结合深圳市住建局现势数据或大众点评实况数据进行校验。"
        ]
    }

    code_cell = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [generate_notebook_cell()]
    }

    return md_cell, code_cell


# 写入可粘贴的代码文件
cell_code = generate_notebook_cell()
with open(NB_OUT, 'w', encoding='utf-8') as f:
    f.write(cell_code)

print("Generated notebook cell code:")
print("=" * 60)
print("File:", NB_OUT)
print("=" * 60)
print(cell_code)
