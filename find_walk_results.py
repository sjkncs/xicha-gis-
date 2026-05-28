import os, json, glob

# Search for the output files
search_dirs = [
    r'e:\xicha gis 智能定位\projects\15min-urban-accessibility\algorithms\deep_learning\dl_pipeline',
    r'e:\xicha gis 智能定位\projects\15min-urban-accessibility\data\dl_pipeline',
    r'e:\xicha gis 智能定位',
]

for search_dir in search_dirs:
    if not os.path.exists(search_dir):
        continue
    for root, dirs, files in os.walk(search_dir):
        for f in files:
            if 'vlm_walkability' in f.lower() or 'vlm_walk' in f.lower():
                path = os.path.join(root, f)
                print(f'=== {path} ===')
                try:
                    if f.endswith('.json'):
                        with open(path, 'r', encoding='utf-8') as fp:
                            data = json.load(fp)
                        for item in data:
                            raw = item.get('raw_response', '')
                            print(f'  sample_id: {item.get("sample_id", "?")}')
                            print(f'  raw_response ({len(raw)} chars):')
                            print(raw[:1500])
                            print(f'  parsed: SCR={item.get("scr")} GVR={item.get("gvr")} VVR={item.get("vvr")} CSR={item.get("csr")} urban_form={item.get("urban_form")}')
                            print()
                    elif f.endswith('.csv'):
                        with open(path, 'r', encoding='utf-8-sig') as fp:
                            lines = fp.readlines()
                        print(f'  CSV ({len(lines)} lines):')
                        for l in lines[:10]:
                            print(f'    {l.strip()}')
                except Exception as e:
                    print(f'  Error: {e}')
