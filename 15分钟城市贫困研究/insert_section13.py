NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

import json, re

# Read as text for line analysis
with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print(f"Total lines: {len(lines)}")

# Find Section 10 markdown cell (contains '<a id=\'10\'>')
sec10_idx = content.find("<a id='10'>")
print(f"Section 10 marker at char: {sec10_idx}")

# Find the line number
sec10_line = content[:sec10_idx].count('\n') + 1
print(f"Section 10 line: {sec10_line}")

# Find Section 9 markdown cell
sec9_idx = content.find("<a id='9'>")
sec9_line = content[:sec9_idx].count('\n') + 1
print(f"Section 9 line: {sec9_line}")

# Find the Section 13 code cell
# It should be between the last clean cell and Section 10 markdown
# The malformed Section 13 code cell ends before Section 10
# Let's find it by looking for the cell that contains the inserted Section 13 code
# Search for "# === Section 13:" in the content
sec13_insert = content.find("# === Section 13")
if sec13_insert >= 0:
    sec13_insert_line = content[:sec13_insert].count('\n') + 1
    print(f"Section 13 code insertion at line: {sec13_insert_line}")
    
    # Show lines around the insertion
    for i in range(max(0, sec13_insert_line-5), min(len(lines), sec13_insert_line+20)):
        print(f"  Line {i+1}: {repr(lines[i][:80])}")
