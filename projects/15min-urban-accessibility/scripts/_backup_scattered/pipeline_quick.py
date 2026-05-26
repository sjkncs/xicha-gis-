"""
快速完成 Pipeline（跳过耗时的地理编码步骤）
"""
import re, os, sys, io, json, sqlite3, csv
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(r'e:\xicha gis 智能定位\15分钟城市时间贫困研究')
SQL_PATH = Path(r'e:\xicha gis 智能定位\fang_2017-08-02.sql')
OUT = BASE_DIR / 'village_data'


def parse_sql(sql_path):
    with open(sql_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    city_map = {'t_bj_village': '北京', 't_gz_village': '广州', 't_sh_village': '上海', 't_sz_village': '深圳'}
    results = {}
    for table, city in city_map.items():
        insert_key = 'INSERT INTO `' + table + '`'
        pos = content.find(insert_key)
        if pos < 0:
            results[city] = []
            continue
        semi = content.find(';', pos + 10)
        block = content[pos:semi + 1] if semi > 0 else ''
        lines = block.split('\n')
        in_v = False
        records = []
        for line in lines:
            s = line.strip()
            if 'VALUES' in s.upper():
                in_v = True
                continue
            if not in_v or not s:
                continue
            # Match (digits, - handles tab prefix, Chinese chars after id
            if not re.match(r'\([\d]+,', s):
                continue
            row_text = s.lstrip('\t').rstrip(',;')
            vals = parse_row(row_text)
            if vals and len(vals) >= 7:
                records.append({
                    'city': city, 'id': safe_int(vals[0]),
                    'housetitle': clean_text(vals[1]),
                    'address': clean_text(vals[2]),
                    'quxian': clean_text(vals[3]),
                    'shangquan': clean_text(vals[4]),
                    'sqpinyin': clean_text(vals[5]),
                    'money': safe_int(vals[6]),
                    'image': vals[7] if len(vals) > 7 else '',
                    'lng': None, 'lat': None, 'geocode_status': 'pending'
                })
        results[city] = records
        print('  ' + city + ': ' + str(len(records)) + ' records')
    return results


def parse_row(s):
    vals, cur, in_str, qc = [], '', False, None
    for i, c in enumerate(s):
        if not in_str:
            if c in ("'", '"'):
                in_str, qc = True, c
            elif c == ',':
                vals.append(cur.strip().strip("'\""))
                cur = ''
            else:
                cur += c
        else:
            if c == qc and i + 1 < len(s) and s[i + 1] == qc:
                cur += qc; i += 1
            elif c == qc:
                in_str = False
            else:
                cur += c
    if cur.strip():
        vals.append(cur.strip().strip("'\""))
    return vals


def clean_text(t):
    if not t: return ''
    return t.strip().replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\')


def safe_int(v, d=0):
    try: return int(str(v).strip().strip("'\""))
    except: return d


def dedup(rs):
    seen, out = set(), []
    for r in rs:
        k = (r['housetitle'], r['address'], r['quxian'])
        if k in seen: continue
        seen.add(k)
        r['housetitle'] = re.sub(r'\s+', ' ', re.sub(r'[\[\]【】]', '', r['housetitle'])).strip()
        r['address'] = re.sub(r'\s+', ' ', r['address']).strip()
        r['address'] = r['city'] + r['address']
        if r['housetitle'] and len(r['housetitle']) >= 2:
            out.append(r)
    return out


def save_sqlite(rs, path):
    if os.path.exists(path): os.remove(path)
    conn = sqlite3.connect(path); cur = conn.cursor()
    cur.execute("""CREATE TABLE sz_village (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        housetitle TEXT, address TEXT, quxian TEXT,
        shangquan TEXT, sqpinyin TEXT, money INTEGER,
        lng REAL, lat REAL, geocode_status TEXT DEFAULT 'pending',
        orig_id INTEGER
    )""")
    cur.execute("CREATE INDEX idx_quxian ON sz_village(quxian)")
    cur.execute("CREATE INDEX idx_shangquan ON sz_village(shangquan)")
    for r in rs:
        cur.execute("INSERT OR IGNORE INTO sz_village (orig_id, housetitle, address, quxian, shangquan, sqpinyin, money, lng, lat, geocode_status) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (r['id'], r['housetitle'], r['address'], r['quxian'],
             r['shangquan'], r['sqpinyin'], r['money'],
             r.get('lng'), r.get('lat'), r.get('geocode_status', 'pending')))
    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM sz_village").fetchone()[0]
    conn.close()
    print('  SQLite: ' + str(path) + ' (' + str(total) + ' records)')
    return total


