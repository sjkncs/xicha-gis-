NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d bytes" % len(raw))

# Find the Section 13 header
search = b"id='13'"
idx = raw.find(search)
print("id='13' at byte %d" % idx)

if idx >= 0:
    # Show 300 bytes from there (in decoded form)
    ctx = raw[idx-50:idx+300]
    decoded = ctx.decode('utf-8', errors='replace')
    print("\nDecoded context:")
    print(repr(decoded))
    
    # Now find where the cell closes
    # Look for the pattern "},\r\n ],\r\n"
    close_idx = raw.find(b'},', idx)
    print("\n'},' found at byte %d" % close_idx)
    
    if close_idx >= 0:
        # Show 200 bytes around the close
        close_ctx = raw[close_idx:close_idx+200]
        print("\nAround close:")
        print(repr(close_ctx.decode('utf-8', errors='replace')))
        
        # The issue is: after the Section 13 header content, there should be:
        # '  ]\n",  <- close source array (5 spaces + ] + \n" + ,)
        # '},\n' <- close cell object (2 spaces + } + ,)
        # '],\n' <- close cells array (2 spaces + ])
        
        # But currently there's:
        # '  ]\n",  <- source close (5 spaces, correct)
        # '},\n',  <- cell close (but missing 2-space indent)
        # '],\n'  <- cells array close
        
        # So the fix is to replace the '},\n' with '  },\n'
        
        # Find the pattern in the raw bytes
        # After Section 13 header, look for "  ]\n", followed by "},\n ],\n"
        # In the file, these are CRLF (Windows)
        
        # Let's search for the pattern
        # The pattern after source close is: 
        # '    "  ]\n",\r\n    },\r\n ],\r\n'
        # We want:
        # '    "  ]\n",\r\n  },\r\n ],\r\n'
        
        # Search for the pattern
        # "  ]\n",\r\n    },\r\n ],\r\n metadata
        # In hex: 22 20 20 20 20 5D 0D 0A 20 20 20 20 7D 0D 0A 20 20 5D 0D 0A
        
        # Find "],\r\n" which should be the cells array close
        # But first, find the Section 13 header close
        # Look backwards from the metadata start
        meta_idx = raw.find(b'"metadata":', idx)
        print("\nMetadata at byte %d" % meta_idx)
        
        if meta_idx >= 0:
            # Show bytes between Section 13 header and metadata
            between = raw[idx:meta_idx]
            print("\nBetween header and metadata (%d bytes):" % len(between))
            print(repr(between.decode('utf-8', errors='replace')))
            
            # Find the closing patterns
            close_source_idx = raw.find(b'],', idx)
            print("\n'],' (source close?) at byte %d" % close_source_idx)
            
            close_cell_idx = raw.find(b'},', close_source_idx)
            print("'},' (cell close?) at byte %d" % close_cell_idx)
            
            close_cells_idx = raw.find(b'],', close_cell_idx)
            print("'],' (cells close?) at byte %d" % close_cells_idx)
            
            # Show bytes around these
            if close_cell_idx >= 0:
                cell_ctx = raw[close_source_idx:close_cell_idx+50]
                print("\nBetween source close and cell close:")
                print(repr(cell_ctx.decode('utf-8', errors='replace')))
