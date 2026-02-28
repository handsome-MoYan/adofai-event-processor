    # i18n.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import sys
from json import JSONDecodeError

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from pathlib import Path
from typing import Dict

LANG_DIR = Path(__file__).parent / "lang"


class I18n:
    _inst = None

    def __new__(cls):
        if cls._inst is None:
            cls._inst = super().__new__(cls)
            cls._inst._load_available()
        return cls._inst

    def _load_available(self):
        self.available = [p.stem for p in LANG_DIR.glob("*.json") if p.name != "lang.json"]

    def set_lang(self, lang: str):
        # 直接 import 当前目录下的 config
        from config import Config
        Config().set("lang", lang)

    def tr(self) -> Dict[str, any]:
        from config import Config
        lang = Config().get("lang", "en_US")
        try:
            with open(LANG_DIR / f"{lang}.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, JSONDecodeError):
            try:
                with open(LANG_DIR / "en_US.json", "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}