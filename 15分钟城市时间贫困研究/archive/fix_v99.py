NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Find all LF positions
lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]

print("LF[3309] to LF[3315]:")
for i in range(3309, min(3315, len(lf_positions))):
    print("  LF[%d] = byte %d" % (i, lf_positions[i]))

print("\n=== Actual line boundaries ===")
for line_num in range(3309, 3317):
    lf_idx = line_num - 1  # 0-indexed
    prev_lf = lf_positions[lf_idx - 1] + 1 if lf_idx > 0 else 0
    curr_lf = lf_positions[lf_idx]
    next_lf = lf_positions[lf_idx + 1] if lf_idx + 1 < len(lf_positions) else len(raw)
    
    # Line starts after previous LF, ends at current LF
    line_start = prev_lf
    line_end = curr_lf
    line_bytes = raw[line_start:line_end]
    
    print("Line %d: bytes %d-%d (%d bytes): %s" % (
        line_num, line_start, line_end, len(line_bytes),
        repr(line_bytes[:80])))
