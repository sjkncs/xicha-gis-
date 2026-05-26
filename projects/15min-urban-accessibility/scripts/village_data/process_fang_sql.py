"""
=======================================================================
fang_2017-08-02.sql 数据处理 Pipeline v2
修复：正确解析 Sequel Pro 多行 VALUES 格式
=======================================================================
"""
import re, os, sys, io, json, time, sqlite3, csv
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(r'e:\xicha gis 智能定位\15分钟城市时间贫困研究')
SQL_PATH = Path(r'e:\xicha gis 智能定位\fang_2017-08-02.sql')
OUT = BASE_DIR / 'village_data'
OUT.mkdir(exist_ok=True)


def parse_sql(sql_path):
    """解析 Sequel Pro SQL 文件"""
    with open(sql_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    city_map = {
        't_bj_village': '北京',
        't_gz_village': '广州',
        't_sh_village': '上海',
        't_sz_village': '深圳',
    }
    tables = re.findall(r'# Dump of table (t_\w+)', content)
    results = {}

    for table in tables:
        city = city_map.get(table, table)
        results[city] = []

        # 找这个表的 INSERT 块（从 INSERT 到 ;）
        insert_key = 'INSERT INTO `' + table + '`'
        pos = content.find(insert_key)
        if pos < 0:
            print('[WARN] ' + city + ': 未找到 INSERT')
            continue

        semi = content.find(';', pos + 10)
        block = content[pos:semi + 1] if semi > 0 else content[pos:pos + 500000]

        # 提取 VALUES 后的所有 (数字开头 的行
        lines = block.split('\n')
        in_values = False
        for line in lines:
            stripped = line.strip()
            if 'VALUES' in stripped.upper():
                in_values = True
                continue
            if not in_values:
                continue
            # 跳过空行
            if not stripped:
                continue
            # 匹配数据行: (数字,'开头
            if re.match(r"\(\d+,", stripped):
                # 清理行首tab和行尾逗号
                row_text = stripped.lstrip('\t').rstrip(',').rstrip(';')
                vals = parse_one_row(row_text)
                if vals and len(vals) >= 7:
                    results[city].append({
                        'city': city,
                        'id': safe_int(vals[0]),
                        'housetitle': clean_text(vals[1]),
                        'address': clean_text(vals[2]),
                        'quxian': clean_text(vals[3]),
                        'shangquan': clean_text(vals[4]),
                        'sqpinyin': clean_text(vals[5]),
                        'money': safe_int(vals[6]),
                        'image': vals[7] if len(vals) > 7 else '',
                    })

        print('  ' + city + ': ' + str(len(results[city])) + ' records')

    return results


def parse_one_row(row_str):
    """解析单行 VALUES，精确处理引号和转义"""
    vals = []
    current = ''
    in_str = False
    str_char = None
    i = 0

    while i < len(row_str):
        c = row_str[i]

        if not in_str:
            if c in ("'", '"'):
                in_str = True
                str_char = c
            elif c == ',':
                vals.append(current.strip().strip("'\""))
                current = ''
            else:
                current += c
        else:
            # 在字符串内
            if c == str_char and i + 1 < len(row_str) and row_str[i + 1] == str_char:
                # SQL 转义引号 ''
                current += str_char
                i += 1
            elif c == str_char:
                in_str = False
            else:
                current += c
        i += 1

    if current.strip():
        vals.append(current.strip().strip("'\""))
    return vals


def clean_text(text):
    if not text:
        return ''
    text = text.strip()
    text = text.replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\')
    return text


def safe_int(val, default=0):
    try:
        return int(str(val).strip().strip("'\""))
    except Exception:
        return default


def dedup(records):
    seen = set()
    out = []
    for r in records:
        key = (r['housetitle'], r['address'], r['quxian'])
        if key in seen:
            continue
        seen.add(key)
        r['housetitle'] = re.sub(r'\s+', ' ', re.sub(r'[\[\]【】]', '', r['housetitle'])).strip()
        r['address'] = re.sub(r'\s+', ' ', r['address']).strip()
        r['address'] = r['city'] + r['address']
        if r['housetitle'] and len(r['housetitle']) >= 2:
            out.append(r)
    return out


def save_csv(records, path):
    fields = ['id', 'housetitle', 'address', 'quxian', 'shangquan', 'sqpinyin', 'money', 'lng', 'lat', 'geocode_status']
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(records)
    print('CSV: ' + str(path) + ' (' + str(len(records)) + ' rows)')


def save_sqlite(records, path, with_coords=False):
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE sz_village (
            id INTEGER PRIMARY KEY,
            housetitle TEXT, address TEXT, quxian TEXT,
            shangquan TEXT, sqpinyin TEXT, money INTEGER,
            lng REAL, lat REAL, geocode_status TEXT DEFAULT 'pending'
        )
    """)
    cur.execute("CREATE INDEX idx_quxian ON sz_village(quxian)")
    cur.execute("CREATE INDEX idx_shangquan ON sz_village(shangquan)")
    for r in records:
        cur.execute(
            "INSERT OR IGNORE INTO sz_village VALUES (?,?,?,?,?,?,?,?,?,?)",
            (r['id'], r['housetitle'], r['address'], r['quxian'],
             r['shangquan'], r['sqpinyin'], r['money'],
             r.get('lng'), r.get('lat'), r.get('geocode_status', 'pending'))
        )
    conn.commit()
    conn.close()
    print('SQLite: ' + str(path) + ' (' + str(len(records)) + ' rows)')


def geocode_amap(address, api_key):
    import urllib.request, urllib.parse
    if not api_key:
        return None, None, 'NO_KEY'
    try:
        url = 'https://restapi.amap.com/v3/geocode/geo?key=' + api_key
        params = urllib.parse.urlencode({'address': address, 'city': '深圳'})
        req = urllib.request.Request(url + '&' + params, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        if result.get('status') == '1' and result.get('geocodes'):
            loc = result['geocodes'][0]['location'].split(',')
            return float(loc[0]), float(loc[1]), 'OK'
        return None, None, 'NO_RESULT'
    except Exception as e:
        return None, None, str(e)[:30]


def geocode_nominatim(records, out_csv):
    import urllib.request, urllib.parse
    print('Nominatim free geocoding (' + str(len(records)) + ' records, 1/s)...')
    results = []
    ok = fail = 0
    for i, r in enumerate(records):
        addr = r['address'] + ' ' + r['housetitle']
        try:
            url = 'https://nominatim.openstreetmap.org/search?'
            params = urllib.parse.urlencode({'q': addr, 'format': 'json', 'limit': '1'})
            req = urllib.request.Request(url + params, headers={
                'User-Agent': 'GISResearchBot/1.0 (educational)',
                'Accept': 'application/json'
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            if data:
                r['lng'] = float(data[0]['lon'])
                r['lat'] = float(data[0]['lat'])
                r['geocode_status'] = 'OK'
                ok += 1
            else:
                r['lng'] = None
                r['lat'] = None
                r['geocode_status'] = 'NO_RESULT'
                fail += 1
        except Exception as e:
            r['lng'] = None
            r['lat'] = None
            r['geocode_status'] = 'ERR:' + str(e)[:20]
            fail += 1
        results.append(r)
        if (i + 1) % 20 == 0:
            print('  ' + str(i + 1) + '/' + str(len(records)) + '  ok=' + str(ok))
        time.sleep(1.05)
    print('Done: ' + str(ok) + ' ok, ' + str(fail) + ' fail')
    save_csv(results, out_csv)
    return results


def save_geojson(records, path):
    feats = []
    for r in records:
        try:
            if not r.get('lng') or not r.get('lat'):
                continue
            lng, lat = float(r['lng']), float(r['lat'])
            if not (113.5 < lng < 114.6 and 22.2 < lat < 22.9):
                continue
            feats.append({
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [lng, lat]},
                'properties': {
                    'id': r['id'], 'name': r['housetitle'],
                    'address': r['address'], 'district': r['quxian'],
                    'area': r['shangquan'], 'price': r['money'],
                    'area_pinyin': r['sqpinyin'],
                }
            })
        except Exception:
            continue
    geo = {'type': 'FeatureCollection', 'crs': {'type': 'name', 'properties': {'name': 'EPSG:4326'}}, 'features': feats}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(geo, f, ensure_ascii=False, indent=2)
    print('GeoJSON: ' + str(path) + ' (' + str(len(feats)) + ' valid points)')


def save_notebook_code(out_path):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    code = (
        '# -*- coding: utf-8 -*-\n'
        '"""小区数据加载 from fang_2017-08-02.sql | ' + ts + ' """\n'
        'import geopandas as gpd\n'
        'import pandas as pd\n'
        'import sqlite3\n'
        'import os\n'
        'from shapely.geometry import Point\n\n'
        'GEOJSON = r"' + str(OUT / 'sz_village.geojson') + '"\n'
        'CSV = r"' + str(OUT / 'sz_village_geocoded.csv') + '"\n'
        'DB = r"' + str(OUT / 'villages.db') + '"\n\n'
        'def load_gdf():\n'
        '    """从 GeoJSON 加载（推荐）"""\n'
        '    if not os.path.exists(GEOJSON):\n'
        '        print("[WARN] GeoJSON not found:", GEOJSON)\n'
        '        return None\n'
        '    gdf = gpd.read_file(GEOJSON)\n'
        '    gdf = gdf.set_crs("EPSG:4326", allow_override=True)\n'
        '    print("Loaded: " + str(len(gdf)) + " villages")\n'
        '    return gdf\n\n'
        'def load_df():\n'
        '    """从 CSV 加载"""\n'
        '    if not os.path.exists(CSV):\n'
        '        print("[WARN] CSV not found:", CSV)\n'
        '        return None\n'
        '    df = pd.read_csv(CSV, encoding="utf-8-sig")\n'
        '    print("Loaded: " + str(len(df)) + " rows, "\n'
        '          + str(df["lng"].notna().sum()) + " with coordinates")\n'
        '    return df\n\n'
        'def load_db_gdf():\n'
        '    """从 SQLite 加载为 GeoDataFrame"""\n'
        '    if not os.path.exists(DB):\n'
        '        print("[WARN] DB not found:", DB)\n'
        '        return None\n'
        '    conn = sqlite3.connect(DB)\n'
        '    df = pd.read_sql_query("SELECT * FROM sz_village", conn)\n'
        '    conn.close()\n'
        '    df_geo = df.dropna(subset=["lng", "lat"])\n'
        '    gdf = gpd.GeoDataFrame(\n'
        '        df_geo,\n'
        '        geometry=[Point(xy) for xy in zip(df_geo["lng"], df_geo["lat"])],\n'
        '        crs="EPSG:4326"\n'
        '    ) if len(df_geo) > 0 else gpd.GeoDataFrame(df, crs="EPSG:4326")\n'
        '    print("Loaded: " + str(len(gdf)) + " from DB")\n'
        '    return gdf\n\n'
        'if __name__ == "__main__":\n'
        '    gdf = load_gdf()\n'
        '    if gdf is not None:\n'
        '        print("\\nDistrict distribution:")\n'
        '        print(gdf["district"].value_counts())\n'
    )
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(code)
    print('Notebook code: ' + str(out_path))


def main():
    print('=' * 60)
    print('fang_2017-08-02.sql Pipeline v2')
    print('=' * 60)

    # Parse
    print('\n=== Step 1: Parse ===')
    data = parse_sql(SQL_PATH)

    # Deduplicate & stats
    print('\n=== Step 2: Deduplicate & Stats ===')
    for city in data:
        before = len(data[city])
        data[city] = dedup(data[city])
        print('  ' + city + ': ' + str(before) + ' -> ' + str(len(data[city])) + ' (after dedup)')

    # Shenzhen stats
    sz = data.get('深圳', [])
    quxian_dist = {}
    for r in sz:
        q = r['quxian']
        quxian_dist[q] = quxian_dist.get(q, 0) + 1
    print('\n  Shenzhen district distribution:')
    for k, v in sorted(quxian_dist.items(), key=lambda x: -x[1]):
        print('    ' + k + ': ' + str(v))
    print('  Total: ' + str(len(sz)) + ' villages')

    # Save SQLite
    print('\n=== Step 3: SQLite ===')
    save_sqlite(sz, OUT / 'villages.db')

    # Save CSV
    print('\n=== Step 4: CSV ===')
    save_csv(sz, OUT / 'sz_village_geocoded.csv')

    # Geocoding
    amap_key = os.environ.get('AMAP_API_KEY', '').strip()
    csv_out = OUT / 'sz_village_geocoded.csv'
    if amap_key and len(amap_key) > 5:
        print('\n=== Step 5: Geocoding (Amap API) ===')
        # batch 10 at a time for rate limit
        geocoded = []
        for i in range(0, len(sz), 10):
            batch = sz[i:i + 10]
            for r in batch:
                addr = r['address'] + ' ' + r['housetitle']
                lng, lat, status = geocode_amap(addr, amap_key)
                r['lng'] = lng
                r['lat'] = lat
                r['geocode_status'] = status
                geocoded.append(r)
            print('  ' + str(min(i + 10, len(sz))) + '/' + str(len(sz)))
            time.sleep(0.35)
        save_csv(geocoded, csv_out)
    else:
        print('\n=== Step 5: Geocoding (Nominatim free, 1/s) ===')
        print('  Set AMAP_API_KEY env var for faster geocoding')
        geocoded = geocode_nominatim(sz, csv_out)

    # Update SQLite
    print('\n=== Step 6: Update SQLite ===')
    save_sqlite(geocoded, OUT / 'villages.db', with_coords=True)

    # GeoJSON
    print('\n=== Step 7: GeoJSON ===')
    save_geojson(geocoded, OUT / 'sz_village.geojson')

    # Notebook code
    print('\n=== Step 8: Notebook Integration ===')
    save_notebook_code(OUT / 'load_village_data.py')

    print('\n' + '=' * 60)
    print('Done!')
    print('Files: ' + str(OUT))
    print('  import_villages.sql')
    print('  villages.db')
    print('  sz_village_geocoded.csv')
    print('  sz_village.geojson')
    print('  load_village_data.py')


if __name__ == '__main__':
    main()
