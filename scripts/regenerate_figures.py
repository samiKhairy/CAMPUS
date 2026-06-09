"""
Run this to regenerate all figures from existing CSV data.

Usage:
    python scripts/regenerate_figures.py                              # results/unified (host run)
    python scripts/regenerate_figures.py --output-base results/server-run

--output-base is passed through to every step so the whole figure set is
generated from the dataset you choose.
"""

import subprocess
import sys
import os
import argparse

scripts_dir = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument("--output-base", default="results/unified",
                    help="Base directory where results are stored (relative to repo root)")
args = parser.parse_args()
ob = ["--output-base", args.output_base]

steps = [
    ("Summary + base figures",  [sys.executable, os.path.join(scripts_dir, "analyze_results.py")] + ob),
    ("Extra figures",           [sys.executable, os.path.join(scripts_dir, "generate_extra_figures.py")] + ob),
    ("Two-panel figures",       [sys.executable, os.path.join(scripts_dir, "generate_twopanel_figures.py")] + ob),
    ("N=20 comparison",         [sys.executable, os.path.join(scripts_dir, "plot_n20_comparison.py")] + ob),
    ("Loss figures",            [sys.executable, os.path.join(scripts_dir, "generate_loss_figures.py")] + ob),
]

for label, cmd in steps:
    print(f"\n--- {label} ---")
    result = subprocess.run(cmd, cwd=os.path.dirname(scripts_dir))
    if result.returncode != 0:
        print(f"[ERROR] {label} failed.")
        sys.exit(1)

print(f"\nAll figures regenerated in {args.output_base}/")
