import json
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'

with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
    nb = json.load(f)

# Check current types
print("Before fix:")
for idx in [12, 13]:
    cell = nb['cells'][idx]
    src_preview = ''.join(cell.get('source', ['']))[:100]
    print(f"  Cell {idx}: type={cell['cell_type']}, preview={src_preview}")

# Fix cell 12 - it should be code but is markdown
cell12 = nb['cells'][12]
if cell12['cell_type'] == 'markdown':
    # Check if it looks like code
    src = ''.join(cell12.get('source', ['']))
    if 'class VulnerablePopulationProfiler' in src or '# VulnerablePopulationProfiler' in src:
        cell12['cell_type'] = 'code'
        if 'execution_count' in cell12:
            cell12['execution_count'] = None
        if 'metadata' not in cell12:
            cell12['metadata'] = {}
        print(f"  Cell 12: fixed markdown -> code")

# Fix cell 13 - it should be code but is markdown
cell13 = nb['cells'][13]
if cell13['cell_type'] == 'markdown':
    src = ''.join(cell13.get('source', ['']))
    if 'fig,' in src and ('plt.savefig' in src or 'matplotlib' in src):
        cell13['cell_type'] = 'code'
        if 'execution_count' in cell13:
            cell13['execution_count'] = None
        if 'metadata' not in cell13:
            cell13['metadata'] = {}
        print(f"  Cell 13: fixed markdown -> code")

# Save
with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("\nAfter fix:")
with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
    nb2 = json.load(f)
for idx in [12, 13]:
    cell = nb2['cells'][idx]
    print(f"  Cell {idx}: type={cell['cell_type']}")

print("\nSaved successfully!")
