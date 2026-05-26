NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')
lines = text.split('\n')

# Get line 3313 (index 3312)
if len(lines) >= 3313:
    line3313 = lines[3312]
    print("Line 3313 repr: %s" % repr(line3313))
    print("Line 3313 bytes: %s" % ' '.join('%02X' % ord(c) for c in line3313))
    
    # Check if it ends with proper quote and comma
    if line3313.endswith('"'):
        print("Ends with quote - OK")
    elif line3313.endswith('"\\r'):
        print("Ends with quote-backslash-r - OK (proper JSON)")
    else:
        print("Missing proper ending!")
    
    # Check content
    if 'print(\'=\'*60)' in line3313:
        print("Contains print('='*60)")
        # Is it wrapped in quotes?
        stripped = line3313.strip()
        if stripped.startswith('"') and stripped.count('"') >= 2:
            print("Has opening and closing quotes - OK")
        else:
            print("MISSING quotes around print statement!")
            
    # Show lines around
    print("\nLines 3310-3317:")
    for i in range(3309, 3317):
        if i < len(lines):
            print("  Line %d: %s" % (i+1, repr(lines[i][:80])))
