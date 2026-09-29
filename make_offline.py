#!/usr/bin/env python3
"""
Run this ONCE on a PC WITH internet (Windows, Linux or Mac) before you go to college.
It downloads Linux-compatible packages into the 'wheelhouse' folder so the college
PC can install without internet.

  python make_offline.py 3.12

Replace 3.12 with the Python version on the college PC (check it there with: python3 --version).
"""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
ver = sys.argv[1] if len(sys.argv) > 1 else "3.12"
cmd = [sys.executable, "-m", "pip", "download", "-r", str(root / "requirements.txt"),
       "-d", str(root / "wheelhouse"), "--only-binary=:all:",
       "--implementation", "cp", "--python-version", ver]
for plat in ("manylinux2014_x86_64", "manylinux_2_17_x86_64", "manylinux_2_28_x86_64", "manylinux_2_34_x86_64"):
    cmd += ["--platform", plat]
print("Downloading Linux packages for Python", ver, "...")
sys.exit(subprocess.call(cmd))
