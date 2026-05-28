import os, json

# Find latest vlm_walkability results
base = r'e:\xicha gis 智能定位\projects\15min-urban-accessibility\data\dl_pipeline'
for root, dirs, files in os.walk(base):
    for f in files:
        if 'vlm_walk' in f.lower():
            path = os.path.join(root, f)
            print(f'Found: {path}')
            try:
                with open(path, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                for item in data:
                    raw = item.get('raw_response', '')
                    print(f'  sample_id: {item.get("sample_id")}')
                    print(f'  raw_response ({len(raw)} chars):')
                    print(raw[:1000])
                    print(f'  SCR={item.get("scr")} urban_form={item.get("urban_form")}')
                    print()
            except Exception as e:
                print(f'  Error: {e}')
