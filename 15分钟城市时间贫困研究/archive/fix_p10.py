# -*- coding: utf-8 -*-
"""Fix the syntax errors in p10_fig11_building_aoi.py."""
import os

filepath = os.path.join(os.path.dirname(__file__), 'v2_real_data', 'p10_fig11_building_aoi.py')

with open(filepath, 'rb') as f:
    content = f.read()

lines = content.split(b'\n')

# Replace lines 470-475 (0-indexed: 469-474)
new_lines_470_475 = [
    b'print(f"Total buildings: {len(bld_wgs):,}")',
    b'hr = (bld_wgs["levels_num"].fillna(2) > 20).sum()',
    b'print(f"High-rise (>20F): {hr:,} ({100*hr/len(bld_wgs):.1f}%)")',
    b'print(f"Super high-rise (>50F): {(bld_wgs["levels_num"].fillna(0) > 50).sum():,}")',
    b'bld_type_msg = "Building types: Res_low=%d / Res_mid=%d / Commercial=%d" % (',
    b'    (bld_wgs["btype_cat"] == "residential_low").sum(),',
    b'    (bld_wgs["btype_cat"] == "residential_mid").sum(),',
    b'    (bld_wgs["btype_cat"] == "commercial").sum())',
    b'print(bld_type_msg)',
]

new_lines = lines[:469] + new_lines_470_475 + lines[475:]
new_content = b'\n'.join(new_lines)

with open(filepath, 'wb') as f:
    f.write(new_content)

print('File patched. Verifying syntax...')

# Verify syntax
import ast
decoded = new_content.decode('utf-8')
try:
    ast.parse(decoded)
    print('Syntax OK!')
except SyntaxError as e:
    print('Syntax error at line {}: {}'.format(e.lineno, e.msg))
    decoded_lines = decoded.split('\n')
    for i in range(max(0, e.lineno-3), min(len(decoded_lines), e.lineno+2)):
        print('  {:4d}: {}'.format(i+1, decoded_lines[i]))
