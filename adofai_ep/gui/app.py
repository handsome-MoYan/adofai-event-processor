# gui/app.py
# !/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADOFAI Event Processor v4.4.0 for v2.9.8
整合工具箱：智能清理、VFX制作、预设组管理
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from json import JSONDecodeError

import webbrowser

import ttkbootstrap as tb
from tkinterdnd2 import DND_FILES, TkinterDnD

from config import Config, ENCODINGS
from i18n import I18n
from processor import Mode, Processor
from utils.encoding import detect_encoding, is_text_file
from .debug_window import DebugWindow
from .widgets import CheckTree
import processor
from .preview_window import PreviewWindow
from .toolbox_ui import ToolboxUI

import queue

log_q = queue.Queue()


def _load_presets() -> dict:
    p = Path(__file__).parent.parent / "presets.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")) or {}
    except (FileNotFoundError, JSONDecodeError):
        return {}


cfg = Config()
i18n = I18n()


class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("ADOFAI Event Processor v4.4.0")
        self.geometry("900x750")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        try:
            icon_path = Path(__file__).resolve().parent.parent / "assets" / "app.ico"
            if icon_path.exists():
                self.iconbitmap(str(icon_path))
        except Exception as e:
            pass

        self.turbo = tk.BooleanVar(value=cfg.get("turbo", False))
        self.console_var = tk.BooleanVar(value=cfg.get("console", True))
        self.log_var = tk.BooleanVar(value=cfg.get("save_log", False))
        self.chk_presets = tk.BooleanVar(value=cfg.get("check_presets_on_startup", True))

        self._worker_running = False
        self._thread = None

        # === 调试/日志/ turbo 相关变量 ===
        self.debug = tk.BooleanVar(value=False)
        self.turbo = tk.BooleanVar(value=cfg.get("turbo", False))
        self.console_var = tk.BooleanVar(value=cfg.get("console", True))
        self.log_var = tk.BooleanVar(value=cfg.get("save_log", False))
        self.chk_presets = tk.BooleanVar(value=cfg.get("check_presets_on_startup", True))
        self.log_q = queue.Queue()
        self.debug_win: DebugWindow | None = None
        self.preview_window = None
        self.toolbox_ui = None

        # 拖拽
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self.on_drop)

        self.build_ui()

        self.create_menu()
        self.load_cfg()

        self.bind_all("<Control-o>", lambda e: self.browse_in())
        self.bind_all("<Control-s>", lambda e: self.browse_out())
        self.bind_all("<Control-Shift-s>", lambda e: self.auto_out())
        self.bind_all("<Control-p>", lambda e: self.preview_process())
        self.bind_all("<Control-Shift-p>", lambda e: self.run_process())
        self.bind_all("<Control-Return>", lambda e: self.add_main())
        self.bind_all("<Shift-Return>", lambda e: self.add_sub())
        self.bind_all("<Control-Delete>", lambda e: self.clear_tree())
        self.bind_all("<Delete>", lambda e: self.delete_sel_safe())
        self.bind_all("<F12>", lambda e: self.toggle_debug())
        self.bind_all("<Control-f>", lambda e: self.focus_search() if self.preview_window else None)

        if cfg.get("check_presets_on_startup", True):
            from pathlib import Path
            import json
            log_q.put(("========== presets.json 诊断 ==========", "INFO"))
            log_q.put((f"文件是否存在：{Path('presets.json').exists()}", "INFO"))
            try:
                p = json.loads(Path("presets.json").read_text("utf-8"))
                log_q.put((f"预设键列表：{list(p.keys())}", "INFO"))
            except Exception as e:
                log_q.put((f"读取失败：{e}", "ERROR"))
            log_q.put(("=======================================", "INFO"))

        show_debug = "--debug" in sys.argv

        if show_debug:
            self.debug_win = DebugWindow(self, self.log_q)

        raw_theme = {v: k for k, v in self.theme_map.items()}.get(cfg.get("theme"), cfg.get("theme"))
        self.after(0, lambda: tb.Style().theme_use(raw_theme))

    def create_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=i18n.tr().get("help", "Help"), menu=help_menu)
        help_menu.add_command(label=i18n.tr().get("usage", "Usage"),
                              command=self.show_help)
        help_menu.add_command(label=i18n.tr().get("debug", "Debug Window"),
                              command=self.toggle_debug)

        # 添加工具箱菜单
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=i18n.tr().get("toolbox", "Toolbox"), menu=tools_menu)
        tools_menu.add_command(label=i18n.tr().get("smart_cleanup", "Smart Cleanup"), command=self.show_toolbox_cleanup)
        tools_menu.add_command(label=i18n.tr().get("vfx_maker", "VFX Maker"), command=self.show_toolbox_vfx)
        tools_menu.add_command(label=i18n.tr().get("preset_groups", "Preset Groups"), command=self.show_toolbox_presets)

    def show_help(self):
        """根据当前语言打开对应 HTML 帮助"""
        lang = cfg.get("lang", "en")

        # 特殊处理喵喵语，其他语言取前半部分
        if lang == "zh_CN_Nya":
            lang_code = "nya"
        else:
            lang_code = lang.split("_")[0]

        help_file = Path(__file__).parent / "locales" / f"help_{lang_code}.html"

        # 若文件不存在，回退到英文
        if not help_file.exists():
            help_file = Path(__file__).parent / "locales" / "help_en.html"

        webbrowser.open(help_file.resolve().as_uri())

    def toggle_debug(self):
        if self.debug_win is None or not self.debug_win.winfo_exists():
            self.debug_win = DebugWindow(self, self.log_q)
        else:
            self.debug_win.deiconify()

    def show_toolbox_cleanup(self):
        """显示工具箱清理标签页"""
        if self.toolbox_ui:
            self.toolbox_ui.notebook.select(0)
            self.main_notebook.select(1)

    def show_toolbox_vfx(self):
        """显示工具箱VFX制作标签页"""
        if self.toolbox_ui:
            self.toolbox_ui.notebook.select(1)
            self.main_notebook.select(1)

    def show_toolbox_presets(self):
        """显示工具箱预设组标签页"""
        if self.toolbox_ui:
            self.toolbox_ui.notebook.select(2)
            self.main_notebook.select(1)

    def build_ui(self):
        # 创建主Notebook以组织界面
        self.main_notebook = ttk.Notebook(self)
        self.main_notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # 主处理标签页
        main_tab = ttk.Frame(self.main_notebook)
        self.main_notebook.add(main_tab, text=i18n.tr().get("event_processing", "Event Processing"))

        # 工具箱标签页
        toolbox_tab = ttk.Frame(self.main_notebook)
        self.main_notebook.add(toolbox_tab, text=i18n.tr().get("toolbox", "Toolbox"))

        # 构建主处理界面
        self._build_main_tab(main_tab)

        # 构建工具箱界面
        self._build_toolbox_tab(toolbox_tab)

        status = ttk.Frame(self)
        status.pack(fill="x", side="bottom", padx=10, pady=5)
        self.status_lbl = ttk.Label(status, text=i18n.tr().get("ready", "Ready"))
        self.status_lbl.pack(side="left")
        self.progress = ttk.Progressbar(status, mode="determinate")
        self.progress.pack(fill="x", expand=True, side="right")

    def _build_main_tab(self, parent):
        """构建主处理标签页"""
        # 顶部栏
        top = ttk.Frame(parent)
        top.pack(fill="x", padx=10, pady=5)

        # 语言
        self.lang_cb = ttk.Combobox(top, state="readonly", width=10,
                                    values=i18n.available)
        self.lang_cb.set(cfg.get("lang"))
        self.lang_cb.bind("<<ComboboxSelected>>", self.change_lang)
        self.lang_cb.pack(side="right")
        ttk.Label(top, text=i18n.tr().get("language", "Language") + ":").pack(side="right", padx=5)

        # 主题
        themes_raw = list(tb.Style().theme_names())
        self.theme_map = {t: i18n.tr().get("themes", {}).get(t, t) for t in themes_raw}
        self.theme_cb = ttk.Combobox(top, state="readonly", width=12,
                                     values=list(self.theme_map.values()))
        self.theme_cb.set(self.theme_map[cfg.get("theme")])
        self.theme_cb.bind("<<ComboboxSelected>>", self.change_theme)
        self.theme_cb.pack(side="right")
        ttk.Label(top, text=i18n.tr().get("theme", "Theme") + ":").pack(side="right", padx=5)

        # 输入
        ttk.Label(parent, text=i18n.tr().get("input_file", "Input file:")).pack(anchor="w", padx=10)
        self.in_ent = ttk.Entry(parent)
        self.in_ent.pack(fill="x", padx=10)
        ttk.Button(parent, text=i18n.tr().get("browse", "Browse…"),
                   command=self.browse_in).pack(anchor="e", padx=10)

        # 输出目录
        ttk.Label(parent, text=i18n.tr().get("output_dir", "Output directory:")).pack(anchor="w", padx=10)
        out_bar = ttk.Frame(parent)
        out_bar.pack(fill="x", padx=10)
        self.out_ent = ttk.Entry(out_bar)
        self.out_ent.pack(side="left", fill="x", expand=True)
        ttk.Button(out_bar, text=i18n.tr().get("browse", "Browse…"),
                   command=self.browse_out).pack(side="left")
        ttk.Button(out_bar, text=i18n.tr().get("auto_fill", "Auto fill"),
                   command=self.auto_out).pack(side="left", padx=5)

        # 输出文件名
        ttk.Label(parent, text=i18n.tr().get("output_filename", "Output filename (no ext):")).pack(anchor="w", padx=10)
        self.name_ent = ttk.Entry(parent)
        self.name_ent.pack(fill="x", padx=10)

        # 编码
        enc_bar = ttk.Frame(parent)
        enc_bar.pack(fill="x", padx=10, pady=2)
        ttk.Label(enc_bar, text=i18n.tr().get("encoding", "Encoding") + ":").pack(side="left")
        self.enc_cb = ttk.Combobox(enc_bar, state="readonly", width=12,
                                   values=ENCODINGS)
        self.enc_cb.set(cfg.get("encoding"))
        self.enc_cb.pack(side="left", padx=5)
        ttk.Button(enc_bar, text=i18n.tr().get("automatic_identification", "Automatic identification"),
                   command=self.auto_detect_encoding).pack(side="left", padx=5)

        preset_bar = ttk.Frame(parent)
        preset_bar.pack(fill=tk.X, padx=10, pady=5)

        self.preset_combo = ttk.Combobox(
            preset_bar, state="readonly", width=15
        )
        self.preset_combo["values"] = list(_load_presets().keys())
        self.preset_combo.set(i18n.tr().get("select_preset", "Select Preset"))
        self.preset_combo.pack(side=tk.LEFT, padx=5)

        self.sub_combo = ttk.Combobox(
            preset_bar, state="readonly", width=25
        )
        self.sub_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            preset_bar,
            text=i18n.tr().get("apply_preset_main", "Apply preset (main)"),
            command=self.apply_preset_main,
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            preset_bar,
            text=i18n.tr().get("apply_preset_sub", "Apply preset (sub)"),
            command=self.apply_preset_sub,
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            preset_bar,
            text=i18n.tr().get("apply_preset_group", "Apply Preset Group"),
            command=self.apply_preset_group_dialog,
            bootstyle="success-outline"
        ).pack(side=tk.LEFT, padx=5)

        self.preset_combo.bind("<<ComboboxSelected>>", self.on_preset_change)

        # 关键词树
        tree_frm = ttk.LabelFrame(parent, text=i18n.tr().get("keyword_filter", "Keyword/Regex filter"))
        tree_frm.pack(fill="both", expand=True, padx=10, pady=5)
        self.tree = CheckTree(tree_frm)
        self.tree.pack(fill="both", expand=True)
        btn_bar = ttk.Frame(tree_frm)
        btn_bar.pack(fill="x")
        ttk.Button(btn_bar, text=i18n.tr().get("add_main", "Add main"),
                   command=self.add_main).pack(side="left")
        ttk.Button(btn_bar, text=i18n.tr().get("add_sub", "Add sub"),
                   command=self.add_sub).pack(side="left")
        ttk.Button(btn_bar, text=i18n.tr().get("delete_sel", "Delete selected"),
                   command=self.delete_sel_safe).pack(side="left")
        ttk.Button(btn_bar, text=i18n.tr().get("clear", "Clear"),
                   command=self.clear_tree).pack(side="left")

        # 模式
        mode_bar = ttk.Frame(parent)
        mode_bar.pack(fill="x", padx=10, pady=5)

        modes = i18n.tr().get("mode", [])
        if not modes:  # 保底
            modes = [
                "Delete lines containing any keyword",
                "Extract lines containing any keyword",
                "Delete lines containing all keywords",
                "Extract lines containing all keywords",
                "Modify lines containing any keyword",
                "Replace substring in matched lines"
            ]
        self.mode_cb = ttk.Combobox(mode_bar, state="readonly", width=35, values=modes)
        idx = cfg.get("mode_idx", 0)
        idx = max(0, min(idx, len(modes) - 1))
        self.mode_cb.current(idx)
        self.mode_cb.pack(side="left")

        # 选项
        self.use_regex = tk.BooleanVar(value=cfg.get("use_regex", False))
        self.ignore_case = tk.BooleanVar(value=cfg.get("ignore_case", False))
        self.all_fmt = tk.BooleanVar(value=cfg.get("all_formats", False))
        self.turbo = tk.BooleanVar(value=cfg.get("turbo", False))
        ttk.Checkbutton(mode_bar, text=i18n.tr().get("regex", "Regex"),
                        variable=self.use_regex).pack(side="left", padx=5)
        ttk.Checkbutton(mode_bar, text=i18n.tr().get("ignore_case", "Ignore case"),
                        variable=self.ignore_case).pack(side="left", padx=5)

        # 替换
        ttk.Label(mode_bar, text=i18n.tr().get("replace_with", "Replace with:")).pack(side="left", padx=5)
        self.repl_ent = ttk.Entry(mode_bar, width=25)
        self.repl_ent.insert(0, cfg.get("replacement", ""))
        self.repl_ent.pack(side="left")

        # 底部
        bot = ttk.Frame(parent)
        bot.pack(fill="x", padx=10, pady=5)
        ttk.Checkbutton(bot, text=i18n.tr().get("turbo", "Turbo"), variable=self.turbo)
        ttk.Button(bot, text=i18n.tr().get("start", "Start process"),
                   command=self.run_process).pack(side="right")
        ttk.Button(bot, text=i18n.tr().get("preview", "Preview"),
                   command=self.preview_process).pack(side="right", padx=5)
        log_bar = ttk.Frame(parent)
        log_bar.pack(fill="x", padx=10, pady=5)
        ttk.Checkbutton(log_bar, text=i18n.tr().get("debug", "Debug"), variable=self.debug).pack(side="left")
        ttk.Checkbutton(log_bar, text=i18n.tr().get("save_log", "Save log"), variable=self.log_var).pack(side="left")
        ttk.Checkbutton(log_bar, text=i18n.tr().get("console", "Console output"), variable=self.console_var).pack(
            side="left")
        ttk.Checkbutton(log_bar, text=i18n.tr().get("turbo", "Turbo"), variable=self.turbo).pack(side="left", padx=5)
        ttk.Checkbutton(log_bar, text=i18n.tr().get("check_presets_on_startup", "Check presets on startup"),
                        variable=self.chk_presets).pack(side="left")

    def _build_toolbox_tab(self, parent):
        """构建工具箱标签页"""
        self.toolbox_ui = ToolboxUI(
            parent,
            log_queue=self.log_q,
            tree_widget=self.tree,
            preset_loader=_load_presets
        )

    def apply_preset_group_dialog(self):
        """弹出对话框应用预设组"""
        dialog = tk.Toplevel(self)
        dialog.title(i18n.tr().get("apply_preset_group", "Apply Preset Group"))
        dialog.geometry("400x300")
        dialog.transient(self)
        dialog.grab_set()

        # 选择预设组
        ttk.Label(dialog, text=i18n.tr().get("select_preset_group", "Select Preset Group:")).pack(pady=5)
        group_var = tk.StringVar()
        combo = ttk.Combobox(dialog, state="readonly", textvariable=group_var, width=30)
        combo["values"] = list(_load_presets().keys())
        combo.pack(pady=5)

        # 选项
        append_var = tk.BooleanVar(value=True)
        ttk.Radiobutton(dialog, text=i18n.tr().get("append_to_tree", "Append to existing tree"),
                        variable=append_var, value=True).pack()
        ttk.Radiobutton(dialog, text=i18n.tr().get("replace_tree", "Replace existing tree"),
                        variable=append_var, value=False).pack()

        # 预览文本
        preview_text = tk.Text(dialog, height=10, wrap=tk.WORD, state="disabled")
        preview_text.pack(fill="both", expand=True, padx=5, pady=5)

        def update_preview(*args):
            group = group_var.get()
            if not group:
                return
            presets = _load_presets()
            if group not in presets:
                return
            preview_text.config(state="normal")
            preview_text.delete(1.0, tk.END)
            data = presets[group]
            text = f"【{group}】{i18n.tr().get('contains', 'contains')} {len(data)} {i18n.tr().get('sub_presets', 'sub-presets')}:\n"
            for name, values in data.items():
                count = len(values) if isinstance(values, list) else 1
                text += f"  • {name}: {count} {i18n.tr().get('items', 'items')}\n"
            preview_text.insert(1.0, text)
            preview_text.config(state="disabled")

        group_var.trace_add("write", update_preview)
        combo.bind("<<ComboboxSelected>>", lambda e: update_preview())

        def do_apply():
            group = group_var.get()
            if not group:
                messagebox.showwarning(i18n.tr().get("hint", "Hint"),
                                       i18n.tr().get("please_select_preset_group",
                                                     "Please select a preset group first"),
                                       parent=dialog)
                return
            presets = _load_presets()
            if group not in presets:
                messagebox.showerror(i18n.tr().get("error", "Error"),
                                     i18n.tr().get("preset_group_not_exist", "Preset group does not exist"),
                                     parent=dialog)
                return
            if not append_var.get():
                self.clear_tree()
            # 应用预设组
            from .toolbox import ToolboxEngine
            engine = ToolboxEngine(self.log_q)
            success = engine.apply_preset_group(presets[group], self.tree, append=append_var.get())
            if success:
                messagebox.showinfo(i18n.tr().get("success", "Success"),
                                    f"{i18n.tr().get('applied_preset_group', 'Applied preset group')}: {group}",
                                    parent=dialog)
                dialog.destroy()

        ttk.Button(dialog, text=i18n.tr().get("apply", "Apply"),
                   command=do_apply, bootstyle="success").pack(pady=10)

    def browse_in(self):
        f = filedialog.askopenfilename(
            title=i18n.tr().get("input_file", "Input file:"),
            filetypes=[
                ("ADOFAI level", "*.adofai"),
                ("Text", "*.txt"),
                ("All", "*.*")
            ])
        if f:
            if not is_text_file(Path(f)):
                messagebox.showerror(
                    i18n.tr().get("format_error", "Format Error"),
                    i18n.tr().get("select_text_file", "Please select a text file (.adofai / .txt etc.)")
                )
                return
            self.in_ent.delete(0, "end")
            self.in_ent.insert(0, f)
            self.auto_out()
            enc = detect_encoding(Path(f))
            if enc and enc.lower() in (e.lower() for e in ENCODINGS):
                self.enc_cb.set(enc.lower())

    def browse_out(self):
        d = filedialog.askdirectory()
        if d:
            self.out_ent.delete(0, "end")
            self.out_ent.insert(0, d)

    def auto_out(self):
        p = self.in_ent.get().strip()
        if p:
            self.out_ent.delete(0, "end")
            self.out_ent.insert(0, str(Path(p).parent))

    def auto_detect_encoding(self):
        enc = detect_encoding(Path(self.in_ent.get()))
        if enc:
            self.enc_cb.set(enc.lower())
        else:
            messagebox.showinfo(
                i18n.tr().get("hint", "Hint"),
                i18n.tr().get("encoding_not_detected", "Could not detect a valid encoding.")
            )

    def preview_process(self):
        """预览处理结果"""
        try:
            in_file = Path(self.in_ent.get().strip())
            enc = self.enc_cb.get()

            if not in_file.is_file():
                messagebox.showerror(
                    i18n.tr().get("error", "Error"),
                    i18n.tr().get("select_valid_input", "Please select a valid input file first.")
                )
                return

            if not is_text_file(in_file):
                messagebox.showerror(i18n.tr().get("error", "Error"),
                                     i18n.tr().get("not_text_file", "Input file is not a text file"))
                return

            # 读取文件
            lines, enc_used = self._read_lines(in_file, enc, self.all_fmt.get())

            if enc_used != enc:
                self.enc_cb.set(enc_used)

            if not lines:
                messagebox.showwarning(
                    i18n.tr().get("warning", "Warning"),
                    i18n.tr().get("file_empty", "File is empty.")
                )
                return

            # 获取处理参数
            mode_idx = self.mode_cb.current()
            mode = Mode(mode_idx)
            patterns = [(self.tree.item(iid, "text"),
                         [self.tree.item(c, "text") for c in self.tree.get_children(iid)])
                        for iid in self.tree.get_children()]

            repl = self.repl_ent.get()
            use_regex = self.use_regex.get()
            ignore_case = self.ignore_case.get()

            self.preview_window = PreviewWindow(
                parent=self,
                lines=lines,
                mode=mode,
                patterns=patterns,
                use_regex=use_regex,
                ignore_case=ignore_case,
                repl=repl,
                tree_widget=self.tree
            )

        except Exception as e:
            messagebox.showerror(i18n.tr().get("error", "Error"),
                                 f"{i18n.tr().get('preview_failed', 'Preview failed')}: {str(e)}")

    def add_main(self):
        from ttkbootstrap.dialogs import Querybox
        txt = Querybox.get_string(
            prompt=i18n.tr().get("enter_keyword", "Enter keyword/regex:"),
            title=i18n.tr().get("add_main", "Add main"))
        if txt:
            self.tree.insert("", "end", text=txt)

    def add_sub(self):
        sel = self.tree.selection()
        if sel and not self.tree.parent(sel[0]):
            from ttkbootstrap.dialogs import Querybox
            txt = Querybox.get_string(
                prompt=i18n.tr().get("enter_sub_keyword", "Enter sub keyword/regex:"),
                title=i18n.tr().get("add_sub", "Add sub"))
            if txt:
                self.tree.insert(sel[0], "end", text=txt)

    def delete_sel_safe(self):
        """安全地删除选中项（修复Delete键错误）"""
        try:
            selection = self.tree.selection()
            if not selection:
                return  # 没有选中项，直接返回
            for iid in selection:
                try:
                    self.tree.delete(iid)
                except tk.TclError:
                    # 项目可能已被删除，忽略错误
                    pass
        except Exception as e:
            # 捕获所有其他错误
            print(f"Delete error (safe ignore): {e}")

    def clear_tree(self):
        self.tree.delete(*self.tree.get_children())

    def on_preset_change(self, ev=None):
        key = self.preset_combo.get()
        if key in _load_presets():
            self.sub_combo["values"] = list(_load_presets()[key].keys())
            self.sub_combo.current(0)

    def apply_preset_main(self):
        key = self.preset_combo.get()
        sub = self.sub_combo.get()
        if key not in _load_presets() or sub not in _load_presets()[key]:
            messagebox.showerror(
                i18n.tr().get("error", "Error"),
                i18n.tr().get("select_valid_preset", "Please select a valid preset first.")
            )
            return
        values = _load_presets()[key][sub]
        if not isinstance(values, list):
            values = [values]
        for v in values:
            self.tree.insert("", tk.END, text=v)

    def apply_preset_sub(self):
        key = self.preset_combo.get()
        sub = self.sub_combo.get()
        if key not in _load_presets() or sub not in _load_presets()[key]:
            messagebox.showerror(
                i18n.tr().get("error", "Error"),
                i18n.tr().get("select_valid_preset", "Please select a valid preset first.")
            )
            return
        values = _load_presets()[key][sub]
        if not isinstance(values, list):
            values = [values]
        sel = self.tree.selection()
        if not sel:
            messagebox.showerror(i18n.tr().get("error", "Error"),
                                 i18n.tr().get("select_main_node", "Please select a main node first"))
            return
        parent = sel[0]
        if self.tree.parent(parent):
            parent = self.tree.parent(parent)
        for v in values:
            self.tree.insert(parent, tk.END, text=v)

    @staticmethod
    def _read_lines(path: Path, enc: str, try_detect: bool):
        """按优先级尝试读取文件，返回 (lines, used_encoding)"""
        try:
            with path.open("r", encoding=enc) as f:
                return f.readlines(), enc
        except UnicodeDecodeError:
            pass

        if try_detect:
            det_enc = detect_encoding(path)
            if det_enc and det_enc.lower() != enc.lower():
                try:
                    with path.open("r", encoding=det_enc) as f:
                        return f.readlines(), det_enc
                except UnicodeDecodeError:
                    pass

        with path.open("r", encoding="utf-8", errors="replace") as f:
            return f.readlines(), "utf-8"

    def run_process(self):
        if self._worker_running:
            messagebox.showinfo("Busy", i18n.tr().get("task_running", "A task is already running"))
            return

        try:
            in_file = Path(self.in_ent.get().strip())
            out_dir = Path(self.out_ent.get().strip())
            enc = self.enc_cb.get()
            mode_idx = self.mode_cb.current()
            mode = Mode(mode_idx)
            patterns = [(self.tree.item(iid, "text"),
                         [self.tree.item(c, "text") for c in self.tree.get_children(iid)])
                        for iid in self.tree.get_children()]
            repl = self.repl_ent.get()
            turbo = self.turbo.get()

            if not in_file.is_file():
                messagebox.showerror(i18n.tr().get("error", "Error"),
                                     i18n.tr().get("input_not_exist", "Input file does not exist"))
                return
            if not is_text_file(in_file):
                messagebox.showerror(i18n.tr().get("error", "Error"),
                                     i18n.tr().get("not_text_file", "Input file is not a text file"))
                return
            if not out_dir.is_dir():
                messagebox.showerror(i18n.tr().get("error", "Error"),
                                     i18n.tr().get("output_not_exist", "Output directory does not exist"))
                return

            # 生成文件名
            stem = self.name_ent.get().strip() or in_file.stem + "_new"
            out_file = out_dir / f"{stem}{in_file.suffix}"
            counter = 1
            while out_file.exists():
                out_file = out_dir / f"{stem}({counter}){in_file.suffix}"
                counter += 1

            # 读取文件
            lines, enc_used = self._read_lines(in_file, enc, self.all_fmt.get())

            if in_file.stat().st_size == 0:
                messagebox.showwarning(i18n.tr().get("warning", "Warning"),
                                       i18n.tr().get("file_empty", "File is empty"))
                return

            # 如果编码被自动切换，回显到界面
            if enc_used != enc:
                self.enc_cb.set(enc_used)
        except Exception as e:
            messagebox.showerror(i18n.tr().get("error", "Error"),
                                 f"{i18n.tr().get('read_failed', 'Read failed')}: {str(e)}")
            return

        self._worker_running = True
        self._thread = threading.Thread(
            target=self.worker,
            args=(lines, out_file, mode, patterns,
                  self.use_regex.get(), self.ignore_case.get(), repl, turbo),
            daemon=False
        )
        self._thread.start()

        if not turbo:
            self.after(100, self.poll_progress)

    def worker(self, lines, out_file, mode, patterns, use_regex, ignore_case, repl, turbo):
        try:
            total = len(lines)
            if total == 0:
                # 空文件直接完成
                open(out_file, 'w', encoding='utf-8').close()
                self.log_q.put(("done", str(out_file)))
                return

            batch = max(1, total // 100)

            with open(out_file, "w", encoding="utf-8") as f:
                for i in range(0, total, batch):
                    chunk = lines[i: i + batch]
                    processed_chunk = Processor.process(
                        chunk, mode, patterns, use_regex, ignore_case, repl
                    )
                    f.writelines(processed_chunk)

                    # 非 turbo 模式实时更新百分比
                    if not turbo:
                        percent = int(min(i + len(chunk), total) / total * 100)
                        self.log_q.put(percent)

            if not turbo:
                self.log_q.put(100)
            self.log_q.put(("done", str(out_file)))

        except Exception as e:
            self.log_q.put(("error", str(e)))
        finally:
            self._worker_running = False

    def poll_progress(self):
        try:
            val = self.log_q.get_nowait()
            if isinstance(val, tuple):
                if val[0] == "done":
                    self.on_done(val[1])
                    return
                elif val[0] == "error":
                    self.on_error(val[1])
                    return
            else:
                self.progress.config(value=val)
        except queue.Empty:
            pass
        self.after(100, self.poll_progress)

    def on_done(self, path):
        self.status_lbl.config(text=i18n.tr().get("done", "Done"))
        self.progress.config(value=0)
        if cfg.get("turbo"):
            self.progress.pack(fill="x", expand=True, side="right")
        hist = cfg.load_history()
        hist.append({
            "timestamp": datetime.now().isoformat(),
            "in": str(self.in_ent.get()),
            "out_dir": str(self.out_ent.get()),
            "encoding": self.enc_cb.get(),
            "mode": self.mode_cb.current(),
            "patterns": [(self.tree.item(iid, "text"),
                          [self.tree.item(c, "text") for c in self.tree.get_children(iid)])
                         for iid in self.tree.get_children()],
            "turbo": self.turbo.get()
        })
        cfg.save_history(hist)
        if not self.progress.winfo_ismapped():
            self.progress.pack(fill="x", expand=True, side="right")

    def on_error(self, msg):
        self.status_lbl.config(text=i18n.tr().get("ready", "Ready"))
        self.progress.config(value=0)
        if cfg.get("turbo"):
            self.progress.pack(fill="x", expand=True, side="right")
        messagebox.showerror(i18n.tr().get("error", "Error"), msg)
        if not self.progress.winfo_ismapped():
            self.progress.pack(fill="x", expand=True, side="right")

    def change_lang(self, _=None):
        new = self.lang_cb.get()
        if new != cfg.get("lang"):
            cfg.set("lang", new)
            # 重启
            import subprocess, sys
            subprocess.Popen([sys.executable, *sys.argv])
            sys.exit(0)

    def change_theme(self, _=None):
        raw = {v: k for k, v in self.theme_map.items()}[self.theme_cb.get()]
        cfg.set("theme", raw)
        tb.Style().theme_use(raw)

    def load_cfg(self):
        self.theme_cb.set(self.theme_map[cfg.get("theme")])
        self.lang_cb.set(cfg.get("lang"))
        self.enc_cb.set(cfg.get("encoding"))
        self.turbo.set(cfg.get("turbo"))
        self.mode_cb.current(cfg.get("mode_idx", 0))
        self.use_regex.set(cfg.get("use_regex", False))
        self.ignore_case.set(cfg.get("ignore_case", False))
        self.all_fmt.set(cfg.get("all_formats", False))
        self.repl_ent.delete(0, "end")
        self.repl_ent.insert(0, cfg.get("replacement", ""))

        self.title(i18n.tr().get("app_title", "ADOFAI Event Processor v4.4.0"))

    def on_close(self):
        if getattr(self, '_thread', None) and self._thread.is_alive():
            if not messagebox.askokcancel(i18n.tr().get("confirm_exit", "Confirm Exit"),
                                          i18n.tr().get("task_running_exit", "Task is still running, force exit?")):
                return
            self._thread.join(timeout=3.0)

        # 保存配置
        cfg.set("encoding", self.enc_cb.get())
        cfg.set("turbo", self.turbo.get())
        cfg.set("mode_idx", self.mode_cb.current())
        cfg.set("use_regex", self.use_regex.get())
        cfg.set("ignore_case", self.ignore_case.get())
        cfg.set("all_formats", self.all_fmt.get())
        cfg.set("replacement", self.repl_ent.get())
        cfg.set("console", self.console_var.get())
        cfg.set("save_log", self.log_var.get())
        cfg.set("check_presets_on_startup", self.chk_presets.get())
        cfg.set("debug", self.debug.get())
        self.destroy()

    def on_drop(self, event):
        files = self.tk.splitlist(event.data)
        if files:
            self.in_ent.delete(0, "end")
            self.in_ent.insert(0, files[0])
            self.auto_out()
            enc = detect_encoding(Path(files[0]))
            if enc and enc.lower() in (e.lower() for e in ENCODINGS):
                self.enc_cb.set(enc.lower())


def start_gui():
    import tkinter as tk
    from .app import App
    app = App()
    app.mainloop()
