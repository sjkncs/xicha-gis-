# -*- coding: utf-8 -*-
"""
为南山区生成真实感合成小区数据
用于 15min_urban_accessibility_SCI.ipynb 论文分析

策略：
1. 基于南山区实际分区（科技园、后海、南头、蛇口、西丽、粤海、沙河）生成小区
2. 使用 nanshan_poi_integrated.csv 的 POI 密度来推断各区域设施供给水平
3. 设施类型基于社区地理位置和名称关键词推断
4. 人口、面积、建成年代基于区域特征统计分布
"""
import os, sys, io, sqlite3, json
import numpy as np
import pandas as pd
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
OUT_DIR = os.path.join(BASE, "village_data")
DB_PATH = os.path.join(OUT_DIR, "villages.db")
POI_CSV = os.path.join(BASE, "osm_data", "nanshan_poi_integrated.csv")

np.random.seed(42)

# ============================================================
# 南山区各街道真实分区信息
# ============================================================
SUB_DISTRICTS = {
    "粤海": {
        "center": (113.935, 22.528),
        "radius": 0.028,
        "description": "深圳湾超级总部基地、高新区、大学城",
        "keywords": ["滨海", "海德", "科技", "高新", "深圳湾", "学府", "浪骑"],
        "typical_types": ["high_end", "commodity_housing"],
        "supply_base": 1.5,
        "built_year_range": (2005, 2023),
        "pop_range": (3000, 12000),
        "area_range": (20000, 120000),
        "weight": 0.22,
    },
    "南山": {
        "center": (113.918, 22.530),
        "radius": 0.022,
        "description": "南山街道办、南头古城",
        "keywords": ["南头", "前海", "豪方", "悠然", "桃花园"],
        "typical_types": ["urban_village", "commodity_housing"],
        "supply_base": 0.9,
        "built_year_range": (1990, 2015),
        "pop_range": (2000, 8000),
        "area_range": (8000, 60000),
        "weight": 0.18,
    },
    "蛇口": {
        "center": (113.904, 22.488),
        "radius": 0.025,
        "description": "蛇口港、太子湾、海上世界、渔人码头",
        "keywords": ["蛇口", "海上世界", "港湾", "半岛", "海韵", "渔村"],
        "typical_types": ["commodity_housing", "high_end", "urban_village"],
        "supply_base": 1.2,
        "built_year_range": (1985, 2022),
        "pop_range": (1500, 10000),
        "area_range": (10000, 80000),
        "weight": 0.14,
    },
    "科技园": {
        "center": (113.938, 22.545),
        "radius": 0.030,
        "description": "科技园南区、中区北区",
        "keywords": ["科技园", "科苑", "深铁", "汇景", "朗景", "英伦", "高新"],
        "typical_types": ["commodity_housing", "high_end"],
        "supply_base": 1.4,
        "built_year_range": (2000, 2023),
        "pop_range": (4000, 15000),
        "area_range": (30000, 150000),
        "weight": 0.20,
    },
    "西丽": {
        "center": (113.930, 22.578),
        "radius": 0.035,
        "description": "西丽大学城、留仙洞、茶光",
        "keywords": ["西丽", "留仙", "大学城", "茶光", "松坪", "珠光", "桃源"],
        "typical_types": ["urban_village", "affordable_housing", "commodity_housing"],
        "supply_base": 0.7,
        "built_year_range": (1988, 2020),
        "pop_range": (2000, 12000),
        "area_range": (5000, 80000),
        "weight": 0.14,
    },
    "沙河": {
        "center": (113.958, 22.528),
        "radius": 0.020,
        "description": "华侨城、欢乐谷、世界之窗",
        "keywords": ["华侨城", "沙河", "波托菲诺", "纯水岸", "天鹅堡", "香山里"],
        "typical_types": ["high_end", "commodity_housing"],
        "supply_base": 1.8,
        "built_year_range": (2000, 2023),
        "pop_range": (3000, 20000),
        "area_range": (40000, 200000),
        "weight": 0.12,
    },
}

