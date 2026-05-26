NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Line 3348 repr:")
line = lines[3347]
print(repr(line))
print("\nChar-by-char from col 0 to 50:")
for i, c in enumerate(line[:50]):
    print("  col %2d: %r" % (i, c))

# Now try to build the CORRECT replacement
# I want this JSON source string:
#     "    \"def load_api_config():\n",
#     "\n",
#     "    config = {}\n",
# Let's build it char by char
entry1 = '    "    \\"def load_api_config():\\n\\",\\n'
entry2 = '    "\\n\\",\\n'
entry3 = '    "    config = \\{\\}\\\\n\\",'
correct = entry1 + entry2 + entry3

print("\n=== Proposed correct replacement ===")
print(repr(correct))
print("\nDecoded (how it looks after JSON parse):")
import json as j
decoded = j.loads('[' + correct + ']')
print("String value:", repr(decoded[0]))

# Also print the char analysis
print("\nChar-by-char of correct replacement:")
for i, c in enumerate(correct[:60]):
    print("  col %2d: %r" % (i, c))

# Now check: does the file have the right number of backslashes?
print("\n=== Comparing file line vs correct ===")
file_line = lines[3347]
print("File line:")
for i, c in enumerate(file_line[:60]):
    if c in ['\\', '"', ',']:
        print("  col %2d: %r" % (i, c))

print("\nCorrect line:")
for i, c in enumerate(correct[:60]):
    if c in ['\\', '"', ',']:
        print("  col %2d: %r" % (i, c))

# Specifically check the char at col 4 (should be ")
print("\n=== Key positions ===")
print("File col 4:", repr(file_line[4]) if len(file_line) > 4 else "TOO SHORT")
print("Correct col 4:", repr(correct[4]) if len(correct) > 4 else "TOO SHORT")
print("File col 5:", repr(file_line[5]) if len(file_line) > 5 else "TOO SHORT")
print("Correct col 5:", repr(correct[5]) if len(correct) > 5 else "TOO SHORT")
print("File col 8:", repr(file_line[8]) if len(file_line) > 8 else "TOO SHORT")
print("Correct col 8:", repr(correct[8]) if len(correct) > 8 else "TOO SHORT")
