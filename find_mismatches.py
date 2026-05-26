import json, re

nb = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb, 'r', encoding='utf-8') as f:
    nb_data = json.load(f)

all_source = '\n'.join(''.join(c['source']) for c in nb_data['cells'] if c.get('cell_type') == 'code')

# Find all def lines with -> annotation that aren't method chains
def_lines = [(m.start(), m.group()) for m in re.finditer(r'def\s+\w+\s*\([^)]*\)\s*(?:->\s*([^:]+?))?:', all_source)]

for pos, match in def_lines:
    line_num = all_source[:pos].count('\n') + 1
    print(f"Line {line_num}: {match}")
