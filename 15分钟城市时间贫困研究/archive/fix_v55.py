NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# The structure: after the print string, we have:
# ...5C 6E 22 5C 72 0A... 
# = \n " \r LF
# The closing quote (22) is missing before \r
# Fix: Insert quote between \r and LF

# Search for: \r followed by LF (0D 0A)
search = bytes([0x5C, 0x72, 0x0A])
pos = raw.find(search)
print("Pattern \\r<LF> at byte: %d" % pos)

if pos >= 0:
    print("Context: %s" % repr(raw[pos-20:pos+30]))
    
    # Check if there's a quote after \r
    if pos + 2 < len(raw):
        print("Byte at pos+2: 0x%02X" % raw[pos+2])
        
        # If no quote, insert one
        if raw[pos+2] != 0x22:  # not a quote
            print("Missing closing quote! Inserting...")
            new_raw = raw[:pos+2] + b'"' + raw[pos+2:]
            
            with open(NOTEBOOK_PATH, 'wb') as f:
                f.write(new_raw)
            print("Fixed!")
            
            # Verify
            try:
                with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
                    nb = json.load(f)
                print("SUCCESS! %d cells" % len(nb['cells']))
                
                for i, cell in enumerate(nb['cells']):
                    cell_type = cell.get('cell_type', 'unknown')
                    src = cell.get('source', [])
                    if isinstance(src, list):
                        first_line = src[0].strip()[:60] if src else '(empty)'
                    else:
                        first_line = str(src)[:60]
                    print("  Cell %d: %s | %s" % (i, cell_type, first_line))
                    
            except json.JSONDecodeError as e:
                print("Still broken: %s at line %d" % (e.msg, e.lineno))
        else:
            print("Quote exists, problem elsewhere")
    else:
        print("EOF reached")
else:
    print("Pattern not found")
