NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')
lines = text.split('\n')

print("Line 3313: %s" % repr(lines[3312]))
print("Line 3314: %s" % repr(lines[3313]))

try:
    nb = json.loads(raw)
    print("\nSUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("\nError: %s at line %d, col %d, pos %d" % (e.msg, e.lineno, e.colno, e.pos))
    
    # Show the actual line content at the error
    if e.lineno <= len(lines):
        print("\nError line: %s" % repr(lines[e.lineno-1]))
        # Show what's at col 22
        err_line = lines[e.lineno-1]
        print("\nChar at col %d: 0x%04X = '%s'" % (e.colno, ord(err_line[e.colno-1]), err_line[e.colno-1]))
        print("Context: %s" % repr(err_line[max(0,e.colno-15):e.colno+15]))
    
    # Maybe the error is actually about a different line number
    # Let me check by parsing byte by byte
    print("\n=== Checking if there's an unescaped character issue ===")
    
    # Count unescaped quotes in the problematic area
    print("\nSearching for unescaped quotes near line 3313...")
    for i in range(max(0, e.pos-100), min(len(text), e.pos+100)):
        if text[i] == '"' and (i == 0 or text[i-1] != '\\'):
            print("  Unescaped quote at pos %d: %s" % (i, repr(text[max(0,i-10):i+20])))
