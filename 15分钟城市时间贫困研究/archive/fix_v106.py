NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

text = raw.decode('utf-8', errors='replace')

# The problem: line 3312 ends with: ...')\n",\r\n    "print('='*60)
# The \r\n got replaced with a space, causing two strings to merge

# Find the merged content: search for the pattern
search = b"print(\\'Fig11 \\xe5\\xbb\\xba\\xe7\\xad\\x91AOI\\xe5\\x88\\x86\\xe6\\x9e\\x90\\xe5\\xae\\x8c\\xe6\\x88\\x90\\'\\)\\n\\\",\\r\\n    \\"print(\\'=\\'\\*60\\)"
# That's too complex. Let me just find by searching for the double-newline pattern

# Actually, let me search for the text in the merged string
search_text = "建筑AOI分析完成')\n\",\r\n    \"print('='*60)"
if search_text in text:
    print("Found merged content!")
    pos = text.find(search_text)
    print("Position: %d" % pos)
    
    # Replace with just the first part
    replacement = "建筑AOI分析完成')\n\",\r"
    
    # Also need to restore the newline between lines
    # Line 3312 should end with \r, line 3313 should start fresh
    # So: "...分析完成')\n\",\r\n" (add newline back)
    
    print("Replacing...")
    text = text.replace(search_text, "建筑AOI分析完成')\n\",\r\n    \"print('='*60)", 1)
    
    # Check if the replacement is correct
    if "建筑AOI分析完成')\n\",\r\n    \"print('='*60)" in text:
        print("Replacement successful!")
    
    # Save
    with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
        f.write(text)
    
    # Verify
    try:
        nb = json.loads(text)
        print("\nSUCCESS! %d cells" % len(nb['cells']))
    except json.JSONDecodeError as e:
        print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
else:
    print("Pattern not found")
    
    # Try to find what's actually there
    search_text2 = "建筑AOI分析完成"
    pos2 = text.find(search_text2)
    if pos2 >= 0:
        print("Found '建筑AOI分析完成' at position %d" % pos2)
        print("Context: %s" % repr(text[pos2:pos2+100])))
