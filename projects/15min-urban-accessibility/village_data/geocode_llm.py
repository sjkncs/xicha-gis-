"""
=======================================================================
LLM辅助地理编码脚本
=======================================================================
使用多模态大模型API直接理解中文地址，返回精确经纬度

优势:
  - 理解中文地址结构（省市区街道门牌）
  - 处理模糊/不完整地址
  - 返回置信度

使用方法:
  1. 设置 OPENAI_API_KEY / ANTHROPIC_API_KEY 环境变量
  2. python geocode_llm.py

依赖: openai 或 anthropic
=======================================================================
"""
import os, sys, io, json, time, sqlite3, csv, re
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

OUT = Path(r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\village_data')
DB = OUT / 'villages.db'
CSV = OUT / 'sz_village_geocoded.csv'
GEOJSON = OUT / 'sz_village.geojson'

# 深圳边界
SZ_BOUNDS = {'min_lng': 113.5, 'max_lng': 114.6, 'min_lat': 22.2, 'max_lat': 22.9}


def is_in_shenzhen(lng, lat):
    return (SZ_BOUNDS['min_lng'] < lng < SZ_BOUNDS['max_lng'] and
            SZ_BOUNDS['min_lat'] < lat < SZ_BOUNDS['max_lat'])


def parse_llm_response(text):
    """从LLM响应中解析经纬度"""
    text = text.strip()

    # 尝试JSON格式
    try:
        data = json.loads(text)
        if 'lng' in data and 'lat' in data:
            return float(data['lng']), float(data['lat'])
        if 'longitude' in data and 'latitude' in data:
            return float(data['longitude']), float(data['latitude'])
        if 'coordinates' in data:
            coords = data['coordinates']
            if isinstance(coords, list) and len(coords) == 2:
                return float(coords[0]), float(coords[1])
    except:
        pass

    # 尝试文本格式
    patterns = [
        r'经度[：:]\s*([\d.]+)[^\d]+纬度[：:]\s*([\d.]+)',
        r'lng[：:]\s*([\d.]+)[^\d]+lat[：:]\s*([\d.]+)',
        r'坐标[：:]\s*([\d.]+)[,\s]+([\d.]+)',
        r'([\d]{2}\.[\d]+)[,\s]+([\d]{2}\.[\d]+)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            lng, lat = float(m.group(1)), float(m.group(2))
            # 判断是否经度在前
            if 113 < lng < 115 and 22 < lat < 23:
                return lng, lat
            elif 113 < lat < 115 and 22 < lng < 23:
                return lat, lng

    return None, None


def geocode_openai(address_str):
    """使用 OpenAI GPT-4o 进行地理编码"""
    import openai
    client = openai.OpenAI(api_key=os.environ.get('OPENAI_API_KEY', ''))

    prompt = f"""你是一个地理编码专家。请根据以下中文地址返回其经纬度坐标。

地址：{address_str}
城市：广东省深圳市

请只返回JSON格式，不要解释：
{{"lng": 经度(6位小数), "lat": 纬度(6位小数), "confidence": 置信度(0-1)}}
如果无法确定，返回：{{"lng": null, "lat": null, "confidence": 0}}"""

    resp = client.chat.completions.create(
        model='gpt-4o',
        messages=[{'role': 'user', 'content': prompt}],
        temperature=0,
        max_tokens=100,
    )
    text = resp.choices[0].message.content
    return parse_llm_response(text)


def geocode_anthropic(address_str):
    """使用 Anthropic Claude 进行地理编码"""
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))

    prompt = f"""你是一个地理编码专家。请根据以下中文地址返回其经纬度坐标。

地址：{address_str}
城市：广东省深圳市

请只返回JSON格式，不要解释：
{{"lng": 经度(6位小数), "lat": 纬度(6位小数), "confidence": 置信度(0-1)}}
如果无法确定，返回：{{"lng": null, "lat": null, "confidence": 0}}"""

    resp = client.messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=100,
        messages=[{'role': 'user', 'content': prompt}],
    )
    text = resp.content[0].text
    return parse_llm_response(text)


