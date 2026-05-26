NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Line 3313 (1-indexed)
idx = 3312  # 0-indexed
if len(lines) > idx:
    line = lines[idx]
    print("Line 3313 (%d chars):" % len(line))
    print(repr(line))
    
    # Show character positions
    print("\nCharacter analysis:")
    for i, c in enumerate(line):
        if i < 100:
            print("  [%3d] 0x%04X = %s" % (i, ord(c), repr(c)))
