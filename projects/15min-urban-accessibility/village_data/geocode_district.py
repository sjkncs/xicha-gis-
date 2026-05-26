"""
用区中心估算生成坐标（快速方案，无API依赖）
对于演示和流程验证足够使用
"""
import sqlite3, json, os, io, sys, csv, math, numpy as np
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

OUT = Path(r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\village_data')
DB = OUT / 'villages.db'
CSV = OUT / 'sz_village_geocoded.csv'
GEOJSON = OUT / 'sz_village.geojson'

# 深圳各区中心坐标
DISTRICT_CENTROIDS = {
    # 区名: (lng, lat, 半径km)
    '宝安': (113.8828, 22.5553, 8),
    '龙岗': (114.2471, 22.7205, 10),
    '南山': (113.9308, 22.5332, 5),
    '福田': (114.0579, 22.5435, 4),
    '罗湖': (114.1317, 22.5482, 4),
    '盐田': (114.2361, 22.5557, 5),
    '光明': (113.9297, 22.7623, 6),
    '坪山': (114.3507, 22.6802, 5),
    '龙华': (114.0495, 22.7149, 6),
    '大鹏': (114.4871, 22.5817, 5),
    '福田保税区': (114.065, 22.525, 2),
    '前海': (113.898, 22.525, 3),
}

def district_for_record(quxian, shangquan, name):
    """根据区县/商圈/名称确定区"""
    quxian = str(quxian or '').strip()
    shangquan = str(shangquan or '').strip()
    name = str(name or '').strip()

    # 直接匹配
    for district in DISTRICT_CENTROIDS:
        if district in quxian or district in shangquan or district in name:
            return district

    # 别名
    aliases = {
        '宝安区': '宝安', '宝安中心区': '宝安', '西乡': '宝安',
        '龙岗区': '龙岗', '布吉': '龙岗', '坂田': '龙岗', '横岗': '龙岗',
        '南山区': '南山', '科技园': '南山', '后海': '南山', '蛇口': '南山',
        '福田区': '福田', '华强北': '福田', 'CBD': '福田',
        '罗湖区': '罗湖', '东门': '罗湖',
        '龙华区': '龙华', '民治': '龙华', '梅林关': '龙华',
        '光明区': '光明',
        '坪山区': '坪山',
    }
    for alias, district in aliases.items():
        if alias in quxian or alias in shangquan or alias in name:
            return district

    # 默认：宝安（数据量最大）
    return '宝安'


def km_to_deg_lng(lat, km):
    return km / 111.32 / math.cos(math.radians(lat))


def km_to_deg_lat(km):
    return km / 110.574


def generate_rough_coords(quxian, shangquan, name, vid):
    """为每条记录生成估算坐标"""
    district = district_for_record(quxian, shangquan, name)
    base_lng, base_lat, radius_km = DISTRICT_CENTROIDS[district]

    # 用vid作为随机种子，确保每次生成一致
    np.random.seed(int(vid) if vid else 0)
    offset_lng = np.random.uniform(-km_to_deg_lng(base_lat, radius_km),
                                    km_to_deg_lng(base_lat, radius_km))
    offset_lat = np.random.uniform(-km_to_deg_lat(radius_km),
                                    km_to_deg_lat(radius_km))

    lng = base_lng + offset_lng
    lat = base_lat + offset_lat
    return lng, lat, district


def main():
    print("Reading SQLite...")
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT id, quxian, shangquan, housetitle FROM sz_village").fetchall()
    conn.close()

    print(f"Generating rough coords for {len(rows)} records...")
    results = []
    district_counts = {}

    for vid, quxian, shangquan, name in rows:
        lng, lat, district = generate_rough_coords(quxian, shangquan, name, vid)
        district_counts[district] = district_counts.get(district, 0) + 1
        results.append((vid, lng, lat, district))

    # 更新 SQLite
    print("Updating SQLite...")
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    updated = 0
    for vid, lng, lat, district in results:
        cur.execute(
            "UPDATE sz_village SET lng=?, lat=?, geocode_status=? WHERE id=?",
            (lng, lat, 'district_centroid', vid)
        )
        updated += 1
    conn.commit()
    conn.close()

    print(f"Updated {updated} records")

    # 统计
    print("\nDistrict distribution:")
    for d, cnt in sorted(district_counts.items(), key=lambda x: -x[1]):
        print(f"  {d:8s}: {cnt:4d} ({100*cnt/len(rows):.1f}%)")

    # 保存CSV
    print("\nSaving CSV...")
    conn = sqlite3.connect(DB)
    df = conn.execute("SELECT * FROM sz_village").fetchall()
    cols = [d[0] for d in conn.execute("PRAGMA table_info(sz_village)").fetchall()]
    conn.close()
    with open(CSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(df)
    print(f"CSV: {CSV}")

    # 保存GeoJSON
    print("Saving GeoJSON...")
    feats = []
    conn = sqlite3.connect(DB)
    records = conn.execute(
        "SELECT id, housetitle, quxian, shangquan, money, lng, lat FROM sz_village"
    ).fetchall()
    conn.close()
    for rec in records:
        vid, name, quxian, shangquan, money, lng, lat = rec
        if lng and lat:
            feats.append({
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [float(lng), float(lat)]},
                'properties': {
                    'id': vid,
                    'name': name,
                    'district': quxian,
                    'area': shangquan,
                    'price': money,
                }
            })
    geo = {
        'type': 'FeatureCollection',
        'crs': {'type': 'name', 'properties': {'name': 'EPSG:4326'}},
        'features': feats
    }
    with open(GEOJSON, 'w', encoding='utf-8') as f:
        json.dump(geo, f, ensure_ascii=False, indent=2)
    print(f"GeoJSON: {GEOJSON} ({len(feats)} points)")

    print("\n[DONE] Rough coordinates generated from district centroids")
    print("Note: Coordinates are approximate, use for demonstration only")
    print("      For real analysis, use geocode_amap.py or geocode_llm.py")


if __name__ == '__main__':
    main()
