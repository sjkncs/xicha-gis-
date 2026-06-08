import re

path = r'E:\xicha gis 智能定位\projects\15min-urban-accessibility\network_analysis_viz.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    ("ax_side.axhline(y=y+0.01, xmin=0.05, xmax=0.95, color='#ccd5de', lw=0.8, transform=ax_side.transAxes)",
     "ax_side.plot([0.05, 0.95], [y+0.01, y+0.01], color='#ccd5de', lw=0.8, transform=ax_side.transAxes)"),
    ("ax_side.axhline(y=y-0.16, xmin=0.05, xmax=0.95, color='#ccd5de', lw=0.8, transform=ax_side.transAxes)",
     "ax_side.plot([0.05, 0.95], [y-0.16, y-0.16], color='#ccd5de', lw=0.8, transform=ax_side.transAxes)"),
    ("ax_side.axhline(y=y_saved+0.01, xmin=0.05, xmax=0.95, color='#ccd5de', lw=0.8, transform=ax_side.transAxes)",
     "ax_side.plot([0.05, 0.95], [y_saved+0.01, y_saved+0.01], color='#ccd5de', lw=0.8, transform=ax_side.transAxes)"),
]

for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        print(f"Replaced: {old[:60]}")
    else:
        print(f"NOT FOUND: {old[:60]}")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
