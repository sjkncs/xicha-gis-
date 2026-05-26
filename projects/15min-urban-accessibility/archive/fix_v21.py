NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# The raw repr of lines 3315-3325
lines = content.split('\n')
print("Lines 3315-3330:")
for i in range(3314, min(3330, len(lines))):
    print("%d: %s" % (i+1, repr(lines[i])))

# Let me also check if the "cells" array is properly opened
# Search backwards from line 3315 to find "cells"
print("\n\nSearching for 'cells' array open...")
content_lines = content.split('\n')
for i in range(3314, -1, -1):
    line = content_lines[i]
    if 'cells' in line and 'source' not in line:
        print("Line %d: %s" % (i+1, repr(line)))
        break

# Check if there's a cells close without proper open
# Count [ and ] in the file
print("\n\nBrackets analysis (near end of file):")
print("'cells': [' found: %d" % content.count("'cells': ["))
print('"cells": [ found: %d' % content.count('"cells": ['))
print('], found: %d' % content.count('],'))

# Check the "cells" line
cells_idx = content.find('"cells": [')
print("\n'\"cells\": [' at index: %d" % cells_idx)
print("Context: %s" % repr(content[cells_idx:cells_idx+50]))
