NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

# Simulate how json.loads counts lines
# JSON uses LF as line separator
json_lines = text.split('\n')
print("Total JSON lines: %d" % len(json_lines))

# Check what's at line 3313 (1-indexed)
if len(json_lines) >= 3313:
    line_3313 = json_lines[3312]  # 0-indexed
    print("\nLine 3313 (%d chars):" % len(line_3313))
    print("  %s" % repr(line_3313[:100]))
    
    # Check col 22
    if len(line_3313) >= 22:
        print("\nCol 22 char: %s (0x%02X)" % (repr(line_3313[21]), ord(line_3313[21])))
        print("Context col 15-30: %s" % repr(line_3313[14:30]))
else:
    print("Only %d lines in file" % len(json_lines))

# Check what comes BEFORE line 3313
print("\n=== Lines 3310-3315 ===")
for i in range(3309, min(3315, len(json_lines))):
    line = json_lines[i]
    print("Line %d (%d chars): %s" % (i+1, len(line), repr(line[:100])))
