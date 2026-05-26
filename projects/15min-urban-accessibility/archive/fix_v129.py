NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

# Find the print('='*60) statement
# Line 3313: '    "print(\'=\'*60)\\n",\r'
# The comma at the end is the problem!

# The structure should be:
# Line 3312: "print('Fig11 建筑AOI分析完成')\n",  (ends with ,)
# Line 3313: "print('='*60)\n"                  (should NOT end with ,)
# Line 3314: ],                                 (closes array)

# So we need to remove the comma from line 3313

# Find the pattern in text: \n",\r followed by CRLF
# Line 3313 should end with \n"\r instead of \n",\r

search = b"print('='*60)"
pos = raw.find(search)
if pos >= 0:
    print("Found at raw byte %d" % pos)
    
    # The string ends at: ...)\n",\r
    # We need to remove the comma: ...)\n"\r
    
    # Find the closing quote and comma
    # Looking for: )\n",\r
    # = 29 5C 6E 22 2C 0D
    # Should be: 29 5C 6E 22 0D
    
    # Find 29 5C 6E 22 2C in bytes after pos
    for i in range(pos, pos + 30):
        if (i + 5 < len(raw) and 
            raw[i] == 0x29 and 
            raw[i+1] == 0x5C and 
            raw[i+2] == 0x6E and 
            raw[i+3] == 0x22 and 
            raw[i+4] == 0x2C):
            print("Found )\\n\", at byte %d" % i)
            print("Context: %s" % ' '.join('%02X' % b for b in raw[i-3:i+10]))
            
            # Remove the comma: 29 5C 6E 22 2C -> 29 5C 6E 22
            raw = raw[:i+4] + raw[i+5:]
            print("Fixed!")
            break
    
    # Save
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(raw)
    print("Saved.")
    
    # Test
    try:
        nb = json.loads(raw)
        print("\nSUCCESS! %d cells" % len(nb['cells']))
    except json.JSONDecodeError as e:
        print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
else:
    print("Pattern not found")
