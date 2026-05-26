NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Error at pos 149465
pos = 149465
print("Bytes around pos 149465:")
print("  Before: %s" % repr(raw[pos-50:pos]))
print("  AT:     %s" % repr(raw[pos:pos+50]))
print("  After:  %s" % repr(raw[pos+50:pos+100]))

# Also check using LF count method
lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]
print("\nLF positions around line 3313:")
print("  LF[3311] (start of line 3313): %d" % lf_positions[3311])
print("  LF[3312] (start of line 3314): %s" % (lf_positions[3312] if len(lf_positions) > 3312 else "N/A"))
print("  Raw line 3313 bytes: %s" % repr(raw[lf_positions[3311]+1:lf_positions[3312]+1 if len(lf_positions) > 3312 else len(raw)]))
print("  Raw line 3313 hex: %s" % ' '.join('%02X' % b for b in raw[lf_positions[3311]+1:lf_positions[3312]+1 if len(lf_positions) > 3312 else len(raw)]))

# Count total lines
print("\nTotal LFs: %d" % len(lf_positions))
print("Total chars (text): %d" % len(raw.decode('utf-8', errors='replace')))

# Try json.loads with position info
try:
    json.loads(raw)
    print("\nJSON parses OK!")
except json.JSONDecodeError as e:
    print("\nError: %s" % e.msg)
    print("  Line: %d, Col: %d, Pos: %d" % (e.lineno, e.colno, e.pos))
    
    # Show what's actually at the error position in the JSON string
    # json.loads reads the file as text, so pos is in the text
    json_text = raw.decode('utf-8', errors='replace')
    
    # Lines in json.loads are based on '\n' in the text
    json_lines = json_text.split('\n')
    print("  JSON text line %d: %s" % (e.lineno, repr(json_lines[e.lineno-1])))
    print("  JSON text line %d chars: %s" % (e.lineno, 
        [(i, repr(c)) for i, c in enumerate(json_lines[e.lineno-1]) if 15 <= i <= 30]))
    
    # The error col is 22
    if e.lineno <= len(json_lines) and e.colno <= len(json_lines[e.lineno-1]):
        print("  Char at col 22: %s (0x%04X)" % (repr(json_lines[e.lineno-1][e.colno-1]), ord(json_lines[e.lineno-1][e.colno-1])))
