"""
Notebook Encoding Diagnostic Script - outputs to file
Diagnoses the double-encoding issue in the notebook
"""
import json
import os
import sys

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'
outpath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\diagnostic_report.txt'

with open(filepath, 'rb') as f:
    raw = f.read()

results = []
results.append(f"File size: {len(raw):,} bytes")

text_utf8 = raw.decode('utf-8', errors='replace')
nb = json.loads(text_utf8)
results.append(f"JSON valid, {len(nb['cells'])} cells")

cell0 = nb['cells'][0]
src0 = ''.join(cell0['source'])
results.append(f"Cell 0 length: {len(src0)} chars")

garbled_chars = [c for c in src0[:500] if ord(c) > 127]
results.append(f"Garbled chars in first 500: {len(garbled_chars)}")

# Show hex of first garbled char
if garbled_chars:
    results.append(f"Sample garbled chars: {[f'{c}={hex(ord(c))}' for c in garbled_chars[:5]]}")

in_utf8_byte_range = sum(1 for c in garbled_chars if 0x80 <= ord(c) <= 0xFF)
results.append(f"Chars in UTF-8 byte range (0x80-0xFF): {in_utf8_byte_range}")

# Try double-decode fix
test = src0[:100]
latin1_bytes = test.encode('latin-1')
results.append(f"Has 0xc3 bytes: {'yes' if b'\xc3' in latin1_bytes else 'no'}")

try:
    fixed = test.encode('latin-1').decode('utf-8')
    has_cjk = any(0x4e00 <= ord(c) <= 0x9fff for c in fixed)
    results.append(f"Double-decode fix works: {'yes' if has_cjk else 'no'}")
    if has_cjk:
        # Count CJK in fixed
        cjk_count = sum(1 for c in fixed if 0x4e00 <= ord(c) <= 0x9fff)
        results.append(f"CJK chars in fixed text: {cjk_count}")
        results.append(f"Sample fixed text: {fixed[:80]}")
except Exception as e:
    results.append(f"Double-decode fix failed: {e}")

# Scan all cells
results.append(f"\n=== All {len(nb['cells'])} cells ===")
for i, cell in enumerate(nb['cells']):
    src = ''.join(cell.get('source', ['']))
    garbled = sum(1 for c in src if 0x80 <= ord(c) <= 0xFF)
    cjk = sum(1 for c in src if 0x4e00 <= ord(c) <= 0x9fff)
    cell_type = cell.get('cell_type', '?')
    first_line = src.split('\n')[0][:40] if src else ''
    results.append(f"Cell {i:2d} | {cell_type:8s} | garbled:{garbled:5d} | cjk:{cjk:5d} | {first_line}")

# Write report
with open(outpath, 'w', encoding='utf-8') as f:
    f.write('\n'.join(results))

print("Diagnostic report written to:", outpath)
