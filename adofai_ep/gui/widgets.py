# widgets.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tkinter as tk
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tkinter import ttk


class CheckTree(ttk.Treeview):
    """支持单选/多选的树，复用原 CheckTree 逻辑"""
    def __init__(self, master, **kw):
        super().__init__(master, show="tree", columns=("value",), displaycolumns=(),
                         selectmode="extended", **kw)
        self.bind("<ButtonRelease-1>", self.on_click)

    def on_click(self, event):
        iid = self.identify_row(event.y)
        if iid:
            tags = list(self.item(iid, "tags") or [])
            if "selected" in tags:
                tags.remove("selected")
                tags.append("unchecked")
            else:
                tags = ["selected"]
            self.item(iid, tags=tags)
            # 视觉上高亮
            self.tag_configure("selected", foreground="white", background="#0078D7")
            self.tag_configure("unchecked", foreground="black", background="white")