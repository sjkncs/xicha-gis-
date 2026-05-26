NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines: %d" % len(lines))

# Context
print("\nLines 3310-3320:")
for i in range(3309, min(3320, len(lines))):
    print("%d: %s" % (i+1, repr(lines[i])))

# Fix: Line 3313 should end the source array with `],` not just `,`
# Line 3314 should be the cell close `},`
# Line 3315 should be the cells array close `]`

# Currently:
# 3313: `    "print(\'=\'*60)\n",`  <- ends source array
# 3314: `   ],`  <- WRONG: this is a string literal
# 3315: `   },`  <- wrong
# 3316: ` ],`   <- wrong

# Fix:
# 3313: `    "print(\'=\'*60)\n",`  <- keep as is (already ends with comma)
# 3314: `   ],` -> `   ],` (this IS the source array close, correct)
# 3315: `   },` -> `   },` (this IS the cell close, correct)
# 3316: ` ],` -> ` ]` (remove comma since it's the last cell and cells array)

# Actually wait, let me check if line 3313 has a newline
print("\n\nLine 3313 ends with: '%s'" % lines[3312][-10:])

# The fix should be:
# Change line 3314 from `   ],` to `   ]` (remove comma)
# Change line 3315 from `   },` to `   }` (remove comma)

# But wait - is there supposed to be more content in the Fig11 cell?
# Let me check if there's supposed to be more code after line 3313

# Actually looking at the earlier cells, the pattern is:
# source line 1,
# source line 2,
# source line N (last line, no comma!)
# `],`  <- closes source array
# `},`  <- closes cell (comma if more cells)
# `]`   <- closes cells array (no comma)

# But currently line 3314 is `   ],` which IS the correct source close
# The problem is that line 3313 ends with `,` but there's no `]` on line 3314
# Oh wait, line 3314 IS `   ],` which DOES close the array

# Let me re-check. The error is "Illegal trailing comma before end of array"
# This means the parser sees content at line 3313, then the end of the array
# But there's a comma AFTER the last element

# Looking at line 3313: `    "print(\'=\'*60)\n",`
# This ends with `",` - comma inside the string, plus quote and comma outside
# So the string is `"print('='*60)\n",` - the comma at the end is INSIDE the JSON

# Wait, that doesn't make sense. Let me look at the repr more carefully:
# `'    "print(\'=\'*60)\\n",'` = `    "print('='*60)\n",`
# This is a JSON string: `    "print('='*60)\n",`
# The string content is `print('='*60)\n` and there's a comma after the closing quote

# Actually I think I see it now - the line 3313 should end the source array
# But the issue is that the Fig11 cell doesn't have all the fields (outputs, etc.)

# Let me just replace the end section completely
