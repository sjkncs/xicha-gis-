NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# At byte 166430, we have: 22 5C 6E 22 5C 72
# = quote, backslash, n, quote, backslash, r

# After that: 0A = LF
# Then: 20 20 20 5D 2C = spaces ] comma
# Then: 0D 0A = CR LF

# So the sequence is:
# "print('='*60)\n"\r
# [space][space][space]], then CR LF

# Now let's understand the JSON structure:
# This line is one element in the source array
# The element ends with: "print('='*60)\n"\r
# Then there's ], which closes the source array
# But wait - in JSON, strings end with a quote "
# So the string should be: "print('='*60)\n"
# And after the string, there should be either , or ]

# Looking at the hex:
# ...29 5C 6E 22 5C 72 0A 20 20 20 5D 2C
# = ) \ n " \ r LF [space][space][space] ] ,

# So the line is:
#     "print('='*60)\n"\r
# [space][space][space]]

# In JSON, this parses as:
# - String: "print('='*60)\n"\r" (ends with closing quote)
# - Then [space][space][space]] = ]] (two closing brackets?)
# - Then comma

# Wait, there are TWO closing brackets! That means there are TWO arrays!

# Let me trace the structure:
# The source array [...], then }, closes the cell object
# But there's ] before } and another ] after }???

print("Examining structure around byte 166430...")

# Let me see the context more clearly
pos = 166420
chunk = raw[pos:pos+50]
print("Bytes %d-%d: %s" % (pos, pos+len(chunk), repr(chunk)))

# The issue: There's an extra ] somewhere
# Looking at: 0A 20 20 20 5D 2C 0D 0A 20 20 20 7D 0D 0A 20 5D
# After the last string comes:
#   LF, 3 spaces, ], comma, CR, LF, 3 spaces, }, CR, LF, space, ]

# So structure is:
#     "print('='*60)\n"\r   <- last source string
#    ],                       <- close source array
#   }                         <- close cell object
#  ]                          <- close cells array?

# But wait, this looks like the source array is closed, then the cell is closed
# But where does the next cell start?

# Let me search for where the cells array closes
# The cells array should end with: ]
# Let me find all ] in the file

print("\nSearching for closing patterns...")

# Find the pattern: '],\n  }' which closes a cell
search = b'],\r\n  }'
positions = []
start = 0
while True:
    p = raw.find(search, start)
    if p < 0:
        break
    positions.append(p)
    start = p + 1

print("Found %d '],\\r\\n  }' patterns" % len(positions))
for p in positions[-5:]:
    print("  byte %d: %s" % (p, repr(raw[p-20:p+30])))
