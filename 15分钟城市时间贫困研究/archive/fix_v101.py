NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

# Check position 149465
print("Text position 149465:")
print("  Char: 0x%04X = '%s'" % (ord(text[149465]), text[149465]))
print("  Context: %s" % repr(text[max(0,149465-50):149465+50]))

# Check what LF position this corresponds to
print("\nCounting LFs up to position 149465...")
lf_count = text[:149465].count('\n')
print("LF count before pos 149465: %d" % lf_count)

# Now check what's at the error according to the LF counting
lf_positions = [i for i, c in enumerate(text) if c == '\n']
if lf_count < len(lf_positions):
    print("\nLF at index %d: byte %d" % (lf_count, lf_positions[lf_count]))
    print("Text at that position: %s" % repr(text[lf_positions[lf_count]:lf_positions[lf_count]+50]))

# The issue: maybe the JSON parser uses different LF counting
# Let me try to reproduce the exact parsing
print("\n=== Testing JSON parsing ===")
try:
    json.loads(text)
    print("SUCCESS!")
except json.JSONDecodeError as e:
    print("Error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
    
    # Find actual line in text
    lines = text.split('\n')
    if e.lineno <= len(lines):
        print("\nActual line %d in text: %s" % (e.lineno, repr(lines[e.lineno-1][:80])))
    
    # But JSON reports line 3313 - where is that?
    print("\n=== Finding where JSON line 3313 is ===")
    # JSON line N starts after the (N-1)th LF
    # Line 3313 starts after LF[3312]
    if len(lf_positions) > 3312:
        line_3313_start = lf_positions[3312] + 1
        line_3313_end = lf_positions[3313] if len(lf_positions) > 3313 else len(text)
        line_3313 = text[line_3313_start:line_3313_end]
        print("JSON line 3313 (bytes %d-%d): %s" % (line_3313_start, line_3313_end, repr(line_3313[:80])))
