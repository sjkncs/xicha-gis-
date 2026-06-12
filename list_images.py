# -*- coding: utf-8 -*-
"""List all image files in the project"""
import os, glob

base = r'E:\xicha gis 智能定位'
patterns = ['**/*.png', '**/*.jpg', '**/*.jpeg', '**/*.svg', '**/*.gif', '**/*.pdf']

all_files = []
for p in patterns:
    for f in glob.glob(os.path.join(base, p), recursive=True):
        size_mb = os.path.getsize(f) / (1024*1024)
        all_files.append((f, size_mb))

all_files.sort(key=lambda x: x[1], reverse=True)

print(f"Total images: {len(all_files)}")
for f, s in all_files[:100]:
    rel = f.replace(base, '').lstrip('\\')
    print(f"{s:.2f}MB  {rel}")
