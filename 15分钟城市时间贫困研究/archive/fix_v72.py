NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# The raw bytes of line 3313 (line 3313 starts after LF[3311]):
# 20 20 20 20 22 70 72 69 6E 74 28 27 3D 27 2A 36 30 29 5C 6E 22 5C 72 22 2C 0A
#
# In terms of what Python bytes represent:
# 20 = ' ', 22 = '"', 70='p', 72='r', 69='i', 6E='n', 74='t'
# 28='(', 27="'", 3D='=', 27="'", 2A='*', 36='6', 30='0', 29=')'
# 5C='\', 6E='n', 22='"', 5C='\', 72='r', 22='"', 2C=',', 0A=LF
#
# So the line is literally (as bytes):
# b'    "print(\'=\'*60)\\\n"\\r",\n'
# i.e., the text: 4 spaces, ", print, (, ', ', =, ', ', *, 6, 0, ), \, n, ", \, r, ", ,, LF

# The PROBLEM: the JSON string should end with:
# print(\'=\'*60)\\n"\\r",
# i.e., bytes: ...5C 6E 22 5C 72 22 2C (\\n"\\r",)
#
# But we have: ...5C 6E 22 5C 72 22 2C
# After \\r we need: " then ,
# We currently have: " then , which IS correct!
#
# Wait... let me re-read the error:
# Error: Expecting ',' delimiter at line 3313, col 22
# Col 22 (1-indexed) = byte index 21 = 0x5C = '\'
#
# So the error is at the backslash before 'n'
# The text is: print(\'=\'*60)\n"\\r",
#                  ^col 17 18 19 20 21 22 23 24
# Actually let me count chars in: '    "print(\'=\'*60)\\n"\\r",'
# Position 0-3: '    '
# Position 4: '"'
# Position 5-9: 'print'
# Position 10: '('
# Position 11: "'"
# Position 12: '='
# Position 13: "'"
# Position 14: ')'
# Position 15: '*'
# Position 16: '6'
# Position 17: '0'
# Position 18: ')'
# Position 19: '\\'
# Position 20: 'n'
# Position 21: '"'
# Position 22: '\\'
# Position 23: 'r'
# Position 24: '"'
# Position 25: ','
#
# Wait that doesn't match. Let me be more careful.
# The string: "print(\'=\'*60)\\n"\\r",
# In Python repr: '    "print(\'=\'*60)\\n"\\r",'
# Characters:
# 0:' ' 1:' ' 2:' ' 3:' '
# 4:'"'
# 5:'p' 6:'r' 7:'i' 8:'n' 9:'t'
# 10:'('
# 11:"'"
# 12:'='
# 13:"'"
# 14:'*'
# 15:'6'
# 16:'0'
# 17:')'
# 18:'\\'
# 19:'n'
# 20:'"'
# 21:'\\'
# 22:'r'
# 23:'"'
# 24:','
#
# But wait - I think I'm confusing JSON strings with Python strings.
# In JSON: "\n" is a newline. "\\\\n" is the literal string "\n" (backslash + n).
# In the raw bytes, 5C 6E means the JSON string literal "\n" (backslash + n)
# 
# The actual JSON string in the cell source is the Python string:
# "print('='*60)\n\"\\r\","
# i.e., the cell source contains the text: print('='*60)\n"\r",
# The \\n in the source means the text has a newline at that point
# The \\r" means the text has \"\\r\" (backslash, r, quote) at that point... no wait.
#
# Let me look at this from the JSON perspective:
# The JSON string value for this line is: "    \"print(\'=\'*60)\\n\"\\r\",\r\n"
# In the JSON file, this is literally 4 spaces, ", p, r, i, n, t, (, ', =, ', *, 6, 0, ), \, n, ", \, r, ", ,, CR, LF
# (24 chars + CR + LF = 26 chars + CR = 27?)

# The line as text: '    "print(\'=\'*60)\\n"\\r",'
# repr shows \\n and \\r because that's Python's way of showing the backslash+n and backslash+r
# The actual chars in Python string are:
# [' ', ' ', ' ', ' ', '"', 'p', 'r', 'i', 'n', 't', '(', "'", '=', "'", '*', '6', '0', ')', '\\', 'n', '"', '\\', 'r', '"', ',']

# Now, in the JSON structure, this is the CONTENT of a string in the "source" array.
# The JSON string should be: "    \"print(\'=\'*60)\\n\"\\r\",\r\n"
# Inside the string value, \\n means backslash-n (not newline)
# \" means quote
# So the string value is: 4 spaces + "print('='*60) + \n + " + \r + " + , + \r\n

# After the \\r (bytes 5C 72), we have:
# 22 = '"' = closing quote of the string
# 2C = ',' = separator (but string not closed yet!)
# 0A = LF = end of line

# AHA! The issue is that after \\r", we should have comma to END the array element
# but the string closing quote comes BEFORE the comma. And we DO have that.
# Wait... let me count the quotes.

line_text = raw[lf_positions[3311]+1:lf_positions[3312]+1].decode('utf-8', errors='replace')
print("Line text: %s" % repr(line_text))

# Count quotes in the line
quote_count = line_text.count('"')
print("Quote count: %d" % quote_count)

# The issue: in a JSON string value, quotes must be escaped as \"
# So in the JSON source, each " should appear as \"
# But we see RAW " characters... which would terminate the string early!

# Let me check the actual bytes vs the text representation
lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]
line_start = lf_positions[3311] + 1
line_end = lf_positions[3312] + 1  # +1 to include LF
line_bytes = raw[line_start:line_end]
print("\nLine bytes (%d-%d):" % (line_start, line_end))
print("  %s" % ' '.join('%02X' % b for b in line_bytes))
print("  %s" % repr(line_bytes))

# Count quote bytes (0x22) in the line
quote_bytes = [i for i, b in enumerate(line_bytes) if b == 0x22]
print("\nQuote byte positions: %s" % str(quote_bytes))
print("Quote byte values: %s" % ' '.join('0x%02X' % line_bytes[i] for i in quote_bytes))
print("Quote char values: %s" % ' '.join('%d:%s' % (i, repr(chr(line_bytes[i]))) for i in quote_bytes))

# JSON strings contain \" for literal quotes
# So 0x22 (") should only appear as \" in JSON strings
# If we see unescaped 0x22 in the JSON source, it terminates the string!
print("\nChecking for unescaped quotes...")
for i, b in enumerate(line_bytes):
    if b == 0x22:  # Quote
        if i > 0 and line_bytes[i-1] != 0x5C:  # Not preceded by backslash
            print("  Unescaped quote at byte offset %d (abs %d): %s" % (i, line_start+i, repr(line_bytes[max(0,i-10):i+10])))
        elif i > 1 and line_bytes[i-2] == 0x5C and line_bytes[i-1] == 0x5C:  # Escaped backslash followed by quote
            print("  Escaped-backslash-quote at byte offset %d: %s" % (i, repr(line_bytes[max(0,i-10):i+10])))
