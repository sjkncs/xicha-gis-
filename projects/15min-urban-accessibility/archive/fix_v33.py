NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Try to find the exact position of JSON error
with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Count newlines to find line 3313
line_count = 0
line_start = 0
for i, byte in enumerate(raw):
    if byte == 0x0A:  # LF
        line_count += 1
        if line_count == 3313:
            line_start = i + 1
        if line_count == 3314:
            line_end = i
            break

print("Line 3313 (bytes %d-%d):" % (line_start, line_end))
line_3313 = raw[line_start:line_end]
print("Hex: %s" % ' '.join('%02X' % b for b in line_3313))
print("Decoded: %s" % repr(line_3313.decode('utf-8', errors='replace')))

# Count brackets in the file to find structure
open_brackets = raw.count(b'[')
close_brackets = raw.count(b']')
open_braces = raw.count(b'{')
close_braces = raw.count(b'}')

print("\nBracket counts:")
print("  [: %d" % open_brackets)
print("  ]: %d" % close_brackets)
print("  {: %d" % open_braces)
print("  }: %d" % close_braces)

# The file should have:
# - 1 outer { (nbformat)
# - cells array: 1 [ 
# - 40 cells: 40 { objects
# - Each cell has 1 [ (source array)
# - So: 1 + 40 = 41 [ total
# And the same number of ] closes

print("\nExpected [ count: 1 (cells) + 40 (source arrays) = 41")
print("Expected { count: 1 (nbformat) + 40 (cells) = 41")

# Check if there's an extra [ from Section 13
if open_brackets > 41:
    print("\nWARNING: Extra %d '[' found!" % (open_brackets - 41))
