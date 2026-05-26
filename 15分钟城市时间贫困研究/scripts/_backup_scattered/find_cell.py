# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

# Find cells with load_village_data
for i, cell in enumerate(nb['cells']):
    src = ''.join(cell.get('source', []))
    if 'community_type' in src and 'population' in src and 'np.random.randint' in src:
        print(f"Cell {i}: cell_type={cell['cell_type']}")
        lines = cell['source']
        for j, line in enumerate(lines):
            if 'population' in line and 'np.random.randint' in line:
                print(f"  Line {j}: {repr(line)}")
                if j > 0:
                    print(f"  Prev:   {repr(lines[j-1])}")
                if j + 1 < len(lines):
                    print(f"  Next:   {repr(lines[j+1])}")
