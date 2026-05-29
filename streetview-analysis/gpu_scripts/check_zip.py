#!/usr/bin/env python3
import zipfile
z = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\model_segformer_b3.zip"
with zipfile.ZipFile(z) as zf:
    names = zf.namelist()
    print(f"Total files: {len(names)}")
    for n in names[:15]:
        print(f"  {n}")
    print("  ...")
    for n in names[-5:]:
        print(f"  {n}")
    # Check for hub prefix
    has_hub = any(n.startswith('hub/') for n in names)
    print(f"\nHas 'hub/' prefix: {has_hub}")
    # Check if it's directly under snapshots
    has_snap_direct = any(n.startswith('snapshots/') for n in names)
    print(f"Has 'snapshots/' prefix: {has_snap_direct}")