# ============================================================
# 社区名称模板（结合区域特征）
# ============================================================
def make_community_name(sub_district, idx):
    """生成真实感的社区名称"""
    prefixes = [
        "星海", "金地", "华润", "中海", "万科", "招商", "华侨城",
        "花样年", "佳兆业", "龙光", "卓越", "华联", "天悦", "龙瑞",
        "阳光", "翠湖", "碧海", "金湾", "银湖", "玉泉", "宝安",
        "瑞景", "盛世", "雅居", "锦绣", "绿景", "振业", "金成",
    ]
    suffixes = {
        "粤海": ["花园", "雅园", "豪庭", "公馆", "苑", "邸", "居", "家园", "名苑", "邸"],
        "南山": ["村", "花园", "小区", "苑", "园", "居", "新区", "家园", "大厦"],
        "蛇口": ["花园", "邨", "村", "苑", "居", "园", "湾", "邸", "公馆"],
        "科技园": ["花园", "公馆", "邸", "名苑", "中心", "雅居", "豪庭", "府"],
        "西丽": ["村", "花园", "新区", "苑", "园", "居", "小区", "邨"],
        "沙河": ["花园", "公馆", "邸", "名苑", "雅居", "湾", "岸", "居"],
    }
    suffix_opt = suffixes.get(sub_district, ["花园", "苑", "居", "家园"])
    prefix = prefixes[idx % len(prefixes)]
    suffix = suffix_opt[idx % len(suffix_opt)]
    return prefix + suffix


def make_address(sub_district):
    """生成真实地址"""
    streets = {
        "粤海": ["南海大道", "科苑路", "高新南一道", "高新南七道", "深圳湾口岸"],
        "南山": ["南头街", "南新路", "学府路", "前海路", "桂庙路"],
        "蛇口": ["望海路", "太子路", "工业八路", "兴华路", "海滨社区"],
        "科技园": ["科技路", "科技中一路", "科发路", "朗山一路", "深南大道"],
        "西丽": ["西丽路", "留仙大道", "茶光路", "松坪山路", "珠光路"],
        "沙河": ["华侨城香山中街", "华侨城波托菲诺", "沙河东路", "世界之窗"],
    }
    options = streets.get(sub_district, ["南山区道路"])
    return "深圳市南山区" + np.random.choice(options) + str(np.random.randint(1, 200)) + "号"


# ============================================================
# 从 POI 密度计算区域供给水平（可选优化）
# ============================================================
print("分析 POI 密度以推断区域供给水平...")
if os.path.exists(POI_CSV):
    try:
        poi_sample = pd.read_csv(POI_CSV, nrows=5000)
        print(f"  加载 POI 样本: {len(poi_sample)} 条")
    except Exception as e:
        print(f"  POI 加载失败: {e}")
        poi_sample = None
else:
    print(f"  POI 文件不存在: {POI_CSV}")
    poi_sample = None


# ============================================================
# 生成小区数据
# ============================================================
N_TOTAL = 500  # 生成 500 个南山区小区
records = []

