NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# The problem: line 3313 ends with \\n"",\
# Should be: \\n"\\r,\r

# Find the pattern: 5C 6E 22 22 2C (in bytes)
# = \n"",
# Should be: 5C 6E 22 5C 72 22 2C = \n"\r",

search = b'\\n"",'  # \n"",
pos = raw.find(search)
if pos >= 0:
    print("Found '\\n\"\"' at raw byte %d" % pos)
    print("Context: %s" % ' '.join('%02X' % b for b in raw[pos-10:pos+15]))
    
    # The fix: replace 22 22 (two quotes) with 5C 72 22 (backslash-r quote)
    # But wait, we need \r", not just \r
    # So we need to replace 22 22 2C with 5C 72 22 2C
    
    # Actually looking at the context: the line ends with \\n"",\r
    # That is: \n",\r (the \\n is the newline in the string, ", is the comma after the string, \r is the line ending)
    # But we have an extra "" before the comma
    
    # The correct bytes for the end should be:
    # 5C 6E 22 5C 72 22 2C 0D 0A
    # = \n"\r",\r\n
    
    # Current: 5C 6E 22 22 2C 0D 0A
    # = \n"",\r\n
    
    # Fix: replace 22 2C with 5C 72 22 2C
    # Wait, no. We need to replace:
    # 22 22 2C 0D 0A (the extra quote)
    # with:
    # 5C 72 22 2C 0D 0A (add \r before the ,)
    
    # Let me find the exact position of this pattern
    # Looking for: \n"",\r\n
    search2 = b'\\n""'
    pos2 = raw.find(search2)
    if pos2 >= 0:
        print("\nFound '\\n\"\" at raw byte %d" % pos2)
        print("Context: %s" % ' '.join('%02X' % b for b in raw[pos2:pos2+20]))
        
        # The pattern is at pos2
        # Current bytes starting at pos2: 5C 6E 22 22 2C
        # = \n"",
        # Should be: 5C 6E 22 5C 72 22 2C
        # = \n"\r",
        
        # Fix: replace 22 (second quote) with 5C 72 (backslash-r)
        # That means replace byte at pos2+3 (0x22) with 0x5C
        # and insert 0x72 before it
        
        # Simpler: replace the 5 bytes 5C 6E 22 22 2C with 5C 6E 22 5C 72 22 2C
        old = b'\\n"",'  # 5C 6E 22 22 2C
        new = b'\\n"\\r",'  # 5C 6E 22 5C 72 22 2C
        
        raw = raw.replace(old, new, 1)
        
        print("After fix: %s" % ' '.join('%02X' % b for b in raw[pos2:pos2+20]))
        
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
