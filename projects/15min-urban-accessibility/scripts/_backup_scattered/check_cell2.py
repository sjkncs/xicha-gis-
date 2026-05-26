import json

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'

with open(filepath, 'r', encoding='utf-8') as f:
    nb = json.load(f)

cell2 = nb['cells'][2]
src = ''.join(cell2['source'])
print("Cell 2 content:")
print(repr(src))
