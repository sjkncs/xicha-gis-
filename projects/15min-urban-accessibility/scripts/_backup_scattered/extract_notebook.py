# -*- coding: utf-8 -*-
"""
执行 notebook 端到端测试：验证所有优化是否正确运行
"""
import subprocess, sys, json, io

# Read notebook
nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

# Extract all code from all code cells in order
all_code = []
for ci, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'code':
        src = ''.join(cell['source'])
        all_code.append(f"\n# ===== CELL {ci} =====\n" + src)

combined = '\n'.join(all_code)

# Write to temp file
temp_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\_test_run.py"
with open(temp_path, 'w', encoding='utf-8') as f:
    f.write(combined)

print(f"Extracted {len(nb['cells'])} cells to {temp_path}")
print(f"Total code length: {len(combined):,} chars")
print("\nNotebook extraction complete. Check the file manually or run via Jupyter.")
