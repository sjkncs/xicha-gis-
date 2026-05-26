NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')
lines = text.split('\n')

# Find cell boundaries by counting nesting
# We need to find where the cell containing line 3313 starts

# Count indentation levels to find cell starts
in_cells = False
cell_depth = 0
last_cell_start = None
cells_array_line = None

for i, line in enumerate(lines):
    stripped = line.rstrip('\r\n')
    
    # Track cells array
    if '"cells": [' in stripped:
        in_cells = True
        cells_array_line = i + 1
        cell_depth = 1
    
    # Track cell dict starts
    if in_cells and stripped.startswith('{') and not stripped.startswith('"'):
        last_cell_start = i + 1
    
    # Track cell dict ends  
    if in_cells and stripped == '},':
        # This might be end of a cell
        pass

# More precise: find the source array that contains line 3313
# Line 3313 is inside a source array. Find the cell that owns it.

# Let me find all source array boundaries
print("=== Finding source arrays ===")
source_starts = []
source_ends = []
in_source = False
source_start_line = 0
depth = 0

for i, line in enumerate(lines):
    stripped = line.strip()
    
    # Track cells array
    if '"cells": [' in stripped:
        in_cells = True
        
    if in_cells:
        for ch in stripped:
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
        
        if '"source": [' in stripped:
            source_start_line = i + 1
            
        # End of source array: when we see ], and depth returns to cells level
        # Actually, each source array is: "source": [ ... ]
        # We need to track when a source array ends
        
        # The source array ends with "],\r" or just "],\r"
        # But we need to know when the [ for source closes
        
        # A simpler approach: find the last "source": [ before line 3313
        if '"source": [' in stripped:
            source_starts.append(i + 1)

# Find the last source array start before line 3313
last_source_start = None
for s in source_starts:
    if s < 3313:
        last_source_start = s

print("Last source array started at line: %s" % last_source_start)
print("Error at line: 3313")

# Now find the corresponding cell_type
print("\n=== Looking for cell structure ===")
# Find cells that start before and end after line 3313
print("\nLines 3065-3320 (looking for cell starts):")
for i in range(3064, 3320):
    stripped = lines[i].strip()
    if stripped.startswith('"cell_type"') or stripped.startswith('"source"'):
        print("  Line %d: %s" % (i+1, repr(stripped)))
    if stripped == '},':
        print("  Line %d: %s (possible cell end)" % (i+1, repr(stripped)))
    if stripped == '],':
        print("  Line %d: %s (possible array end)" % (i+1, repr(stripped)))
