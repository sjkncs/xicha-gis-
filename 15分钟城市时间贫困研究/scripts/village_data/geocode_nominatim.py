"""
地理编码脚本 - Nominatim 免费（1/s）
适用于无 API Key 的情况
预计耗时: ~26分钟（1539条）
"""
import re, os, sys, io, json, time, sqlite3, csv
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

OUT = Path(r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\village_data')
DB = OUT / 'villages.db'
CSV = OUT / 'sz_village_geocoded.csv'
GEOJSON = OUT / 'sz_village.geojson'


def geocode_nominatim():
    """Nominatim 免费地理编码"""
    import urllib.request, urllib.parse

    # 读取 SQLite 中 pending 的记录
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT id, address, housetitle FROM sz_village WHERE lng IS NULL OR lng = 0").fetchall()
    conn.close()

    if not rows:
        print('No records needing geocoding')
        return

    print('Nominatim free geocoding: ' + str(len(rows)) + ' records')
    print('Estimated time: ~' + str(int(len(rows) * 1.1 / 60)) + ' minutes')
    print()

    ok = fail = 0
    results = []

    for i, (vid, addr, name) in enumerate(rows):
        addr_full = addr + ' ' + name
        try:
            url = 'https://nominatim.openstreetmap.org/search?'
            params = urllib.parse.urlencode({
                'q': addr_full, 'format': 'json', 'limit': '1',
                'addressdetails': '0'
            })
            req = urllib.request.Request(
                url + params,
                headers={
                    'User-Agent': 'GISResearchBot/1.0 (educational research)',
                    'Accept': 'application/json'
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            if data:
                lng = float(data[0]['lon'])
                lat = float(data[0]['lat'])
                # 过滤深圳范围
                if 113.5 < lng < 114.6 and 22.2 < lat < 22.9:
                    results.append((vid, lng, lat, 'OK'))
                    ok += 1
                else:
                    results.append((vid, None, None, 'OUT_OF_RANGE'))
                    fail += 1
            else:
                results.append((vid, None, None, 'NO_RESULT'))
                fail += 1
        except Exception as e:
            results.append((vid, None, None, 'ERR:' + str(e)[:20]))
            fail += 1

        if (i + 1) % 20 == 0:
            print('  ' + str(i + 1) + '/' + str(len(rows)) + '  ok=' + str(ok) + '  fail=' + str(fail))
        time.sleep(1.05)

    # 更新 SQLite
    print('Updating SQLite...')
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    for vid, lng, lat, status in results:
        cur.execute("UPDATE sz_village SET lng=?, lat=?, geocode_status=? WHERE id=?",
                    (lng, lat, status, vid))
    conn.commit()
    conn.close()

    # 保存 CSV
    conn = sqlite3.connect(DB)
    df = conn.execute("SELECT * FROM sz_village").fetchall()
    cols = [d[0] for d in conn.execute("PRAGMA table_info(sz_village)").fetchall()]
    conn.close()
    with open(CSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(df)

    # 生成 GeoJSON
    feats = []
    for vid, lng, lat, status in results:
        if lng and lat and status == 'OK':
            feats.append({
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [lng, lat]},
                'properties': {'id': vid}
            })
    geo = {'type': 'FeatureCollection', 'crs': {'type': 'name', 'properties': {'name': 'EPSG:4326'}}, 'features': feats}
    with open(GEOJSON, 'w', encoding='utf-8') as f:
        json.dump(geo, f, ensure_ascii=False, indent=2)

    print('Done! ' + str(ok) + ' ok, ' + str(fail) + ' fail')
    print('  SQLite updated: ' + str(DB))
    print('  CSV saved: ' + str(CSV))
    print('  GeoJSON: ' + str(GEOJSON) + ' (' + str(len(feats)) + ' points)')


if __name__ == '__main__':
    geocode_nominatim()
