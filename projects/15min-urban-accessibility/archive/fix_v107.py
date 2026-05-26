NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

# The issue: line 3312 ends with: ...')\n",\r and line 3313 starts with:     "print('='*60)
# They should be on separate lines

# Find where in the text this merge happens
# The Chinese text "建筑AOI分析完成" appears in line 3312
search = "建筑AOI分析完成"
pos = text.find(search)
if pos >= 0:
    print("Found '建筑AOI分析完成' at text position %d" % pos)
    print("Context: %s" % repr(text[pos:pos+80]))
    
    # Check what's after it
    after = text[pos+len(search):pos+len(search)+50]
    print("After: %s" % repr(after))
    
    # The issue is: the Chinese text ends, then there's \n",\r\n    "print
    # But the \r\n got merged into the text

# Find the pattern: '建筑AOI分析完成' followed by 'print('='*60)
pattern = "建筑AOI分析完成')\n"
pos2 = text.find(pattern)
if pos2 >= 0:
    print("\nFound pattern at text position %d" % pos2)
    print("After: %s" % repr(text[pos2:pos2+100]))
    
    # The fix: insert \r\n after the closing ) before \n
    # Current: ...建筑AOI分析完成')\n
    # Should be: ...建筑AOI分析完成')\n",\r\n
    # Actually, let me check the exact bytes
    
# Let me just find where the issue is in bytes
# The error is at pos 149465 in the JSON string
# That corresponds to the \r character (before the merge)
lf_positions = [i for i, c in enumerate(text) if c == '\n']
print("\nLF positions:")
print("LF[3310] (end of line 3311): %d" % lf_positions[3310])
print("LF[3311] (end of line 3312): %d" % lf_positions[3311])
print("LF[3312] (end of line 3313): %d" % lf_positions[3312])

# Line 3312 starts after LF[3310] and ends at LF[3311]
line_3312_start = lf_positions[3310] + 1
line_3312_end = lf_positions[3311]
line_3312_text = text[line_3312_start:line_3312_end]

print("\nLine 3312 (text positions %d-%d):" % (line_3312_start, line_3312_end))
print("  %s" % repr(line_3312_text))

# Line 3313 starts after LF[3311] and ends at LF[3312]
line_3313_start = lf_positions[3311] + 1
line_3313_end = lf_positions[3312]
line_3313_text = text[line_3313_start:line_3313_end]

print("\nLine 3313 (text positions %d-%d):" % (line_3313_start, line_3313_end))
print("  %s" % repr(line_3313_text))

# The fix: line 3312 should end with \r and line 3313 should start with:
#      "print('='*60)\n"\\r",
# The current merged content means line 3312 ends at:
# ...建筑AOI分析完成')\n",\r and the rest is missing

# Actually, looking at the raw bytes from before:
# Line 3312 raw bytes: 20 20 20 20 22 70 72 69 6E 74 28 27 46 69 67 31 31 20 ...27 29 5C 6E 22 2C 0D
# The last bytes are: 27 29 5C 6E 22 2C 0D
# = ' ) \ n " , CR
# So it ends with ')",\,n",CR
# But it SHOULD end with ')",\,n",\,r,CR,LF

# The fix: insert \n",\ before the CR, then start a new line

# Current line 3312: ... 27 29 5C 6E 22 2C 0D
# Target line 3312: ... 27 29 5C 6E 22 2C 5C 72 22 2C 0D 0A
# AND we need a new line 3313

# Let me just fix the bytes directly
line_3312_start_byte = lf_positions[3310] + 1
line_3312_end_byte = lf_positions[3311]
line_3312_bytes = raw[line_3312_start_byte:line_3312_end_byte]

print("\nLine 3312 bytes (%d-%d):" % (line_3312_start_byte, line_3312_end_byte))
print("  %s" % ' '.join('%02X' % b for b in line_3312_bytes))

# The fix: insert \r", after the existing CR (0x0D) and before the LF
# Current end: ... 27 29 5C 6E 22 2C 0D
# Should end:  ... 27 29 5C 6E 22 2C 5C 72 22 2C 0D 0A

# Find where to insert
# The CR is at position line_3312_end_byte - 1
cr_pos = line_3312_end_byte - 1
print("\nCR at byte position %d" % cr_pos)
print("Current byte: 0x%02X" % raw[cr_pos])

# Insert after CR: 5C 72 22 2C 0A
insert_bytes = bytes([0x5C, 0x72, 0x22, 0x2C, 0x0A])
print("Inserting: %s" % ' '.join('%02X' % b for b in insert_bytes))

raw[cr_pos+1:cr_pos+1] = insert_bytes

with open(NOTEBOOK_PATH, 'wb') as f:
    f.write(raw)
print("Saved.")

try:
    nb = json.loads(raw)
    print("\nSUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
