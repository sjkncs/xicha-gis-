import json, sys

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'

# Read raw bytes
with open(filepath, 'rb') as f:
    raw = f.read()

# Find the content of cell 2 in raw bytes
# The cell 2 content starts after "source\": ["
# Let's search for the install command bytes
search = 'pip install'.encode('utf-8')
# Also search for Chinese encoding
gbk_install = '# 安装所有必需依赖\n!pip install'.encode('gbk')
big5_install = '# 安裝所有必需依賴\n!pip install'.encode('big5')

print("UTF-8 pip install at:", raw.find(search))
print("GBK install at:", raw.find(gbk_install))
print("Big5 install at:", raw.find(big5_install))

# Let's check the raw bytes around the install section
idx = raw.find(search)
if idx > 0:
    print(f"\nRaw bytes around UTF-8 pip install (idx {idx}):")
    print(raw[idx-100:idx+200])

# Also check what character set '#' followed by Chinese would be in the raw bytes
# If the Chinese was stored as GBK in the file:
gbk_hash = '# 安装'.encode('gbk')
print(f"\nGBK '# 安装' at:", raw.find(gbk_hash))

# Check raw bytes of what looks like comment
latin1_bytes = '    \"# '.encode('latin-1')
utf8_bytes = '    \"# '.encode('utf-8')

# Search for the pip install line
pip_line_idx = raw.find(b'!pip install')
if pip_line_idx > 0:
    print(f"\nBytes before '!pip install':")
    chunk = raw[pip_line_idx-200:pip_line_idx]
    print(f"  As latin-1: {chunk!r}")
    print(f"  As utf-8: {chunk.decode('utf-8', errors='replace')}")
    print(f"  As gbk: {chunk.decode('gbk', errors='replace')}")
    print(f"  As big5: {chunk.decode('big5', errors='replace')}")
