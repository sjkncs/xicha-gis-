NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Validate JSON by trying to parse
try:
    nb = json.loads(content)
    print("JSON OK! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("Error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
    
    # Find what the parser is looking at
    lines = content.split('\n')
    print("\nError line (%d): %s" % (e.lineno, repr(lines[e.lineno-1])))
    print("Previous line (%d): %s" % (e.lineno-1, repr(lines[e.lineno-2])))
    
    # What character is at col 23?
    err_line = lines[e.lineno-1]
    if e.colno <= len(err_line):
        print("\nChar at col %d: 0x%04X = '%s'" % (e.colno, ord(err_line[e.colno-1]), err_line[e.colno-1]))
        print("Context: %s" % repr(err_line[max(0,e.colno-10):e.colno+10]))
    
    # Now let's try to reconstruct what the parser THINKS is happening
    # by counting brackets in the lines BEFORE the error
    print("\n=== Bracket depth BEFORE error line ===")
    depth = 0
    for i in range(max(0, e.lineno-20), e.lineno):
        line = lines[i]
        for ch in line:
            if ch in '{["':
                depth += 1
            elif ch in '}"]':
                depth -= 1
        if i >= e.lineno - 5:
            print("  Line %d (depth=%d): %s" % (i+1, depth, repr(line[:60])))
    
    print("\n=== Summary ===")
    print("At error line %d, col %d:" % (e.lineno, e.colno))
    print("  Current depth of arrays: checking...")
