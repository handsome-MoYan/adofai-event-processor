#!/usr/bin/env python3
import sys, json, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import wx
from pathlib import Path
from processor import Mode, Processor

def main():
    # 通过临时 JSON 文件传参
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        data = json.load(f)

    lines = data['lines']
    mode = Mode(data['mode'])
    patterns = data['patterns']
    use_regex = data['use_regex']
    ignore_case = data['ignore_case']
    repl = data['repl']

    app = wx.App(False)
    from preview_window_wx import PreviewFrame
    PreviewFrame(None, lines, mode, patterns, use_regex, ignore_case, repl)
    app.MainLoop()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python -m gui.preview_standalone <json_path>")
        input("按回车退出……")
        sys.exit(1)
    main()