NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Read the file
with open(NOTEBOOK_PATH, 'r', encoding='utf-8', errors='replace') as f:
    text = f.read()

# Find the cell containing Fig11 - look for cell with 'Fig11 建筑AOI分析完成'
# Find the cell boundaries
search = '"cell_type": "code"'
positions = []
start = 0
while True:
    pos = text.find(search, start)
    if pos < 0:
        break
    positions.append(pos)
    start = pos + 1

print("Found %d code cells" % len(positions))

# Find which cell contains Fig11
for i, pos in enumerate(positions):
    # Find the next cell or end
    if i + 1 < len(positions):
        next_pos = positions[i + 1]
    else:
        next_pos = len(text)
    
    cell_text = text[pos:next_pos]
    
    # Check if this cell contains Fig11
    if 'Fig11' in cell_text and '建筑AOI' in cell_text:
        print("\nFound Fig11 cell at position %d" % pos)
        print("Cell preview: %s" % repr(cell_text[:500]))
        
        # Find the source array bounds
        source_start = cell_text.find('"source": [')
        if source_start >= 0:
            print("\nSource array starts at cell offset %d" % source_start)
            # Check the source structure
            source_text = cell_text[source_start:]
            print("Source: %s" % repr(source_text[:200]))
            
            # Try to parse just this cell as JSON
            # Find the cell object bounds
            # Look for {"cell_type":... to }
            cell_json_start = cell_text.rfind('{', 0, 50)
            print("\nCell JSON starts at offset %d" % cell_json_start)
            
            # Find the closing }
            # Simple approach: count braces
            depth = 0
            cell_end = cell_json_start
            in_string = False
            escape = False
            
            for j, c in enumerate(cell_text[cell_json_start:]):
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
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        cell_end = cell_json_start + j + 1
                        break
            
            print("Cell ends at offset %d" % cell_end)
            cell_json = cell_text[cell_json_start:cell_end]
            
            try:
                cell_obj = json.loads(cell_json)
                print("\nCell parses OK!")
                print("Source lines: %d" % len(cell_obj.get('source', [])))
            except json.JSONDecodeError as e:
                print("\nCell JSON error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
                print("Problematic section: %s" % repr(cell_json[e.pos-50:e.pos+50]))
        
        break
