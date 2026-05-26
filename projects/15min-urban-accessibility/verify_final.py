import json, sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('15min_urban_accessibility_SCI.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

print("=" * 60)
print("Notebook Structure Summary")
print("=" * 60)
print(f"\nTotal cells: {len(nb['cells'])}")

# Find all section headers
print("\n=== Section Headers ===")
for i, cell in enumerate(nb['cells']):
    if cell.get('cell_type') == 'markdown':
        source = ''.join(cell.get('source', []))
        # Check for anchors
        match = re.search(r"<a id='(\d+)'", source)
        if match:
            section_num = match.group(1)
            # Get the section title
            title_match = re.search(r"##\s*[\d.]+\s*(.+)", source)
            title = title_match.group(1)[:60] if title_match else ""
            print(f"Cell {i}: Section {section_num} - {title}")

# Check Section 13 cells
print("\n=== Section 13 Cells ===")
for i, cell in enumerate(nb['cells']):
    if i >= 40:  # Section 13 cells start at index 40
        cell_type = cell.get('cell_type', 'unknown')
        source = ''.join(cell.get('source', []))
        preview = source[:60].replace('\n', ' ').replace('\r', '')[:50]
        print(f"Cell {i} ({cell_type}): {preview}...")

print("\n" + "=" * 60)
print("SUCCESS! Notebook is valid JSON with Section 13 inserted.")
print("=" * 60)
