NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Read the file as text and try to fix common issues
with open(NOTEBOOK_PATH, 'r', encoding='utf-8', errors='replace') as f:
    text = f.read()

# Fix common issues:
# 1. Double CRs: \r\r -> \r\n
text = text.replace('\r\r', '\r\n')

# 2. Remove trailing commas before ] or }
# Pattern: ,] -> ]
import re
text = re.sub(r',\s*\]', ']', text)
text = re.sub(r',\s*\}', '}', text)

# Save
with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
    f.write(text)
print("Saved fixes.")

# Test
try:
    nb = json.loads(text)
    print("SUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("Error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
    
    # Show problematic area
    lines = text.split('\n')
    if e.lineno <= len(lines):
        print("\nLine %d: %s" % (e.lineno, repr(lines[e.lineno-1])))
