# main
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import multiprocessing
from pathlib import Path
from gui.app import start_gui

from gui.app import log_q
# print("main.py 拿到的 log_q 地址：", id(log_q))

if __name__ == "__main__":
    multiprocessing.freeze_support()
    start_gui()