def save_csv(rs, path):
    fields = ['id', 'housetitle', 'address', 'quxian', 'shangquan', 'sqpinyin', 'money', 'lng', 'lat', 'geocode_status']
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rs)
    print('  CSV: ' + str(path) + ' (' + str(len(rs)) + ' rows)')


def save_mysql(data, path):
    lines = ['-- 小区数据 MySQL 导入脚本 | 2026-05-20',
              'SET NAMES utf8mb4; SET FOREIGN_KEY_CHECKS = 0;', '']
    table_map = {'北京': 't_bj_village', '广州': 't_gz_village', '上海': 't_sh_village', '深圳': 't_sz_village'}
    for city, table in table_map.items():
        rs = dedup(data.get(city, []))
        if not rs: continue
        lines += ['', '-- ' + city + ' (' + str(len(rs)) + ' records)',
                  'DROP TABLE IF EXISTS `' + table + '`;',
                  'CREATE TABLE `' + table + '` (',
                  '  `id` int NOT NULL, `housetitle` varchar(100), `address` varchar(200),',
                  '  `quxian` varchar(50), `shangquan` varchar(100),',
                  '  `sqpinyin` varchar(100), `money` int, `image` varchar(500),',
                  '  `lng` decimal(10,6), `lat` decimal(10,6), PRIMARY KEY(`id`)',
                  ') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;', '']
        for i in range(0, len(rs), 100):
            batch = rs[i:i+100]
            rows = []
            for r in batch:
                rows.append("('" + r['housetitle'].replace("'", "''") + "','"
                            + r['address'].replace("'", "''") + "','"
                            + r['quxian'].replace("'", "''") + "','"
                            + r['shangquan'].replace("'", "''") + "','"
                            + r['sqpinyin'].replace("'", "''") + "',"
                            + str(r['money']) + ",'"
                            + r['image'][:200].replace("'", "''") + "')")
            lines.append('INSERT INTO `' + table + '` VALUES ' + ','.join(rows) + ';')
        lines.append('')
    lines += ['SET FOREIGN_KEY_CHECKS = 1;', '-- Done']
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print('  MySQL: ' + str(path))


