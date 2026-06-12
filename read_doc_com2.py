# -*- coding: utf-8 -*-
import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

import win32com.client
import pythoncom
import win32api

def read_doc_via_word(doc_path):
    pythoncom.CoInitialize()
    word = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0

        abs_path = os.path.abspath(doc_path)
        doc = word.Documents.Open(abs_path, ConfirmConversions=False, ReadOnly=True)
        doc.Activate()

        full_text = doc.Content.Text

        # Write text to a temp file immediately
        temp_txt = os.path.join(os.path.dirname(doc_path), '_report_text.txt')
        with open(temp_txt, 'w', encoding='utf-8') as f:
            f.write(full_text)
        print(f"Text written to: {temp_txt}")
        print(f"Total chars: {len(full_text)}")

        # Try to close gracefully
        try:
            doc.Close(False)
        except:
            pass
        try:
            word.Quit()
        except:
            pass

        return full_text
    except Exception as e:
        print(f"Error: {e}")
        # Still try to write whatever we got
        return ""
    finally:
        if word:
            try:
                word.Quit()
            except:
                pass
        pythoncom.CoUninitialize()

doc_path = r'E:\xicha gis 智能定位\报告.doc'
text = read_doc_via_word(doc_path)

if text:
    lines = [l.strip() for l in text.split('\r\n') if l.strip() and len(l.strip()) > 3]
    print(f"Paragraphs: {len(lines)}")
    for i, line in enumerate(lines[:100]):
        print(f"[{i}] {line[:200]}")
