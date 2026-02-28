# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

# 项目根目录
ROOT = Path(SPECDIR) / "adofai_ep"

block_cipher = None

# 要包含的数据文件
added_files = [
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "lang"), "lang"),
    (str(ROOT / "gui" / "locales"), "gui/locales"),
    (str(ROOT / "presets.json"), "."),
    (str(ROOT / "utils"), "utils"),
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT), str(ROOT.parent)],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'tkinter',
        'tkinterdnd2',
        'ttkbootstrap',
        'chardet',
        'json',
        're',
        'queue',
        'threading',
        'datetime',
        'pathlib',
        'enum',
        'functools',
        'i18n',
        'config',
        'processor',
        'toolbox',
        'widgets',
        'encoding',
        'debug_window',
        'preview_window',
        'toolbox_ui',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'wx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ADOFAI_Event_Processor_v4.4.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "app.ico"),
)