def save_notebook_code():
    nb_file = str(OUT / 'load_village_data.py')
    code = [
        '# -*- coding: utf-8 -*-',
        '"""小区数据加载 from fang_2017-08-02.sql | 2026-05-20 """',
        '',
        'import geopandas as gpd',
        'import pandas as pd',
        'import sqlite3',
        'import os',
        'from shapely.geometry import Point',
        '',
        'GEOJSON = r"' + str(OUT / 'sz_village.geojson').replace('\\', '\\\\') + '"',
        'CSV = r"' + str(OUT / 'sz_village_geocoded.csv').replace('\\', '\\\\') + '"',
        'DB = r"' + str(OUT / 'villages.db').replace('\\', '\\\\') + '"',
        '',
        'def load_gdf():',
        '    """从 GeoJSON 加载（有坐标时推荐）"""',
        '    if not os.path.exists(GEOJSON):',
        '        print("[INFO] GeoJSON not found:", GEOJSON)',
        '        return None',
        '    gdf = gpd.read_file(GEOJSON)',
        '    gdf = gdf.set_crs("EPSG:4326", allow_override=True)',
        '    print("Loaded: " + str(len(gdf)) + " villages")',
        '    return gdf',
        '',
        'def load_df():',
        '    """从 CSV 加载（无几何）"""',
        '    if not os.path.exists(CSV):',
        '        print("[INFO] CSV not found:", CSV)',
        '        return None',
        '    df = pd.read_csv(CSV, encoding="utf-8-sig")',
        '    print("Loaded: " + str(len(df)) + " rows (" + str(df["lng"].notna().sum()) + " with coords)")',
        '    return df',
        '',
        'def load_db_gdf():',
        '    """从 SQLite 加载 GeoDataFrame（无坐标时使用）"""',
        '    if not os.path.exists(DB):',
        '        print("[INFO] DB not found:", DB)',
        '        return None',
        '    conn = sqlite3.connect(DB)',
        '    df = pd.read_sql_query("SELECT * FROM sz_village", conn)',
        '    conn.close()',
        '    df_geo = df.dropna(subset=["lng", "lat"])',
        '    if len(df_geo) > 0:',
        '        gdf = gpd.GeoDataFrame(df_geo,',
        '            geometry=[Point(xy) for xy in zip(df_geo["lng"], df_geo["lat"])],',
        '            crs="EPSG:4326")',
        '    else:',
        '        gdf = gpd.GeoDataFrame(df, crs="EPSG:4326")',
        '    print("Loaded: " + str(len(gdf)) + " from DB")',
        '    return gdf',
        '',
        'if __name__ == "__main__":',
        '    gdf = load_db_gdf()',
        '    if gdf is not None:',
        '        print("\\nDistrict distribution:")',
        '        print(gdf["quxian"].value_counts() if "quxian" in gdf.columns else gdf["district"].value_counts())',
    ]
    with open(nb_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(code))
    print('  Notebook code: ' + nb_file)


print('=' * 55)
print('fang_2017-08-02.sql Pipeline (quick mode)')
print('=' * 55)

print('\n[1] Parsing SQL...')
data = parse_sql(SQL_PATH)

print('\n[2] Deduplicate & Stats...')
for city in data:
    before = len(data[city])
    data[city] = dedup(data[city])
    print('  ' + city + ': ' + str(before) + ' -> ' + str(len(data[city])))

sz = data.get('深圳', [])
print('\n  Shenzhen districts:')
qx = {}
for r in sz:
    q = r['quxian']
    qx[q] = qx.get(q, 0) + 1
for k, v in sorted(qx.items(), key=lambda x: -x[1]):
    print('    ' + k + ': ' + str(v))
print('    Total: ' + str(len(sz)))

print('\n[3] Save SQLite...')
save_sqlite(sz, OUT / 'villages.db')

print('\n[4] Save CSV...')
save_csv(sz, OUT / 'sz_village_geocoded.csv')

print('\n[5] Save MySQL script...')
save_mysql(data, OUT / 'import_villages.sql')

print('\n[6] Notebook integration code...')
save_notebook_code()

print('\n[7] GeoJSON placeholder...')
empty_gj = {'type': 'FeatureCollection', 'crs': {'type': 'name', 'properties': {'name': 'EPSG:4326'}}, 'features': []}
with open(OUT / 'sz_village.geojson', 'w', encoding='utf-8') as f:
    json.dump(empty_gj, f, ensure_ascii=False, indent=2)

print('\n' + '=' * 55)
print('All done! Output: ' + str(OUT))
print('=' * 55)

msg = '\nNEXT STEPS:\n'
msg += '1. Geocoding: Set AMAP_API_KEY env var, then:\n'
msg += '   python geocode_and_geojson.py\n'
msg += '2. Free geocoding (slow ~25min):\n'
msg += '   python geocode_nominatim.py\n'
msg += '3. In notebook, paste this into a new cell:\n'
nb_path = str(OUT / 'load_village_data.py').replace('\\', '\\\\')
msg += '   exec(open(r"' + nb_path + '").read())\n'
msg += '   village_gdf = load_db_gdf()\n'
print(msg)
