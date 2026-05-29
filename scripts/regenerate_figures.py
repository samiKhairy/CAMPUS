"""
Run this to regenerate all figures from the existing CSV data.
Usage: python scripts/regenerate_figures.py
"""

import subprocess
import sys
import os

scripts_dir = os.path.dirname(os.path.abspath(__file__))

steps = [
    ("Summary + base figures",  [sys.executable, os.path.join(scripts_dir, "analyze_results.py")]),
    ("Extra figures",           [sys.executable, os.path.join(scripts_dir, "generate_extra_figures.py")]),
    ("Two-panel figures",       [sys.executable, os.path.join(scripts_dir, "generate_twopanel_figures.py")]),
]

for label, cmd in steps:
    print(f"\n--- {label} ---")
    result = subprocess.run(cmd, cwd=os.path.dirname(scripts_dir))
    if result.returncode != 0:
        print(f"[ERROR] {label} failed.")
        sys.exit(1)

print("\nAll figures regenerated in results/unified/")
