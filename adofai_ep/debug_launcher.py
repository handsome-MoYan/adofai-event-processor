#!/usr/bin/env python3
import subprocess, sys, os
from pathlib import Path

base = Path(__file__).parent
main_script = base / "main.py"
if not main_script.exists():
    print("main.py not found!", file=sys.stderr)
    sys.exit(1)

subprocess.Popen([sys.executable, str(main_script), "--debug"])