"""Deep analysis of remaining garbled cells"""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'

with open(filepath, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Analyze cells with remaining garbled chars
for i in [0, 12, 13, 16, 21, 26, 34]:
    cell = nb['cells'][i]
    src = ''.join(cell.get('source', ['']))
    garbled = [c for c in src if 0x80 <= ord(c) <= 0xFF]
    cjk = [c for c in src if 0x4e00 <= ord(c) <= 0x9fff]
    print(f"\n=== Cell {i} (garbled={len(garbled)}, cjk={len(cjk)}) ===")
    print(f"First 100 chars: {repr(src[:100])}")
    print(f"Sample garbled: {[f'{c}={hex(ord(c))}' for c in garbled[:10]]}")
    
    # Try fixing this specific cell
    try:
        fixed = src.encode('latin-1').decode('utf-8')
        fixed_cjk = sum(1 for c in fixed if 0x4e00 <= ord(c) <= 0x9fff)
        fixed_garbled = sum(1 for c in fixed if 0x80 <= ord(c) <= 0xFF)
        print(f"After latin-1 decode: cjk={fixed_cjk}, garbled={fixed_garbled}")
        if fixed_garbled < len(garbled):
            print(f"IMPROVED! Fixed: {repr(fixed[:100])}")
    except Exception as e:
        print(f"Latin-1 fix failed: {e}")
    
    # Check if garbled chars are in specific ranges
    if garbled:
        ranges = {
            'C0-DF (UTF8 2b first)': sum(1 for c in garbled if 0xC0 <= ord(c) <= 0xDF),
            'E0-EF (UTF8 3b first)': sum(1 for c in garbled if 0xE0 <= ord(c) <= 0xEF),
            'F0-F7 (UTF8 4b first)': sum(1 for c in garbled if 0xF0 <= ord(c) <= 0xF7),
            '80-BF (UTF8 continuation)': sum(1 for c in garbled if 0x80 <= ord(c) <= 0xBF),
            'C3 (UTF8 2b first byte)': sum(1 for c in garbled if ord(c) == 0xC3),
            'Other (non-UTF8)': sum(1 for c in garbled if not (0x80 <= ord(c) <= 0xFF)),
        }
        print(f"Garbled char ranges: {ranges}")

# Also check the backup
print("\n\n=== BACKUP ANALYSIS ===")
backup = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb.backup_before_encoding_fix'
with open(backup, 'rb') as f:
    raw = f.read()

# Check raw bytes around cell 26 area
# Find position of cell 26 markers
text = raw.decode('utf-8', errors='replace')
lines = text.split('\n')

# Look for cell 26 content
for idx, line in enumerate(lines):
    if '"cell_type": "code"' in line:
        # count cells
        pass
