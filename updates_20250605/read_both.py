# -*- coding: utf-8 -*-
import sys, os, zipfile, xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding='utf-8')

def read_doc_utf16(path):
    """Read .doc file by decoding WordDocument stream as UTF-16-LE"""
    import olefile
    ole = olefile.OleFileIO(path)
    data = ole.openstream('WordDocument').read()
    # Decode as UTF-16-LE
    text = data.decode('utf-16-le', errors='ignore')
    # Filter out control characters but keep Chinese and meaningful content
    lines = []
    current_line = []
    for i, c in enumerate(text):
        code = ord(c)
        # Control chars except CR/LF/Tab
        if code < 32 and code not in (9, 10, 13):
            continue
        # Skip common zero-width / formatting chars
        if c in '\x00\x01\x02\x03\x07\x08\x0b\x0c\x0e\x0f':
            continue
        # Newlines
        if code == 13:  # CR
            continue
        if code == 10:  # LF
            line = ''.join(current_line).strip()
            if line:
                lines.append(line)
            current_line = []
        else:
            current_line.append(c)
    # Last line
    line = ''.join(current_line).strip()
    if line:
        lines.append(line)
    return lines

def read_pptx(path):
    """Extract text from .pptx file"""
    texts = []
    with zipfile.ZipFile(path, 'r') as z:
        # Get all slide files
        slide_files = sorted([n for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')])
        print(f"Found {len(slide_files)} slides")
        for sf in slide_files:
            slide_num = sf.split('slide')[1].replace('.xml', '')
            content = z.read(sf)
            root = ET.fromstring(content)
            # Extract all text elements
            ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
            slide_texts = []
            for t in root.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'):
                if t.text and t.text.strip():
                    slide_texts.append(t.text.strip())
            texts.append((slide_num, slide_texts))
    return texts

# Read .doc file
doc_path = r'E:\xicha gis 智能定位\报告.doc'
print("=" * 60)
print("报告.doc 内容 (前100行)")
print("=" * 60)
doc_lines = read_doc_utf16(doc_path)
for i, line in enumerate(doc_lines[:100]):
    print(f"[{i}] {line}")

print(f"\n总计 {len(doc_lines)} 行")

# Read PPTX file
pptx_path = r'E:\xicha gis 智能定位\哈工大PPT_博士答辩模板优化版_专业排版v8_跨区对比版(1).pptx'
print("\n" + "=" * 60)
print("PPT 内容概览")
print("=" * 60)
slides = read_pptx(pptx_path)
for slide_num, slide_texts in slides:
    if slide_texts:
        print(f"\n--- Slide {slide_num} ---")
        for t in slide_texts[:20]:
            print(f"  {t}")
