NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]

line_start = lf_positions[3311] + 1
line_end = lf_positions[3312] + 1  # +1 to include LF
line_bytes = raw[line_start:line_end]

print("Line bytes (%d-%d):" % (line_start, line_end))
print("  %s" % ' '.join('%02X' % b for b in line_bytes))
print("  %s" % repr(line_bytes))

# Count quote bytes (0x22) in the line
quote_positions = [i for i, b in enumerate(line_bytes) if b == 0x22]
print("\nQuote byte offsets in line: %s" % str(quote_positions))
print("Quote byte values: %s" % ' '.join('0x%02X' % line_bytes[i] for i in quote_positions))
print("Quote char values: %s" % ' '.join('%d:%s' % (i, repr(chr(line_bytes[i]))) for i in quote_positions))

# JSON strings contain \" for literal quotes
# So 0x22 (") should only appear as \" in JSON strings
# If we see unescaped 0x22 in the JSON source, it terminates the string!
print("\nChecking for unescaped quotes...")
for i, b in enumerate(line_bytes):
    if b == 0x22:  # Quote
        if i == 0 or line_bytes[i-1] != 0x5C:  # Not preceded by backslash
            # Check if it's preceded by an even number of backslashes
            num_backslashes = 0
            j = i - 1
            while j >= 0 and line_bytes[j] == 0x5C:
                num_backslashes += 1
                j -= 1
            if num_backslashes % 2 == 0:
                print("  UNESCAPED quote at line offset %d (abs %d): %s" % (i, line_start+i, repr(line_bytes[max(0,i-10):i+10])))

# Count backslashes before each quote
print("\nBackslashes before each quote:")
for qp in quote_positions:
    num_bs = 0
    j = qp - 1
    while j >= 0 and line_bytes[j] == 0x5C:
        num_bs += 1
        j -= 1
    print("  Quote at offset %d: preceded by %d backslash(es)" % (qp, num_bs))
