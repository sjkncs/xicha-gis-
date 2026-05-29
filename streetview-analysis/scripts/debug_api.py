"""Debug Baidu street view API"""
import requests, json, re, random, time, math, os

x_pi = 3.14159265358979324 * 3000.0 / 180.0
pi = 3.1415926535897932384626
a = 6378245.0
ee = 0.00669342162296594323

def wgs84togcj02(lng, lat):
    dlat = transformlat(lng - 105.0, lat - 35.0)
    dlng = transformlng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi)
    return [lng + dlng, lat + dlat]

def gcj02tobd09(lng, lat):
    z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * x_pi)
    theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * x_pi)
    return [z * math.cos(theta) + 0.0065, z * math.sin(theta) + 0.006]

def wgstobd09(lon, lat):
    tmplon, tmplat = wgs84togcj02(lon, lat)
    return gcj02tobd09(tmplon, tmplat)

def bd09tomercator(lng, lat):
    class LLT:
        def __init__(self, x, y): self.x = x; self.y = y
    LLBAND = [75, 60, 45, 30, 15, 0]
    LL2MC = [
        [-0.0015702102444, 111320.7020616939, 1704480524535203, -10338987376042340, 26112667856603880, -35149669176653700, 26595700718403920, -10725012454188240, 1800819912950474, 82.5],
        [0.0008277824516172526, 111320.7020463578, 647795574.6671607, -4082003173.641316, 10774905663.51142, -15171875531.51559, 12053065338.62167, -5124939663.577472, 913311935.9512032, 67.5],
        [0.00337398766765, 111320.7020202162, 4481351.045890365, -23393751.19931662, 79682215.47186455, -115964993.2797253, 97236711.15602145, -43661946.33752821, 8477230.501135234, 52.5],
        [0.00220636496208, 111320.7020209128, 51751.86112841131, 3796837.749470245, 992013.7397791013, -1221952.21711287, 1340652.697009075, -620943.6990984312, 144416.9293806241, 37.5],
        [-0.0003441963504368392, 111320.7020576856, 278.2353980772752, 2485758.690035394, 6070.750963243378, 54821.18345352118, 9540.606633304236, -2710.55326746645, 1405.483844121726, 22.5],
        [-0.0003218135878613132, 111320.7020701615, 0.00369383431289, 823725.6402795718, 0.46104986909093, 2351.343141331292, 1.58060784298199, 8.77738589078284, 0.37238884252424, 7.45],
    ]
    def getRange(cC, cB, T):
        if cB is not None: cC = max(cC, cB)
        if T is not None: cC = min(cC, T)
        return cC
    def getLoop(cC, cB, T):
        while cC > T: cC -= T - cB
        while cC < cB: cC += T - cB
        return cC
    def convertor(cC, cD):
        T = cD[0] + cD[1] * abs(cC.x)
        cB = abs(cC.y) / cD[9]
        cE = cD[2] + cD[3]*cB + cD[4]*cB*cB + cD[5]*cB**3 + cD[6]*cB**4 + cD[7]*cB**5 + cD[8]*cB**6
        if cC.x < 0: T = T * -1
        if cC.y < 0: cE = cE * -1
        return [T, cE]
    t = LLT(getLoop(lng, -180, 180), getRange(lat, -74, 74))
    cD = None
    for cC in range(len(LLBAND)):
        if t.y >= LLBAND[cC]: cD = LL2MC[cC]; break
    if cD is None:
        for cC in range(len(LLBAND) - 1, -1, -1):
            if t.y <= -LLBAND[cC]: cD = LL2MC[cC]; break
    return convertor(t, cD)

def transformlat(lng, lat):
    ret = -100.0 + 2.0*lng + 3.0*lat + 0.2*lat*lat + 0.1*lng*lat + 0.2*math.sqrt(math.fabs(lng))
    ret += (20.0*math.sin(6.0*lng*pi) + 20.0*math.sin(2.0*lng*pi)) * 2.0/3.0
    ret += (20.0*math.sin(lat*pi) + 40.0*math.sin(lat/3.0*pi)) * 2.0/3.0
    ret += (160.0*math.sin(lat/12.0*pi) + 320*math.sin(lat*pi/30.0)) * 2.0/3.0
    return ret

def transformlng(lng, lat):
    ret = 300.0 + lng + 2.0*lat + 0.1*lng*lng + 0.1*lng*lat + 0.1*math.sqrt(math.fabs(lng))
    ret += (20.0*math.sin(6.0*lng*pi) + 20.0*math.sin(2.0*lng*pi)) * 2.0/3.0
    ret += (20.0*math.sin(lng*pi) + 40.0*math.sin(lng/3.0*pi)) * 2.0/3.0
    ret += (150.0*math.sin(lng/12.0*pi) + 300.0*math.sin(lng/30.0*pi)) * 2.0/3.0
    return ret

