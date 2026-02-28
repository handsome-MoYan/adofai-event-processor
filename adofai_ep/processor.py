# processor.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from enum import IntEnum
from functools import lru_cache
from typing import Iterable, List, Tuple

from config import Config   # 直接 import 当前包


class Mode(IntEnum):
    DELETE_ANY = 0
    EXTRACT_ANY = 1
    DELETE_ALL = 2
    EXTRACT_ALL = 3
    REPLACE_LINE = 4
    REPLACE_SUBSTRING = 5


class Processor:
    _cfg = Config()  # 单例

    # ---------- 编译缓存 ----------
    @staticmethod
    @lru_cache(maxsize=256)
    def _compile(patterns: Tuple[Tuple[str, Tuple[str, ...]], ...],
                 use_regex: bool, ignore_case: bool):
        flags = re.I if ignore_case else 0
        compiled = []
        for main, subs in patterns:
            main_pat = re.compile(main if use_regex else re.escape(main), flags)
            sub_pats = [re.compile(s if use_regex else re.escape(s), flags) for s in subs]
            compiled.append((main_pat, sub_pats))
        return compiled

    # ---------- 处理 ----------
    @staticmethod
    def process(lines: Iterable[str], mode: Mode, patterns: List[Tuple[str, List[str]]],
                use_regex: bool, ignore_case: bool, replacement: str = "") -> List[str]:
        c_patterns = Processor._compile(tuple((m, tuple(s)) for m, s in patterns),
                                        use_regex, ignore_case)
        try:
            replacement = replacement.encode("utf-8").decode("unicode_escape")
        except UnicodeDecodeError as ex:
            replacement = replacement

        out = []
        for line in lines:
            line = line.rstrip("\n")
            any_ok = all_ok = False
            for main_pat, sub_pats in c_patterns:
                if main_pat.search(line) and all(p.search(line) for p in sub_pats):
                    any_ok = True
                    all_ok = True
                    break

            if mode == Mode.DELETE_ANY:
                keep = not any_ok
            elif mode == Mode.EXTRACT_ANY:
                keep = any_ok
            elif mode == Mode.DELETE_ALL:
                keep = not all_ok
            elif mode == Mode.EXTRACT_ALL:
                keep = all_ok
            elif mode == Mode.REPLACE_LINE:
                line = replacement if any_ok else line
                keep = True
            elif mode == Mode.REPLACE_SUBSTRING:
                for main_pat, sub_pats in c_patterns:
                    line = main_pat.sub(replacement, line)
                    for sub in sub_pats:
                        line = sub.sub(replacement, line)
                keep = True
            else:
                keep = True

            if keep:
                out.append(line + "\n")
        return out