# utils/encoding.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pathlib import Path
from typing import Optional

try:
    import chardet
except ImportError:
    chardet = None

def detect_encoding(file_path: Path) -> Optional[str]:
    if chardet is None:
        return None
    try:
        with open(file_path, "rb") as f:
            raw = f.read(min(100_000, os.path.getsize(file_path)))
        res = chardet.detect(raw) or {}
        return res.get("encoding")
    except Exception:
        return None

def is_text_file(path: Path, sample_size: int = 32_768) -> bool:
    """
    快速判断文件是否为文本。
    返回 True 认为是文本，False 认为是二进制。
    """
    try:
        data = path.read_bytes()[:sample_size]
    except OSError:
        return False

    # 1. 出现空字节直接判为二进制
    if b'\x00' in data:
        return False

    # 2. 控制字符比例过高判为二进制
    control = sum(1 for b in data if b < 32 and b not in (9, 10, 13))
    if control / max(len(data), 1) > 0.3:
        return False

    # 3. 尝试用 utf-8 解码
    try:
        data.decode('utf-8')
        return True
    except UnicodeDecodeError:
        return False