# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')

import olefile

path = r'E:\xicha gis 智能定位\报告.doc'
ole = olefile.OleFileIO(path)

print("=== OLE streams ===")
for stream in ole.listdir():
    name = '/'.join(stream)
    print(f"  {name}")

# Try to read the main text stream
print("\n=== SummaryInformation ===")
try:
    prop = ole.get_properties('SummaryInformation')
    print(f"  Title: {prop.title}")
    print(f"  Author: {prop.author}")
    print(f"  Subject: {prop.subject}")
    print(f"  Keywords: {prop.keywords}")
    print(f"  Comments: {prop.comments}")
    print(f"  Template: {prop.template}")
    print(f"  TotalPages: {prop.total_pages}")
    print(f"  TotalChars: {prop.total_chars}")
except Exception as e:
    print(f"  Error: {e}")

# Try to read 1Table stream
print("\n=== Trying Word Document streams ===")
if ole.exists('WordDocument'):
    print("  WordDocument stream found!")
    data = ole.openstream('WordDocument').read()
    print(f"  Size: {len(data)} bytes")
    # Try to find text - look for ANSI text chunks
    text_chars = []
    for i, b in enumerate(data):
        if 32 <= b <= 126 or b in (9, 10, 13):
            text_chars.append(chr(b))
        else:
            if len(text_chars) > 20:
                chunk = ''.join(text_chars)
                if any('\u4e00' <= c <= '\u9fff' for c in chunk):
                    pass
                if chunk.strip():
                    print(f"  Text chunk: {chunk[:200]}")
            text_chars = []
else:
    print("  No WordDocument stream - trying Data stream")
    if ole.exists('Data'):
        data = ole.openstream('Data').read()
        print(f"  Data stream size: {len(data)} bytes")
        # Try UTF-16 decode
        try:
            text = data.decode('utf-16-le', errors='ignore')
            if text.strip():
                print(f"  UTF-16 text (first 2000 chars): {text[:2000]}")
        except:
            pass
        # Try to find readable ASCII
        chunk = []
        for i, b in enumerate(data):
            if 32 <= b <= 126 or b in (9, 10, 13):
                chunk.append(chr(b))
            else:
                if len(chunk) > 5:
                    s = ''.join(chunk).strip()
                    if s:
                        print(f"  ASCII chunk: {s[:200]}")
                chunk = []
