from __future__ import annotations

from pathlib import Path
from PIL import Image
import numpy as np

# Batch-generate local overlays for viz samples.
# For each `*.png` in VIZ_SAMPLES_DIR (excluding `__LOCAL_OVERLAY` outputs),
# it searches for a same-basename `*.jpg` under SEARCH_ROOT and writes
# `<basename>__LOCAL_OVERLAY.png` next to the viz.

VIZ_SAMPLES_DIR = Path(r"E:\xicha gis 智能定位\自选年份\gpu_scripts\results\viz_samples")
SEARCH_ROOT = Path(r"E:\xicha gis 智能定位\自选年份\baidu_streetview")

ALPHA_ORIG = 0.60
ALPHA_VIZ = 0.40


def find_original_jpg(basename: str) -> Path | None:
    target = basename + ".jpg"
    # recursive glob, stop at first match
    for p in SEARCH_ROOT.rglob(target):
        return p
    return None


def make_overlay(orig_path: Path, viz_path: Path, out_path: Path) -> None:
    orig = Image.open(orig_path).convert("RGB")
    viz = Image.open(viz_path).convert("RGB")

    # Keep viz resolution; resize original to match
    orig = orig.resize(viz.size)

    o = np.asarray(orig, dtype=np.float32)
    v = np.asarray(viz, dtype=np.float32)

    out = (o * ALPHA_ORIG + v * ALPHA_VIZ).clip(0, 255).astype(np.uint8)
    Image.fromarray(out).save(out_path)


def main() -> None:
    if not VIZ_SAMPLES_DIR.exists():
        raise SystemExit(f"Missing viz samples dir: {VIZ_SAMPLES_DIR}")

    viz_files = sorted(VIZ_SAMPLES_DIR.glob("*.png"))
    viz_files = [p for p in viz_files if "__LOCAL_OVERLAY" not in p.name]

    if not viz_files:
        print(f"No viz png files found in: {VIZ_SAMPLES_DIR}")
        return

    ok = 0
    miss = 0
    for viz_path in viz_files:
        basename = viz_path.stem
        out_path = VIZ_SAMPLES_DIR / f"{basename}__LOCAL_OVERLAY.png"

        if out_path.exists():
            print(f"SKIP exists: {out_path.name}")
            ok += 1
            continue

        orig_path = find_original_jpg(basename)
        if orig_path is None:
            print(f"MISS original: {basename}.jpg")
            miss += 1
            continue

        make_overlay(orig_path, viz_path, out_path)
        print(f"OK: {out_path.name}  (orig: {orig_path})")
        ok += 1

    print("\nDone.")
    print(f"  overlays ok: {ok}")
    print(f"  originals missing: {miss}")


if __name__ == "__main__":
    main()
