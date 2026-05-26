NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d bytes" % len(raw))

# ================================================================
# Approach: Byte-level search and replace
# Find the broken section: "    },\n    ],\n..." 
# Replace with: "    },\n",\n  ],\n" + proper metadata
# ================================================================

# In the file, the broken section starts after:
# "    \"  ]\n\",\n"  (Section 13 source array close)
# followed by:
# "    \"},\n    ],\n"  (broken: Section 13 cell close with missing closing string literal)
#
# Search for the pattern in bytes
# Pattern: 22 20 20 20 20 7D 2C (quote, space, space, space, space, }, comma)
# But this is hard to find without more context
#
# Let me find the Section 13 header first
search1 = b"<a id='13'"
idx1 = raw.find(search1)
print("Section 13 header at byte %d" % idx1)

# Find the Section 13 source close
search2 = b'\\"  ]\\"'
idx2 = raw.find(search2, idx1)
print("Section 13 source close at byte %d" % idx2)

# Now show bytes from idx2 onwards
print("\n=== Bytes from idx2 to idx2+300 ===")
chunk = raw[idx2:idx2+300]
print("hex:", chunk.hex())
print("str:", chunk.decode('utf-8', errors='replace'))

# The broken section: after the source close, there's "    }," instead of "    },\n","
# Then there's "    ]," instead of proper close
# Let me find the exact position

# Search for the pattern: "    }," followed by newline
# In bytes: 22 20 20 20 20 7D 2C 0D 0A (or 0A)
search3 = b'"    },'  # 8 chars: quote + 4 spaces + } + ,
idx3 = raw.find(search3)
print("\n'\"    },' pattern at byte %d" % idx3)

if idx3 > 0:
    # Show context
    ctx = raw[idx3:idx3+50]
    print("Context:", ctx)
    print("Hex:", ctx.hex())
    
    # This is the broken line
    # Fix: replace "    }," with '    "},\n",'
    # In bytes:
    # OLD: 22 20 20 20 20 7D 2C  (",    },)
    # NEW: 22 20 20 20 20 7D 2C 0D 0A 22  (",    },\r\n",) 
    # Wait, but in the file it's "    " },' literally
    # Let me decode the bytes around idx3
    print("\nDecoded bytes around idx3:")
    for i in range(idx3, min(idx3+20, len(raw))):
        b = raw[i]
        c = chr(b) if 32 <= b < 127 else '.'
        print("  %d: 0x%02x = %r (%s)" % (i, b, bytes([b]), c))
