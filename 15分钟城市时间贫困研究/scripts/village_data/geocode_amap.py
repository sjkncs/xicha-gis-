"""
地理编码脚本 - 高德 API（快速，需要 API Key）
申请: https://lbs.amap.com/
免费额度: 5000次/日
"""
import re, os, sys, io, json, time, sqlite3, csv
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

OUT = Path(r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\village_data')
DB = OUT / 'villages.db'
CSV = OUT / 'sz_village_geocoded.csv'
GEOJSON = OUT / 'sz_village.geojson'

AMAP_KEY = os.environ.get('AMAP_API_KEY', 'c2d6e6faba4fba3311618be75e07cdee').strip()


def geocode_amap():
    import urllib.request, urllib.parse

    if not AMAP_KEY or len(AMAP_KEY) < 5:
        print('[ERROR] AMAP_API_KEY not set')
        print('  Set it: setx AMAP_API_KEY your_key')
        print('  Or: os.environ["AMAP_API_KEY"] = "your_key"')
        print('  Get key: https://lbs.amap.com/')
        return

    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT id, address, housetitle FROM sz_village WHERE lng IS NULL OR lng = 0").fetchall()
    conn.close()

    if not rows:
        print('No records needing geocoding')
        return

    print('Amap geocoding: ' + str(len(rows)) + ' records')
    print('Key: ' + AMAP_KEY[:6] + '...')
    print()

    ok = fail = 0
    results = []

    for i, (vid, addr, name) in enumerate(rows):
        addr_full = addr + ' ' + name
        try:
            params = urllib.parse.urlencode({
                'key': AMAP_KEY,
                'address': addr_full,
                'city': '深圳',
                'output': 'json'
            })
            url = 'https://restapi.amap.com/v3/geocode/geo?' + params
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            if result.get('status') == '1' and result.get('geocodes'):
                loc = result['geocodes'][0]['location'].split(',')
                lng = float(loc[0])
                lat = float(loc[1])
                if 113.5 < lng < 114.6 and 22.2 < lat < 22.9:
                    results.append((vid, lng, lat, 'OK'))
                    ok += 1
                else:
                    results.append((vid, None, None, 'OUT_OF_RANGE'))
                    fail += 1
            else:
                results.append((vid, None, None, 'NO_RESULT:' + result.get('info', '')[:20]))
                fail += 1
        except Exception as e:
            results.append((vid, None, None, 'ERR:' + str(e)[:20]))
            fail += 1

        if (i + 1) % 20 == 0:
            print('  ' + str(i + 1) + '/' + str(len(rows)) + '  ok=' + str(ok) + '  fail=' + str(fail))
        time.sleep(0.31)

    # 更新 SQLite
    print('Updating SQLite...')
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    for vid, lng, lat, status in results:
        cur.execute("UPDATE sz_village SET lng=?, lat=?, geocode_status=? WHERE id=?",
                    (lng, lat, status, vid))
    conn.commit()
    conn.close()

    # CSV
    conn = sqlite3.connect(DB)
    df = conn.execute("SELECT * FROM sz_village").fetchall()
    cols = [d[0] for d in conn.execute("PRAGMA table_info(sz_village)").fetchall()]
    conn.close()
    with open(CSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(df)

    # GeoJSON
    feats = []
    for vid, lng, lat, status in results:
        if lng and lat and status == 'OK':
            conn = sqlite3.connect(DB)
            rec = conn.execute("SELECT housetitle, quxian, shangquan, money FROM sz_village WHERE id=?", (vid,)).fetchone()
            conn.close()
            feats.append({
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [lng, lat]},
                'properties': {
                    'id': vid,
                    'name': rec[0] if rec else '',
                    'district': rec[1] if rec else '',
                    'area': rec[2] if rec else '',
                    'price': rec[3] if rec else 0,
                }
            })
    geo = {'type': 'FeatureCollection', 'crs': {'type': 'name', 'properties': {'name': 'EPSG:4326'}}, 'features': feats}
    with open(GEOJSON, 'w', encoding='utf-8') as f:
        json.dump(geo, f, ensure_ascii=False, indent=2)

    print('Done! ' + str(ok) + ' ok, ' + str(fail) + ' fail')
    print('  SQLite: ' + str(DB))
    print('  CSV: ' + str(CSV))
    print('  GeoJSON: ' + str(GEOJSON) + ' (' + str(len(feats)) + ' points)')


if __name__ == '__main__':
    geocode_amap()
