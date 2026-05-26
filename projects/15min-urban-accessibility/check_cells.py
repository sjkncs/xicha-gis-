import json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('15min_urban_accessibility_SCI.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Check Cell 0
cell0 = nb['cells'][0]
print("Cell 0 type: %s" % cell0['cell_type'])
source0 = ''.join(cell0['source'])
print("Cell 0 source (%d chars):" % len(source0))
print(source0)

print("\n" + "="*80)

# Check Cell 1
cell1 = nb['cells'][1]
print("\nCell 1 type: %s" % cell1['cell_type'])
source1 = ''.join(cell1['source'])
print("Cell 1 source (%d chars):" % len(source1))
print(source1[:500] + "...")

# Check Cell 2 (should be Section 1)
cell2 = nb['cells'][2]
print("\nCell 2 type: %s" % cell2['cell_type'])
source2 = ''.join(cell2['source'])
print("Cell 2 source (%d chars):" % len(source2))
print(source2[:500])
