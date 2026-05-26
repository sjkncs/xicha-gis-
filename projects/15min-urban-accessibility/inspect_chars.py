NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
line = lines[3347]  # 0-indexed

print("Line 3348:")
print(repr(line))
print("\nChar-by-char:")

for i, c in enumerate(line):
    if c == '\\':
        print("  idx %d: BACKSLASH \\  (next: %r)" % (i, line[i+1] if i+1 < len(line) else 'END'))
    elif c == '"':
        print("  idx %d: QUOTE   " % i)
    elif c == ',':
        print("  idx %d: COMMA   " % i)
    elif c == '\n':
        print("  idx %d: NEWLINE \\n" % i)
    elif c == ' ':
        print("  idx %d: SPACE" % i)
    else:
        print("  idx %d: %r" % (i, c))

print("\n--- Correct structure for 3 entries ---")
print("""
Entry 1: "    \\"def load_api_config():\\n\\"
  In JSON file: '    "    \\"def load_api_config():\\n\\",\\n'
Entry 2: "\\n"
  In JSON file: '    "\\n\\",\\n'
Entry 3: "    config = \\{\\}\\n"
  In JSON file: '    "    config = \\{\\}\\\\n\\",\\n'
""")

# Build the correct replacement
correct = '    "    \\"def load_api_config():\\n\\",\\n    "\\n\\",\\n    "    config = \\{\\}\\\\n\\",\\n'
print("Correct replacement:")
print(repr(correct))

if line.strip() == correct.strip():
    print("\nMatches!")
else:
    print("\nDifference:")
    print("  Line: ", repr(line))
    print("  Corr: ", repr(correct))
    print("  Line len:", len(line))
    print("  Corr len:", len(correct))
