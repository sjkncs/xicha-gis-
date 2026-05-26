"""Verify notebook encoding state after fix"""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'

with open(filepath, 'r', encoding='utf-8') as f:
    nb = json.load(f)

print(f'Total cells: {len(nb["cells"])}')
print()
for i, cell in enumerate(nb['cells']):
    src = ''.join(cell.get('source', ['']))
    garbled = sum(1 for c in src if 0x80 <= ord(c) <= 0xFF)
    cjk = sum(1 for c in src if 0x4e00 <= ord(c) <= 0x9fff)
    ct = cell.get('cell_type', '?')
    first = src.split('\n')[0][:40] if src else '(empty)'
    flag = '*** GARBLED ***' if garbled > 0 else ''
    print(f'Cell {i:2d} | {ct:8s} | garbled:{garbled:5d} | cjk:{cjk:5d} | {flag} {first}')
