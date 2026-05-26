import json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('15min_urban_accessibility_SCI.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Check Cell 40 (last cell)
cell40 = nb['cells'][40]
print("Cell 40 type: %s" % cell40['cell_type'])
source40 = ''.join(cell40['source'])
print("Cell 40 source (%d chars):" % len(source40))
# Show last 500 chars
print(source40[-500:])

# Count total cells
print("\nTotal cells before cleanup: %d" % len(nb['cells']))

# Remove Cell 0 (misplaced Section 13 header)
print("\nRemoving Cell 0 (misplaced Section 13 header)...")
nb['cells'].pop(0)

# Verify
print("Cells after removal: %d" % len(nb['cells']))

# Now Cell 40 is now Cell 39 (0-indexed)
# Check the new Cell 39
cell39 = nb['cells'][39]
print("\nNew Cell 39 type: %s" % cell39['cell_type'])

# Save the notebook
with open('15min_urban_accessibility_SCI.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("\nSaved notebook.")

# Verify JSON
try:
    with open('15min_urban_accessibility_SCI.ipynb', 'r', encoding='utf-8') as f:
        nb2 = json.load(f)
    print("SUCCESS! %d cells" % len(nb2['cells']))
except json.JSONDecodeError as e:
    print("Error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
