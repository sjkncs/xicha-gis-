NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# The issue: line 3313 has literal backslash + 'n' characters instead of \n escape
# Current (wrong):    "print('='*60)\n"\r",
# Should be:           "print('='*60)\n",\r",
# 
# Bytes at line 3313 around col 19-26:
# col 19: 5C (backslash)
# col 20: 6E ('n')
# col 21: 22 (quote)
# col 22: 5C (backslash)
# col 23: 72 ('r')
# col 24: 22 (quote)
# col 25: 2C (comma)
# col 26: 0D (CR)

# The fix: replace the literal backslash + 'n' (5C 6E) with \n escape (5C 6E) is ALREADY CORRECT!
# Wait, 5C 6E IS \n in JSON! Let me re-check...

# Actually looking at the repr:
# Line 3313: '    "print(\'=\'*60)\\n"\\r",\r'
# 
# In repr:
# \\ = single backslash
# \\n = backslash + letter n (literal)
# 
# So the text has literal backslash + n, which is WRONG.
# The fix: replace backslash + 'n' (5C 6E) with newline (0x0A)

# Find the print statement and check its context
search = b"print('='*60)"
pos = raw.find(search)
print("print('='*60) at raw byte %d" % pos)

# Check bytes around it
# Looking for pattern: ...29 5C 6E 22 ... 
# = ) \ n "
for i in range(pos-10, pos+20):
    if i+1 < len(raw) and raw[i] == 0x5C and raw[i+1] == 0x6E:
        print("Found backslash-n at raw byte %d" % i)
        print("Context: %s" % ' '.join('%02X' % b for b in raw[i-5:i+15]))
        
        # Check: is this 5C 6E followed by 0x22 (quote)?
        if i+2 < len(raw) and raw[i+2] == 0x22:
            print("Backslash-n is followed by quote - this is correct JSON!")
        else:
            print("Backslash-n NOT followed by quote - this is wrong!")
            print("Next bytes: %s" % ' '.join('%02X' % b for b in raw[i:i+10]))

# Let me check if the issue is elsewhere - maybe the \r is not properly escaped
# The repr shows \\r which means literal backslash + 'r'
# Let me search for the pattern 5C 72 (backslash + 'r')
search2 = b"\\r"
positions = []
start = 0
while True:
    pos2 = raw.find(search2, start)
    if pos2 < 0:
        break
    positions.append(pos2)
    start = pos2 + 1

print("\nFound %d occurrences of backslash-r" % len(positions))
for p in positions:
    if 166400 < p < 166500:
        print("At %d: %s" % (p, ' '.join('%02X' % b for b in raw[p-5:p+10])))
