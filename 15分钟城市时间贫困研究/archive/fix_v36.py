NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Read raw bytes
with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d bytes" % len(raw))
print("LF count: %d" % raw.count(b'\x0A'))
print("CR count: %d" % raw.count(b'\x0D'))

# Try to parse and get error
try:
    nb = json.loads(raw)
    print("JSON is valid!")
except json.JSONDecodeError as e:
    print("Error: %s" % e.msg)
    print("At pos: %d" % e.pos)
    
    # The error line in json.loads is based on the decoded text, not raw bytes
    # But our file has literal \n in strings which affects line counting
    
    # Let me decode and count
    try:
        text = raw.decode('utf-8')
    except:
        text = raw.decode('utf-8', errors='replace')
    
    # Find the line number of the error
    lines_before = text[:e.pos].count('\n')
    print("Error is at text line: %d" % (lines_before + 1))
    
    # Show context
    lines = text.split('\n')
    print("\nLines around error:")
    for i in range(max(0, lines_before-2), min(len(lines), lines_before+3)):
        marker = ">>> " if i == lines_before else "    "
        print("%s%d: %s" % (marker, i+1, repr(lines[i])))
    
    # Also try to find the actual raw position
    raw_pos = 0
    text_idx = 0
    lf_count = 0
    while raw_pos < len(raw) and lf_count < lines_before:
        if raw[raw_pos] == 0x0A:
            lf_count += 1
        raw_pos += 1
    
    print("\nRaw position of error line start: %d" % raw_pos)
    print("Raw byte at error position: %s" % repr(raw[e.pos:e.pos+20]))
