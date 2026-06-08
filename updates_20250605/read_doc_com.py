# -*- coding: utf-8 -*-
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

import win32com.client
import pythoncom

def read_doc_via_word(doc_path):
    """Use Word COM to read .doc file"""
    pythoncom.CoInitialize()
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0

        # Open document
        doc = word.Documents.Open(os.path.abspath(doc_path))
        doc.Activate()

        # Read all text
        full_text = doc.Content.Text

        # Close without saving
        doc.Close(False)
        word.Quit()

        return full_text
    finally:
        pythoncom.CoUninitialize()

doc_path = r'E:\xicha gis 智能定位\报告.doc'
print("Using Word COM to read .doc...")
text = read_doc_via_word(doc_path)
print(f"Total chars: {len(text)}")

# Split into paragraphs
lines = [l.strip() for l in text.split('\r\n') if l.strip() and len(l.strip()) > 5]
print(f"Paragraphs: {len(lines)}")
for i, line in enumerate(lines[:80]):
    print(f"[{i}] {line[:200]}")
