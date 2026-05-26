NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Read as text and show lines 3315-3330
with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("Total lines: %d" % len(lines))
print("\nLines 3315-3330:")
for i in range(3314, min(3330, len(lines))):
    print("%d: %s" % (i+1, repr(lines[i])))

# Count lines
print("\n=== Line count analysis ===")
print("Line 3322 char 1: '%s'" % repr(lines[3321][0] if lines[3321] else "EMPTY"))
print("Line 3321 last char: '%s'" % repr(lines[3320][-5:] if lines[3320] else "EMPTY"))
