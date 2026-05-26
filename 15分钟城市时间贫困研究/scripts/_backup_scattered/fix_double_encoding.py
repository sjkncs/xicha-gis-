import json, re

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'

with open(filepath, 'rb') as f:
    raw = f.read()

# The problem: Chinese text was double-encoded:
# UTF-8 text -> interpreted as latin-1 -> stored in JSON -> double-encoded again
# Fix: decode from latin-1 then re-encode as proper UTF-8

# Approach: treat each string value in the notebook as if it was UTF-8 bytes
# that were decoded as latin-1, then encode back and save as proper JSON

# The file was saved with latin-1 encoding of UTF-8 text
# We need to read the raw bytes and properly reconstruct the UTF-8 strings

# Actually, let me try a different approach:
# The json.loads() with latin-1 already preserved the correct bytes
# The issue is when we json.dump with ensure_ascii=False, it should work

# Let me check: the raw bytes at position 3958 show UTF-8 encoded Chinese
# So the source bytes ARE correct UTF-8
# The issue must be in how we READ the file

# Try: read raw bytes -> decode as latin-1 (this gives the python string)
# Then for each Chinese character, it shows as weird chars
# To fix: for each line, encode back as latin-1 bytes, then decode as utf-8

with open(filepath, 'r', encoding='latin-1') as f:
    nb_latin = json.load(f)

def fix_garbled_text(text):
    """Convert garbled text (latin-1 interpretation of UTF-8 bytes) back to proper Chinese."""
    if not text:
        return text
    # Encode as latin-1 (which gives the UTF-8 byte values)
    # Then decode as UTF-8
    try:
        return text.encode('latin-1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text

fixed_count = 0
for cell in nb_latin['cells']:
    if 'source' in cell and isinstance(cell['source'], list):
        new_source = []
        for line in cell['source']:
            if isinstance(line, str):
                # Check if this line has garbled Chinese
                if any(ord(c) > 127 for c in line):
                    fixed_line = fix_garbled_text(line)
                    if fixed_line != line:
                        fixed_count += 1
                        new_source.append(fixed_line)
                    else:
                        new_source.append(line)
                else:
                    new_source.append(line)
            else:
                new_source.append(line)
        cell['source'] = new_source

print(f"Fixed {fixed_count} lines with garbled text")

# Verify fix
cell2 = nb_latin['cells'][2]
src2 = ''.join(cell2['source'])
has_chinese = any('\u4e00' <= c <= '\u9fff' for c in src2)
print(f"Cell 2 has correct Chinese: {has_chinese}")
if has_chinese:
    print(f"Cell 2 first 50 chars: {src2[:50]}")

# Save with UTF-8
with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(nb_latin, f, ensure_ascii=False, indent=1)
print("Saved with UTF-8 encoding")

# Verify saved file
with open(filepath, 'r', encoding='utf-8') as f:
    nb_verify = json.load(f)
cell2_v = nb_verify['cells'][2]
src2_v = ''.join(cell2_v['source'])
has_chinese_v = any('\u4e00' <= c <= '\u9fff' for c in src2_v)
print(f"Verification - cell 2 has correct Chinese: {has_chinese_v}")

# Syntax check
try:
    compile(src2_v, '<cell2>', 'exec')
    print("Cell 2 syntax: OK!")
except SyntaxError as e:
    print(f"Cell 2 syntax: {e}")
