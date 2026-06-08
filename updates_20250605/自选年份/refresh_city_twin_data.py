from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BUILDER = ROOT / "city_twin_builder.py"
OUTPUT_DIR = ROOT / "city_twin_output"
OUTPUT_HTML = OUTPUT_DIR / "city_twin_viewer.html"


def run_builder() -> int:
    if not BUILDER.exists():
        print(f"[ERROR] Missing builder: {BUILDER}")
        return 1

    cmd = [sys.executable, str(BUILDER)]
    print("[INFO] Rebuilding city twin datasets...")
    print("[INFO] Command:", " ".join(cmd))

    proc = subprocess.run(cmd, cwd=str(ROOT))
    if proc.returncode != 0:
        print(f"[ERROR] Builder failed with exit code {proc.returncode}")
        return proc.returncode

    print("[OK] Rebuild completed.")
    print(f"[OK] Output directory: {OUTPUT_DIR}")
    print(f"[OK] Main viewer: {OUTPUT_HTML}")
    print("[NEXT] Refresh your local static server page to load the latest buildings/roads/models.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_builder())
