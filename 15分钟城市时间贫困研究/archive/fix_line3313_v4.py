NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Let me look at the exact byte position of the error
try:
    nb = json.loads(raw)
    print("SUCCESS!")
except json.JSONDecodeError as e:
    print("Error at line %d, col %d" % (e.lineno, e.colno))
    print("Pos: %d" % e.pos)
    
    # Find line 3313 in bytes
    text = raw[:e.pos].decode('utf-8', errors='replace')
    lines = text.split('\n')
    
    # Line 3312 would be the one before the error
    print("\nLast 5 lines:")
    for i in range(max(0, len(lines)-5), len(lines)):
        print("  Line %d: %s" % (i+1, repr(lines[i][:80])))
        
    # Check line 3313 specifically
    if len(lines) >= 3313:
        print("\nLine 3313: %s" % repr(lines[3312][:100]))
        
    # The actual line in the raw bytes
    # Line 3313 in JSON terms (not Python repr terms)
    # Let me check actual line numbers
    
    # Count LF characters up to error position
    lf_count = raw[:e.pos].count(b'\n')
    print("\nLF count up to error: %d" % lf_count)
    
    # Show bytes around error position
    chunk = raw[e.pos-50:e.pos+50]
    print("\nBytes around error (pos %d):" % e.pos)
    print("  %s" % ' '.join('%02X' % b for b in chunk))
    print("  %s" % repr(chunk))
