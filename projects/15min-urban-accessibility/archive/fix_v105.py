NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Find the actual error by using json.decoder.JSONDecoder
class MyDecoder(json.JSONDecoder):
    def raw_decode(self, s, idx=0):
        return super().raw_decode(s, idx)

# Try to parse and catch the exact position
try:
    nb = json.loads(raw)
    print("SUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("Error: %s at line %d, col %d, pos %d" % (e.msg, e.lineno, e.colno, e.pos))
    
    # Check the line content
    text = raw.decode('utf-8', errors='replace')
    lines = text.split('\n')
    
    print("\nError line %d: %s" % (e.lineno, repr(lines[e.lineno-1][:80])))
    
    # The problem: line 3313 is part of a source array
    # Let's find the start of the source array containing it
    
    # Find the last "source": [ before line 3313
    lf_positions = [i for i, c in enumerate(text) if c == '\n']
    
    # Line 3313 is the 3313th LF in text
    # Find its byte position
    if e.lineno <= len(lf_positions):
        line_start_in_text = lf_positions[e.lineno - 2] + 1 if e.lineno >= 2 else 0
        line_end_in_text = lf_positions[e.lineno - 1]
        
        print("\nLine %d in text: chars %d to %d" % (e.lineno, line_start_in_text, line_end_in_text))
        
        # But json.loads might use different line counting!
        # Let's check by manually finding where line 3313 is
        
    # Actually, let me just search for any problematic pattern
    print("\n=== Checking for unescaped quotes ===")
    
    # Search for the pattern where a quote appears without a preceding backslash
    # in the context of the error
    
    # Look at bytes around the error
    print("\nBytes around error position (in text):")
    if e.pos < len(text):
        print("Text at pos %d: %s" % (e.pos, repr(text[e.pos:e.pos+50])))
        print("Text before pos %d: %s" % (e.pos, repr(text[e.pos-50:e.pos])))
    
    # Check if there's an unescaped quote right before the error
    if e.pos > 0:
        for i in range(e.pos - 200, e.pos):
            if text[i] == '"' and (i == 0 or text[i-1] != '\\'):
                print("Unescaped quote at text pos %d: %s" % (i, repr(text[max(0,i-20):i+30])))

# Let me try a different approach: check if there's a specific pattern causing the issue
print("\n=== Checking line 3312 for quote issues ===")

lf_positions = [i for i, c in enumerate(text) if c == '\n']
line_3312_start = lf_positions[3310] + 1  # LF[3310] ends line 3311
line_3312_end = lf_positions[3311]  # LF[3311] ends line 3312
line_3312 = raw[line_3312_start:line_3312_end]

print("Line 3312: bytes %d-%d (%d bytes)" % (line_3312_start, line_3312_end, len(line_3312)))
print("Hex: %s" % ' '.join('%02X' % b for b in line_3312))

# Check if there's a " anywhere that's not preceded by \
in_string = False
escaped = False
for i, b in enumerate(line_3312):
    c = chr(b)
    if not in_string:
        if c == '"':
            # Start of string
            in_string = True
            escaped = False
    else:
        if escaped:
            escaped = False
        elif c == '\\':
            escaped = True
        elif c == '"':
            # End of string
            in_string = False
        elif c in '\n\r':
            print("WARNING: Unclosed string at byte %d" % (line_3312_start + i))
            print("  Context: %s" % repr(line_3312[max(0,i-20):i+10]))
            break
