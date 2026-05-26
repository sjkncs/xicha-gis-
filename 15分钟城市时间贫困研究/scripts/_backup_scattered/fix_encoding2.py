import json, sys

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'

# Read with latin-1 to get raw bytes (original file encoding)
with open(filepath, 'rb') as f:
    raw_bytes = f.read()

# Check the encoding of the file
print("File size:", len(raw_bytes))

# Try reading as latin-1 (preserves bytes as-is)
with open(filepath, 'r', encoding='latin-1') as f:
    nb_latin = json.load(f)

cell2 = nb_latin['cells'][2]
src = ''.join(cell2['source'])

# Check if it contains Chinese or garbled
has_chinese = any('\u4e00' <= c <= '\u9fff' for c in src)
has_garbled = '��' in src or '\ufffd' in src

print(f"Has correct Chinese: {has_chinese}")
print(f"Has garbled text: {has_garbled}")

# Save as proper UTF-8
# Convert from latin-1 to UTF-8 by re-encoding
cell2_content = src  # This is already the correct text, just in latin-1

# The fix: save with UTF-8 encoding so JSON preserves Unicode
# But we need to be careful - the current file was saved as latin-1 (UTF-8 bytes interpreted as latin-1)
# So the characters are already correct, we just need to save properly

# Reload from latin-1 and save as UTF-8
# This preserves the Chinese characters properly
with open(filepath, 'r', encoding='latin-1') as f:
    nb_correct = json.load(f)

with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(nb_correct, f, ensure_ascii=False, indent=1)

print("Re-saved with UTF-8 encoding")

# Verify by reading with UTF-8
with open(filepath, 'r', encoding='utf-8') as f:
    nb_verify = json.load(f)

cell2_v = nb_verify['cells'][2]
src_v = ''.join(cell2_v['source'])
has_correct_chinese = '安装所有必需依赖' in src_v
print(f"UTF-8 verify - has correct Chinese: {has_correct_chinese}")

# Syntax check cell 2
try:
    compile(src_v, '<cell2>', 'exec')
    print("Cell 2 syntax: OK")
except SyntaxError as e:
    print(f"Cell 2 syntax error: {e}")

print(f"\nTotal cells: {len(nb_verify['cells'])}")