for sub_dist, info in SUB_DISTRICTS.items():
    n_sub = max(20, int(N_TOTAL * info["weight"]))
    sub_lng_c, sub_lat_c = info["center"]
    r = info["radius"]

    for i in range(n_sub):
        # 坐标：在区域内均匀分布
        angle = np.random.uniform(0, 2 * np.pi)
        dist = np.random.uniform(0, r)
        lng = sub_lng_c + dist * np.cos(angle)
        lat = sub_lat_c + dist * np.sin(angle)
        # 边界约束（南山区大致范围）
        lng = np.clip(lng, 113.85, 113.98)
        lat = np.clip(lat, 22.45, 22.62)

        # 小区名称
        global_idx = len(records)
        name = make_community_name(sub_dist, global_idx)

        # 小区类型
        type_probs = info["typical_types"]
        if len(type_probs) == 1:
            ctype = type_probs[0]
        else:
            ctype = np.random.choice(type_probs)

        # 建成年代
        yr_lo, yr_hi = info["built_year_range"]
        built_year = int(np.random.normal((yr_lo + yr_hi) / 2, (yr_hi - yr_lo) / 6))
        built_year = int(np.clip(built_year, yr_lo, yr_hi))

        # 人口
        pop_lo, pop_hi = info["pop_range"]
        if ctype == "urban_village":
            population = int(np.random.randint(int(pop_lo * 1.2), int(pop_hi * 1.5)))
        else:
            population = int(np.random.randint(pop_lo, pop_hi))

        # 面积
        area_lo, area_hi = info["area_range"]
        area_m2 = np.random.uniform(area_lo, area_hi)
        if ctype == "urban_village":
            area_m2 *= np.random.uniform(0.3, 0.8)  # 城中村密度高但规模小

        # 供给水平：基于 POI 密度优化
        supply_base = info["supply_base"]
        if poi_sample is not None:
            # 找最近邻 POI，夜间服务设施越多，供给越高
            try:
                poi_lng = poi_sample["gcj_lon"].values
                poi_lat = poi_sample["gcj_lat"].values
                night_flags = poi_sample["night_service_final"].values
                dists = np.sqrt((poi_lng - lng)**2 + (poi_lat - lat)**2)
                near_mask = dists < 0.01  # ~1km 半径
                near_night = near_mask.sum()
                if near_night > 0:
                    night_ratio = poi_sample.loc[poi_mask, "night_service_final"].mean() if (poi_mask := near_mask).any() else 0
                    supply = supply_base + night_ratio * 0.5 + np.random.uniform(-0.2, 0.2)
                else:
                    supply = supply_base + np.random.uniform(-0.3, 0.3)
            except Exception:
                supply = supply_base + np.random.uniform(-0.3, 0.3)
        else:
            supply = supply_base + np.random.uniform(-0.3, 0.3)

        supply = float(np.clip(supply, 0.3, 2.5))

        # 价格（元/月·平方米），用于推断小区类型
        if ctype == "urban_village":
            price = np.random.uniform(25, 50)
        elif ctype == "affordable_housing":
            price = np.random.uniform(50, 80)
        elif ctype == "commodity_housing":
            price = np.random.uniform(80, 150)
        else:
            price = np.random.uniform(150, 300)

        records.append({
            "id": len(records) + 1,
            "housetitle": name,
            "address": make_address(sub_dist),
            "quxian": "南山",
            "shangquan": sub_dist,
            "sqpinyin": sub_dist,
            "money": int(price * area_m2 / 10000),  # 模拟总价（万元）
            "price_per_m2": price,  # 元/月/m²
            "lng": round(lng, 6),
            "lat": round(lat, 6),
            "geocode_status": "OK",
            "community_type": ctype,
            "population": population,
            "built_year": built_year,
            "area_m2": round(area_m2, 2),
            "supply": round(supply, 3),
        })

print(f"\n生成了 {len(records)} 个南山区小区")

# 统计
import collections
type_cnt = collections.Counter(r["community_type"] for r in records)
sub_cnt = collections.Counter(r["shangquan"] for r in records)
print("\n小区类型分布:")
for t, c in type_cnt.most_common():
    print(f"  {t}: {c}")
print("\n街道分布:")
for s, c in sub_cnt.most_common():
    print(f"  {s}: {c}")

# ============================================================
# 保存到 SQLite
# ============================================================
print(f"\n保存到: {DB_PATH}")

# 重建数据库
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("""
    CREATE TABLE sz_village (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        housetitle TEXT NOT NULL,
        address TEXT,
        quxian TEXT,
        shangquan TEXT,
        sqpinyin TEXT,
        money INTEGER,
        lng REAL,
        lat REAL,
        geocode_status TEXT DEFAULT 'pending',
        community_type TEXT,
        population INTEGER,
        built_year INTEGER,
        area_m2 REAL,
        supply REAL,
        price_per_m2 REAL
    )
""")

for r in records:
    cur.execute("""
        INSERT INTO sz_village
        (housetitle, address, quxian, shangquan, sqpinyin, money, lng, lat,
         geocode_status, community_type, population, built_year, area_m2, supply, price_per_m2)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        r["housetitle"], r["address"], r["quxian"], r["shangquan"],
        r["sqpinyin"], r["money"], r["lng"], r["lat"],
        r["geocode_status"], r["community_type"], r["population"],
        r["built_year"], r["area_m2"], r["supply"], r["price_per_m2"]
    ))

conn.commit()
total = cur.execute("SELECT COUNT(*) FROM sz_village").fetchone()[0]
conn.close()

print(f"SQLite 保存完成: {total} 条记录")

# CSV 备份
csv_path = os.path.join(OUT_DIR, "nanshan_communities_synthetic.csv")
df = pd.DataFrame(records)
df.to_csv(csv_path, index=False, encoding="utf-8-sig")
print(f"CSV 备份: {csv_path}")

print("\n[完成] 下一步：在 notebook 中运行 load_village_data() 即可加载")
