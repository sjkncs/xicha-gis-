NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# The line is missing the opening quote
# Current: nt('='*60)\n",\r,
# Should be: "print('='*60)\n",\r,

# Find 'nt(' (the end of 'prin')
search = b"nt('='*60)"
pos = raw.find(search)
print("Found 'nt(' at byte: %d" % pos)

if pos >= 0:
    # The line starts 4 bytes before 'prin'
    # So the beginning of the line is at pos - 4 (before 'prin')
    line_start = pos - 4  # 'prin' is 4 chars before 'nt'
    
    print("Line starts at byte: %d" % line_start)
    print("Bytes: %s" % repr(raw[line_start:line_start+30]))
    
    # Check if there's a quote before 'prin'
    if line_start > 0:
        print("Byte before 'prin': 0x%02X" % raw[line_start-1])
        
        # If no quote, add it
        if raw[line_start-1] != 0x22:  # 0x22 = "
            print("Missing quote! Adding...")
            new_raw = raw[:line_start] + b'"' + raw[line_start:]
            
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
            print("Quote exists, problem is elsewhere")
else:
    print("Pattern not found")