lon, lat = 113.9263685, 22.5129279
bd = wgstobd09(lon, lat)
mc = bd09tomercator(bd[0], bd[1])
print(f"WGS84: {lon}, {lat}")
print(f"BD09: {bd[0]:.6f}, {bd[1]:.6f}")
print(f"Mercator: {mc[0]:.6f}, {mc[1]:.6f}")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://map.baidu.com/',
    'Accept': '*/*',
}

# Step 1: get sid
ts = int(time.time() * 1000)
sid_params = {
    'udt': time.strftime('%Y%m%d'),
    'action': 0,
    'x': mc[0],
    'y': mc[1],
    'l': 18.367179030452565,
    'mode': 'day',
    't': ts,
    'fn': 'jsonp1',
    'qt': 'qsdata',
}
print(f"\n[Step 1] Getting SID for coordinate...")
try:
    r = requests.get('https://mapsv0.bdimg.com/', params=sid_params, headers=headers, timeout=(5, 10))
    print(f"  status={r.status_code}, ct={r.headers.get('Content-Type','N/A')}, size={len(r.content)}")
    print(f"  response: {r.text[:500]}")
    if r.content:
        print(f"  first bytes: {r.content[:20].hex()}")

    # Parse SID
    sid = json.loads(r.text.split('(')[1].split(')')[0])['content']['id']
    print(f"\n  -> SID: {sid}")

    # Step 2: get timeline (with target years 2022-2025)
    target_years = [2022, 2023, 2024, 2025]
    bdsid_params = {
        'sid': sid,
        'pc': 1,
        'udt': time.strftime('%Y%m%d'),
        'fn': 'jsonp2',
        'qt': 'sdata',
    }
    print(f"\n[Step 2] Getting timeline...")
    try:
        r2 = requests.get('https://mapsv0.bdimg.com/', params=bdsid_params, headers=headers, timeout=(5, 10))
        print(f"  status={r2.status_code}, ct={r2.headers.get('Content-Type','N/A')}, size={len(r2.content)}")

        # Better JSON parsing - handle potential truncation
        raw = r2.content
        # Find the actual JSON start and end
        start = raw.find(b'(') + 1
        end = raw.rfind(b')')
        if start > 0 and end > start:
            json_str = raw[start:end].decode('utf-8', errors='replace')
        else:
            json_str = raw.decode('utf-8', errors='replace')

        print(f"  JSON length: {len(json_str)}")
        print(f"  JSON preview: {json_str[:500]}")

        j = json.loads(json_str)
        direction = float(j['content'][0]['MoveDir'])
        print(f"  Direction: {direction} deg")

        for i in range(len(j['content'][0]['TimeLine'])):
            tl_year = j['content'][0]['TimeLine'][i]['Year']
            tl_id = j['content'][0]['TimeLine'][i]['ID']
            print(f"    Timeline[{i}]: year={tl_year}, id={tl_id}")

        # Try each target year
        for year in target_years:
            timeid = None
            for i in range(len(j['content'][0]['TimeLine'])):
                if int(j['content'][0]['TimeLine'][i]['Year']) == year:
                    timeid = j['content'][0]['TimeLine'][i]['ID']
                    break
            if timeid:
                print(f"\n  -> Using year {year}, timeid: {timeid}")
            else:
                print(f"\n  -> No data for year {year}, skipping")
                continue

            # Step 3: get images for 4 directions
            for head in [0, 90, 180, 270]:
                img_params = {
                    'fovy': 90,
                    'quality': 100,
                    'panoid': timeid,
                    'heading': (head + direction) % 360,
                    'width': 512,
                    'height': 512,
                    'qt': 'pr3d',
                }
                print(f"\n[Step 3] heading={head} (adjusted={img_params['heading']})...")
                try:
                    r3 = requests.get('https://mapsv0.bdimg.com/', params=img_params, headers=headers, timeout=(5, 10))
                    ct = r3.headers.get('Content-Type', '')
                    size = len(r3.content)
                    print(f"  status={r3.status_code}, ct={ct}, size={size}")
                    first_bytes = r3.content[:8].hex()
                    print(f"  first bytes: {first_bytes}")

                    # Save based on JPEG magic bytes
                    is_jpeg = r3.content[:2] == b'\xff\xd8'
                    print(f"  is_jpeg={is_jpeg}")

                    if is_jpeg and size > 1000:
                        savepath = f"picture_test/{head}_{year}.jpg"
                        os.makedirs("picture_test", exist_ok=True)
                        with open(savepath, 'wb') as f:
                            f.write(r3.content)
                        print(f"  -> SAVED: {savepath}")
                    elif size > 0:
                        savepath = f"picture_test/{head}_{year}_raw.bin"
                        os.makedirs("picture_test", exist_ok=True)
                        with open(savepath, 'wb') as f:
                            f.write(r3.content)
                        print(f"  -> Saved raw (not JPEG): {savepath}")
                except Exception as e:
                    print(f"  ERROR: {e}")

            break  # Found the year, stop

    except Exception as e:
        print(f"  ERROR parsing timeline: {e}")

except Exception as e:
    print(f"ERROR: {e}")
