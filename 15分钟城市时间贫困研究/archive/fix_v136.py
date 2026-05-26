NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

# Find "outputs": [] in the text
search = '"outputs": []'
pos = text.find(search)
if pos >= 0:
    print("Found '\"outputs\": []' at text position %d" % pos)
    print("Context: %s" % repr(text[pos-20:pos+50]))
    
    # Check what follows
    after = text[pos+len(search):pos+len(search)+20]
    print("After: %s" % repr(after))
    
    # The line should be: "outputs": [],
    # But it's: "outputs": []
    # We need to add a comma after ]
    
    # Find the exact position
    close_bracket = text.find(']', pos)
    if close_bracket >= 0:
        print("Found ] at position %d" % close_bracket)
        print("After ]: %s" % repr(text[close_bracket:close_bracket+10]))
        
        # Check if it has a comma
        if close_bracket + 1 < len(text) and text[close_bracket+1] == ',':
            print("Already has comma")
        else:
            print("Missing comma after ]")
            # Insert comma
            text = text[:close_bracket+1] + ',' + text[close_bracket+1:]
            
            # Save
            with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
                f.write(text)
            print("Saved.")
            
            # Test
            try:
                nb = json.loads(text)
                print("\nSUCCESS! %d cells" % len(nb['cells']))
            except json.JSONDecodeError as e:
                print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