def geocode_batch(addresses, batch_size=20, delay=1.0):
    """
    批量LLM地理编码
    addresses: list of (vid, full_address) tuples
    batch_size: 每批处理数量
    delay: 请求间隔(秒)
    """
    api_key = os.environ.get('OPENAI_API_KEY', '') or os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        print('[ERROR] No API key found')
        print('  Set: setx OPENAI_API_KEY your_key')
        print('  Or: setx ANTHROPIC_API_KEY your_key')
        return []

    results = []
    use_openai = bool(os.environ.get('OPENAI_API_KEY', ''))

    for i, (vid, addr) in enumerate(addresses):
        try:
            if use_openai:
                lng, lat = geocode_openai(addr)
            else:
                lng, lat = geocode_anthropic(addr)

            if lng and lat and is_in_shenzhen(lng, lat):
                results.append((vid, lng, lat, 'OK'))
            else:
                results.append((vid, None, None, 'OUT_OF_RANGE_OR_FAILED'))

            if (i + 1) % 10 == 0:
                print(f'  {i+1}/{len(addresses)}  ok={sum(1 for r in results if r[2])}  '
                      f'fail={sum(1 for r in results if r[2] is None)}')

        except Exception as e:
            results.append((vid, None, None, f'ERR:{str(e)[:20]}'))
        time.sleep(delay)

    return results


def main():
    # 读取待编码记录
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT id, address, housetitle FROM sz_village WHERE lng IS NULL OR lng = 0"
    ).fetchall()
    conn.close()

    if not rows:
        print('No records needing geocoding')
        return

    # 构造完整地址
    addresses = []
    for vid, addr, name in rows:
        full_addr = f"深圳市{addr} {name}"
        addresses.append((vid, full_addr))

    print(f'LLM geocoding: {len(addresses)} records')
    print(f'Provider: {"OpenAI" if os.environ.get("OPENAI_API_KEY") else "Anthropic"}')
    print(f'Estimated cost: ~${len(addresses) * 0.002:.2f} (OpenAI) or ~${len(addresses) * 0.001:.2f} (Claude)')
    print()

    # 分批处理（每批20条，1秒间隔，约需5分钟）
    BATCH = 20
    all_results = []
    for i in range(0, len(addresses), BATCH):
        batch = addresses[i:i + BATCH]
        print(f'Batch {i // BATCH + 1}/{(len(addresses) + BATCH - 1) // BATCH}: {batch[0][1][:40]}...')
        results = geocode_batch(batch, delay=0.5)
        all_results.extend(results)

    # 更新 SQLite
    print('Updating SQLite...')
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    for vid, lng, lat, status in all_results:
        cur.execute(
            "UPDATE sz_village SET lng=?, lat=?, geocode_status=? WHERE id=?",
            (lng, lat, status, vid)
        )
    conn.commit()
    conn.close()

    # 保存CSV
    conn = sqlite3.connect(DB)
    df = conn.execute("SELECT * FROM sz_village").fetchall()
    cols = [d[0] for d in conn.execute("PRAGMA table_info(sz_village)").fetchall()]
    conn.close()
    with open(CSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(df)

    # 保存GeoJSON
    feats = []
    conn = sqlite3.connect(DB)
    records = conn.execute(
        "SELECT id, housetitle, quxian, shangquan, money, lng, lat FROM sz_village WHERE lng IS NOT NULL AND lat IS NOT NULL"
    ).fetchall()
    conn.close()
    for rec in records:
        vid, name, quxian, shangquan, money, lng, lat = rec
        if is_in_shenzhen(lng, lat):
            feats.append({
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [lng, lat]},
                'properties': {
                    'id': vid, 'name': name, 'district': quxian,
                    'area': shangquan, 'price': money,
                }
            })
    geo = {
        'type': 'FeatureCollection',
        'crs': {'type': 'name', 'properties': {'name': 'EPSG:4326'}},
        'features': feats
    }
    with open(GEOJSON, 'w', encoding='utf-8') as f:
        json.dump(geo, f, ensure_ascii=False, indent=2)

    ok = sum(1 for r in all_results if r[2] is not None)
    fail = len(all_results) - ok
    print(f'Done! {ok} ok, {fail} fail')
    print(f'SQLite: {DB}')
    print(f'CSV: {CSV}')
    print(f'GeoJSON: {GEOJSON} ({len(feats)} points)')


if __name__ == '__main__':
    main()
