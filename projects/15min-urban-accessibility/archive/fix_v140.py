NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Read the file
with open(NOTEBOOK_PATH, 'r', encoding='utf-8', errors='replace') as f:
    text = f.read()

# Find the Fig11 cell
search = '"cell_type": "code"'
positions = []
start = 0
while True:
    pos = text.find(search, start)
    if pos < 0:
        break
    # Find the start of this cell object (look for { before cell_type)
    obj_start = text.rfind('{', 0, pos)
    if obj_start >= 0:
        positions.append(obj_start)
    start = pos + 1

print("Found %d code cells" % len(positions))

# Find which cell contains Fig11
for i, pos in enumerate(positions):
    if i + 1 < len(positions):
        next_pos = positions[i + 1]
    else:
        next_pos = len(text)
    
    cell_text = text[pos:next_pos]
    
    if 'Fig11' in cell_text and '建筑AOI' in cell_text:
        print("\nFound Fig11 cell at position %d" % pos)
        
        # Try to parse this cell as JSON
        try:
            cell_obj = json.loads(cell_text)
            print("Cell parses OK!")
            print("Source: %d lines" % len(cell_obj.get('source', [])))
            
            # The source array should end without a trailing comma
            source = cell_obj.get('source', [])
            if source:
                print("Last source element: %s" % repr(source[-1]))
            
        except json.JSONDecodeError as e:
            print("Cell JSON error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
            # Try to find the issue
            
            # Find the source array and check it
            source_match = cell_text.find('"source": [')
            if source_match >= 0:
                print("\nSource array starts at offset %d" % source_match)
                # Look for the end of source array
                source_section = cell_text[source_match:]
                
                # Find where source array closes
                # It should end with: ]
                bracket_count = 0
                in_string = False
                escape = False
                source_end = 0
                
                for j, c in enumerate(source_section):
                    if escape:
                        escape = False
                        continue
                    if c == '\\':
                        escape = True
                        continue
                    if c == '"':
                        in_string = not in_string
                        continue
                    if in_string:
                        continue
                    if c == '[':
                        bracket_count += 1
                    elif c == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            source_end = source_match + j + 1
                            break
                
                print("Source array ends at offset %d" % source_end)
                print("Last 100 chars of source: %s" % repr(source_section[source_end-100:source_end+50]))
        
        break
