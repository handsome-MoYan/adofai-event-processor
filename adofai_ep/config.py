# config.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import sys
# 让本文件独立测试也能用
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import threading
from json import JSONDecodeError

_FILE_LOCK = threading.Lock()

from pathlib import Path
from typing import Any, Dict

CONFIG_FILE = Path(__file__).parent / "adofai_ep_config.json"
HISTORY_FILE = Path(__file__).parent / "adofai_ep_history.json"
ENCODINGS = ["utf-8-sig", "utf-8", "gbk", "shift_jis", "ascii"]  # GUI 下拉框


class Config:
    """线程安全的单例配置"""
    _instance = None
    _lock = __import__('threading').Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._cfg = {}
                cls._instance.load()
        return cls._instance

    # ---------- 当前配置 ----------
    def get(self, key: str, default=None) -> Any:
        return self._cfg.get(key, default)

    def set(self, key: str, value: Any):
        self._cfg[key] = value
        self.save()

    # ---------- 持久化 ----------
    def load(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                self._cfg = json.load(f)
        except (FileNotFoundError, JSONDecodeError):
            self._cfg = {}
        self._cfg.setdefault("encoding", "utf-8-sig")
        self._cfg.setdefault("turbo", False)
        self._cfg.setdefault("theme", "cosmo")
        self._cfg.setdefault("lang", "en_US")
        self._cfg.setdefault("max_history", 10)
        self._cfg.setdefault("console", True)
        self._cfg.setdefault("save_log", False)
        self._cfg.setdefault("check_presets_on_startup", True)
        self._cfg.setdefault("debug_startup", False)
        self._cfg.setdefault("preview_word_wrap", True)
        self._cfg.setdefault("preview_max_lines", 1000)
        self._cfg.setdefault("preview_max_chars", 50000)
        self._cfg.setdefault("preview_case_sensitive", False)

    def save(self):
        with _FILE_LOCK:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._cfg, f, ensure_ascii=False, indent=2)

    # ---------- 历史 ----------
    def load_history(self) -> list[Dict]:
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def save_history(self, records: list[Dict]):
        max_h = self.get("max_history", 10)
        records = records[-max_h:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)