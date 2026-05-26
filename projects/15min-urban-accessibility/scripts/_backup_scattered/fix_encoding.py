import json

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'

# Read with latin-1 to preserve raw bytes (original file was latin-1 encoded)
with open(filepath, 'r', encoding='latin-1') as f:
    nb = json.load(f)

print(f"Notebook: {len(nb['cells'])} cells")

# Check cell 2
cell2 = nb['cells'][2]
src = ''.join(cell2['source'])
print(f"\nCell 2 content (first 100 chars):")
print(src[:100])
print(f"\nIs it valid Python syntax?")
try:
    compile(src, '<cell>', 'exec')
    print("YES - valid Python!")
except SyntaxError as e:
    print(f"NO - SyntaxError: {e}")

# Check if Chinese chars in cell 2 are correct
if '安装所有必需依赖' in src:
    print("✓ Chinese chars in cell 2 are CORRECT")
elif '��װ' in src or 'װ' in src:
    print("✗ Chinese chars in cell 2 are GARBLED")
else:
    print("? Chinese chars in cell 2 - unexpected state")

# Save with UTF-8 encoding
with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print("\n✓ Re-saved with UTF-8 encoding")

# Verify the save worked
with open(filepath, 'r', encoding='utf-8') as f:
    nb2 = json.load(f)
cell2b = nb2['cells'][2]
src2 = ''.join(cell2b['source'])
if '安装所有必需依赖' in src2:
    print("✓ UTF-8 save verified - Chinese chars are correct!")
elif '��װ' in src2:
    print("✗ Still garbled after UTF-8 save")
    print(f"First 100: {src2[:100]}")
else:
    print("? Unexpected state after UTF-8 save")
