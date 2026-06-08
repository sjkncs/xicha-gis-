# -*- coding: utf-8 -*-
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

import olefile

def read_doc_streams(path):
    ole = olefile.OleFileIO(path)
    data = ole.openstream('WordDocument').read()
    text = data.decode('utf-16-le', errors='ignore')
    return text

doc_path = r'E:\xicha gis 智能定位\报告.doc'
text = read_doc_streams(doc_path)

# 找所有双字节范围字符
chinese_lines = []
lines = text.split('\n')
for i, line in enumerate(lines):
    chinese = sum(1 for c in line if '\u4e00' <= c <= '\u9fff')
    if chinese > 5:
        # 清理 null bytes and short control chars
        cleaned = ''.join(c for c in line if ord(c) >= 32 or c == '\t')
        if len(cleaned.strip()) > 3:
            chinese_lines.append((i, chinese, cleaned.strip()[:200]))

print(f"Total lines with Chinese: {len(chinese_lines)}")
for idx, (orig_i, chinese_count, content) in enumerate(chinese_lines[:80]):
    print(f"[{idx}] (raw:{orig_i}, CN:{chinese_count}) {content}")
