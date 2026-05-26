"""Ultra-thorough fix: read raw bytes, decode every cell"""
import json, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'
backup = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb.backup_before_encoding_fix'

# Load backup (which is the original garbled version)
with open(backup, 'rb') as f:
    raw = f.read()

print(f"Backup size: {len(raw):,} bytes")

# Try to parse as JSON (UTF-8) first
try:
    text = raw.decode('utf-8')
    nb = json.loads(text)
    print("JSON parses as UTF-8: OK")
except json.JSONDecodeError:
    print("JSON does NOT parse as UTF-8")
    # Try reading as latin-1
    text = raw.decode('latin-1')
    try:
        nb = json.loads(text)
        print("JSON parses as latin-1: OK")
    except:
        print("Cannot parse JSON at all")

# Check first cell raw bytes
cell0 = nb['cells'][0]
src = ''.join(cell0['source'])
print(f"\nCell 0 first 50 chars: {repr(src[:50])}")
print(f"Cell 0 has CJK: {any(0x4e00 <= ord(c) <= 0x9fff for c in src)}")
print(f"Cell 0 has >0x7F: {any(ord(c) > 0x7F for c in src)}")

# The key insight: check if latin-1 decode can fix this
try:
    fixed_src = src.encode('latin-1').decode('utf-8')
    print(f"After latin-1 fix: has CJK = {any(0x4e00 <= ord(c) <= 0x9fff for c in fixed_src)}")
    print(f"After latin-1 fix: {repr(fixed_src[:50])}")
except Exception as e:
    print(f"Latin-1 fix failed: {e}")

# Deep inspection: what are the garbled chars actually?
print("\n=== Cell 0 garbled chars analysis ===")
garbled = [c for c in src if 0x80 <= ord(c) <= 0xFF]
for c in garbled[:10]:
    print(f"  char='{c}' code={ord(c):#04x} hex={hex(ord(c))}")
    # What UTF-8 byte does this correspond to?
    byte_val = ord(c)
    print(f"    As UTF-8 continuation (80-BF): {0x80 <= byte_val <= 0xBF}")
    print(f"    As UTF-8 first byte (C0-DF): {0xC0 <= byte_val <= 0xDF}")
    print(f"    As UTF-8 first byte (E0-EF): {0xE0 <= byte_val <= 0xEF}")
