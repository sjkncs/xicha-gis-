import os, json

base = r'e:\xicha gis 智能定位'
for root, dirs, files in os.walk(base):
    for f in files:
        if 'vlm_walkability' in f.lower():
            path = os.path.join(root, f)
            print(f'Found: {path}')
            try:
                with open(path, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                for item in data:
                    print(f'=== {item["sample_id"]} ===')
                    print(item['raw_response'][:800])
                    print(f'SCR={item["scr"]} GVR={item["gvr"]} VVR={item["vvr"]} CSR={item["csr"]}')
                    print()
            except Exception as e:
                print(f'Error: {e}')
