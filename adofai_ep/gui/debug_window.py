# debug_window.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import queue
import tkinter as tk
from pathlib import Path
from tkinter import ttk, scrolledtext

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

class DebugWindow(tk.Toplevel):
    TITLE = "ADOFAI Event Processor – Debug"
    FONT = ("Consolas", 9)

    def __init__(self, parent=None, log_queue=None):
        super().__init__(parent)
        self.queue = log_queue or queue.Queue()
        self.title(self.TITLE)
        self.geometry("800x420")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.txt = scrolledtext.ScrolledText(self, state="disabled", font=self.FONT)
        self.txt.pack(fill="both", expand=True)

        frm = ttk.Frame(self)
        frm.pack(fill="x", padx=5, pady=3)
        ttk.Button(frm, text="Save", command=self.save_log).pack(side="right")
        ttk.Button(frm, text="Clear", command=self.clear).pack(side="right", padx=5)
        self.auto_scroll = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm, text="Auto-scroll", variable=self.auto_scroll).pack(side="left")

        self.after(100, self.poll)

    # ---------- 公共 ----------
    def write(self, msg, level="INFO"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        tag = level.lower()
        self.txt.configure(state="normal")
        self.txt.insert("end", f"{ts} [{level}] {msg}\n", tag)
        self.txt.configure(state="disabled")
        if self.auto_scroll.get():
            self.txt.see("end")

        # 同时写入文件
        with open(LOG_DIR / f"{datetime.date.today().isoformat()}.log",
                  "a", encoding="utf-8") as f:
            f.write(f"{ts} [{level}] {msg}\n")

    def poll(self):
        try:
            while True:
                item = self.queue.get_nowait()
                if isinstance(item, tuple) and len(item) == 2:
                    msg, level = item
                else:
                    msg, level = str(item), "INFO"
                self.write(msg, level)
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def clear(self):
        self.txt.configure(state="normal")
        self.txt.delete(1.0, "end")
        self.txt.configure(state="disabled")

    def save_log(self):
        from tkinter.filedialog import asksaveasfilename
        path = asksaveasfilename(defaultextension=".log",
                                 filetypes=[("Log", "*.log"), ("Text", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.txt.get(1.0, "end"))

    def on_close(self):
        self.destroy()