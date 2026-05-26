NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

# Search for Section 13 content
print("Searching for 'id='13' in lines...")
for i, line in enumerate(lines):
    if "id='13'" in line or "Section 13" in line or "街景感知" in line:
        print("Line %d: %s" % (i+1, line[:80]))

# Search for where the Section 13 content got into the source array
# It should be in the Fig11 cell's source
# Let's find the "source": [ pattern
print("\n\nSearching for '\"source\": [' pattern...")
source_starts = []
for i, line in enumerate(lines):
    if '"source": [' in line or "'source': [" in line:
        source_starts.append(i)
        print("Line %d: %s" % (i+1, line[:60]))

print("\n\nFound %d source array openings" % len(source_starts))
if source_starts:
    print("Last source opens at line %d" % (source_starts[-1] + 1))
    
# Count how many lines are in each source array
# by finding matching ] close
