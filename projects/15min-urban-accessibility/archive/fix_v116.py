NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

# Check current state
try:
    nb = json.loads(raw)
    print("JSON OK")
except json.JSONDecodeError as e:
    print("Error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))

# Find the print('='*60) statement in current bytes
search = b"print('='*60)"
pos = raw.find(search)
print("print('='*60) at raw byte %d" % pos)

# Context around it
print("\nContext bytes %d-%d:" % (pos-20, pos+30))
chunk = raw[pos-20:pos+30]
print(' '.join('%02X' % b for b in chunk))

# The string is:
# "print('='*60)\n"\\r",
# Bytes: 22 ... 29 5C 6E 22 5C 72 22 2C 0D 0A
# = "print('='*60)\n" + \r" + ,\r\n

# So looking at pos-20 to pos+30:
# pos-20 should be around: 22 5C 6E = "\n
# pos+29 should be around: 2C 0D 0A = ,\r\n

# Check the current bytes around the \r" part
# Find where \r", is now
for i in range(pos-20, pos+40):
    if i+1 < len(raw) and raw[i] == 0x5C and raw[i+1] == 0x72:
        print("\nFound \\r at raw byte %d" % i)
        print("Context: %s" % ' '.join('%02X' % raw[i-5:i+10]))
        
        # Check if there's a quote after \r
        if i+2 < len(raw) and raw[i+2] == 0x22:
            print("Quote follows \\r correctly")
            # Check if comma follows quote
            if i+3 < len(raw) and raw[i+3] == 0x2C:
                print("Comma follows quote correctly")
                # Check if CR follows comma
                if i+4 < len(raw) and raw[i+4] == 0x0D:
                    print("CR follows comma correctly")
                else:
                    print("CR missing! byte at +4 is 0x%02X" % (raw[i+4] if i+4 < len(raw) else 0))
            else:
                print("Comma missing! byte at +3 is 0x%02X" % (raw[i+3] if i+3 < len(raw) else 0))
        else:
            print("Quote NOT after \\r! byte at +2 is 0x%02X" % (raw[i+2] if i+2 < len(raw) else 0))
