# -*- coding: utf-8 -*-
"""Run p10_fig11_building_aoi.py from this directory to avoid shell quoting issues."""
import subprocess, sys, os

script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "v2_real_data", "p10_fig11_building_aoi.py")

env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8'
env['PYTHONLEGACYWINDOWSSTDIO'] = 'utf-8'

result = subprocess.run(
    [sys.executable, script],
    env=env,
    capture_output=False
)
sys.exit(result.returncode)
