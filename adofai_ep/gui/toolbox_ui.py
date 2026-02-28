import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from typing import Callable
import threading
import queue
import datetime
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from .toolbox import ToolboxEngine
from i18n import I18n


class ToolboxUI:
    """工具箱UI管理器"""

    def __init__(self, parent: tk.Widget, log_queue: queue.Queue, tree_widget=None,
                 preset_loader: Callable = None):
        self.parent = parent
        self.log_q = log_queue
        self.tree_widget = tree_widget
        self.preset_loader = preset_loader
        self.engine = ToolboxEngine(log_queue)
        self.i18n = I18n()

        # 创建Notebook标签页
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # 创建各个标签页
        self._create_cleanup_tab()
        self._create_vfx_tab()
        self._create_preset_group_tab()

    def tr(self, key: str, default: str = "") -> str:
        """获取翻译文本"""
        return self.i18n.tr().get(key, default)

    def _create_cleanup_tab(self):
        """智能清理工具标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=self.tr("smart_cleanup", "智能清理"))

        file_frame = ttk.LabelFrame(tab, text=self.tr("file_selection", "文件选择"), padding=5)
        file_frame.pack(fill="x", padx=5, pady=5)

        self.cleanup_file_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.cleanup_file_var).pack(
            side="left", fill="x", expand=True, padx=5)
        ttk.Button(file_frame, text=self.tr("browse", "浏览..."), command=self._browse_cleanup_file).pack(side="left")
        ttk.Button(file_frame, text=self.tr("use_current_input", "使用当前输入"), command=self._use_current_file).pack(side="left", padx=5)

        backup_frame = ttk.LabelFrame(tab, text=self.tr("backup_path", "备份路径"), padding=5)
        backup_frame.pack(fill="x", padx=5, pady=5)

        self.cleanup_backup_var = tk.StringVar()
        ttk.Entry(backup_frame, textvariable=self.cleanup_backup_var).pack(
            side="left", fill="x", expand=True, padx=5)
        ttk.Button(backup_frame, text=self.tr("auto_fill", "自动填充"), command=self._auto_backup_path).pack(side="left")

        tool_frame = ttk.LabelFrame(tab, text=self.tr("cleanup_tools", "清理工具"), padding=5)
        tool_frame.pack(fill="x", padx=5, pady=5)

        self.cleanup_tool = tk.StringVar(value="empty_move")
        ttk.Radiobutton(tool_frame, text=self.tr("empty_move_cleaner", "空MoveDecorations清理 (EmptyMoveCleaner)"),
                        variable=self.cleanup_tool, value="empty_move").pack(anchor="w")
        ttk.Radiobutton(tool_frame, text=self.tr("unused_deco_cleaner", "未使用装饰物清理 (UnusedDecorationCleaner)"),
                        variable=self.cleanup_tool, value="unused_deco").pack(anchor="w")

        options_frame = ttk.LabelFrame(tab, text=self.tr("options", "选项"), padding=5)
        options_frame.pack(fill="x", padx=5, pady=5)

        self.cleanup_dry_run = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text=self.tr("dry_run_only", "仅预览（不实际删除）"),
                        variable=self.cleanup_dry_run).pack(anchor="w")

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill="x", padx=5, pady=10)
        ttk.Button(btn_frame, text=self.tr("start_cleanup", "开始清理"), command=self._run_cleanup).pack(side="left", padx=5)

    def _create_vfx_tab(self):
        """VFX制作标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=self.tr("vfx_maker", "VFX制作"))

        file_frame = ttk.LabelFrame(tab, text=self.tr("file_selection", "文件选择"), padding=5)
        file_frame.pack(fill="x", padx=5, pady=5)

        self.vfx_file_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.vfx_file_var).pack(
            side="left", fill="x", expand=True, padx=5)
        ttk.Button(file_frame, text=self.tr("browse", "浏览..."), command=self._browse_vfx_file).pack(side="left")
        ttk.Button(file_frame, text=self.tr("use_current_input", "使用当前输入"), command=self._use_current_file_vfx).pack(side="left", padx=5)

        mode_frame = ttk.LabelFrame(tab, text=self.tr("production_mode", "制作模式"), padding=5)
        mode_frame.pack(fill="x", padx=5, pady=5)

        self.vfx_mode = tk.StringVar(value="foreground")
        self.vfx_method = tk.StringVar(value="vvfxp")

        ttk.Radiobutton(mode_frame, text=self.tr("mode_foreground", "前景 / 谱子 (Foreground)"),
                        variable=self.vfx_mode, value="foreground").pack(anchor="w")
        ttk.Radiobutton(mode_frame, text=self.tr("mode_background", "背景 / 录制 (Background)"),
                        variable=self.vfx_mode, value="background").pack(anchor="w")

        method_frame = ttk.LabelFrame(tab, text=self.tr("processing_method", "处理方法"), padding=5)
        method_frame.pack(fill="x", padx=5, pady=5)

        ttk.Radiobutton(method_frame, text="Video VFX Pro",
                        variable=self.vfx_method, value="vvfxp").pack(anchor="w")
        ttk.Radiobutton(method_frame, text="Video VFX",
                        variable=self.vfx_method, value="vvfx").pack(anchor="w")

        keywords_frame = ttk.LabelFrame(tab, text=self.tr("keywords_config", "关键词配置（仅 Video VFX 模式使用）"), padding=5)
        keywords_frame.pack(fill="x", padx=5, pady=5)

        self.vfx_keywords = {
            "foreground": [
                '"eventType": "SetText"', '"eventType": "EmitParticle"',
                '"eventType": "SetParticle"', '"eventType": "SetDefaultText"',
                '"eventType": "AddDecoration"', '"eventType": "AddText"',
                '"eventType": "AddParticle"', "Background"
            ],
            "background": [
                '"eventType": "SetPlanetRotation"', '"eventType": "ScalePlanets"',
                '"eventType": "ColorTrack"', '"eventType": "AnimateTrack"',
                '"eventType": "RecolorTrack"', '"eventType": "MoveTrack"',
                '"eventType": "SetObject"', '"eventType": "SetFilter"',
                '"eventType": "HallOfMirrors"', '"eventType": "Bloom"',
                '"eventType": "ScreenTile"', '"eventType": "ScreenScroll"',
                '"eventType": "SetFrameRate"', '"eventType": "AddObject"',
                "Foreground"
            ]
        }

        ttk.Button(keywords_frame, text=self.tr("edit_fg_keywords", "编辑前景关键词"),
                   command=lambda: self._edit_keywords("foreground")).pack(side="left", padx=5)
        ttk.Button(keywords_frame, text=self.tr("edit_bg_keywords", "编辑背景关键词"),
                   command=lambda: self._edit_keywords("background")).pack(side="left", padx=5)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill="x", padx=5, pady=10)
        ttk.Button(btn_frame, text=self.tr("start_production", "开始制作"), command=self._run_vfx).pack(side="left", padx=5)

    def _create_preset_group_tab(self):
        """预设组应用标签页"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=self.tr("preset_groups", "预设组"))

        info_label = ttk.Label(tab, text=self.tr("preset_group_desc", "一键应用整个预设组到关键词树"),
                               font=("Arial", 10, "bold"))
        info_label.pack(pady=10)

        select_frame = ttk.Frame(tab)
        select_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(select_frame, text=self.tr("select_preset_group", "选择预设组:")).pack(side="left")
        self.preset_group_var = tk.StringVar()
        self.preset_group_combo = ttk.Combobox(select_frame, state="readonly",
                                               textvariable=self.preset_group_var, width=30)
        self.preset_group_combo.pack(side="left", padx=5)

        ttk.Button(select_frame, text=self.tr("refresh_list", "刷新列表"), command=self._refresh_preset_groups).pack(side="left")

        preview_frame = ttk.LabelFrame(tab, text=self.tr("group_preview", "组内容预览"), padding=5)
        preview_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.preset_preview = tk.Text(preview_frame, height=15, wrap=tk.WORD, state="disabled")
        self.preset_preview.pack(fill="both", expand=True, side="left")
        scrollbar = ttk.Scrollbar(preview_frame, command=self.preset_preview.yview)
        scrollbar.pack(side="right", fill="y")
        self.preset_preview.config(yscrollcommand=scrollbar.set)

        self.preset_group_combo.bind("<<ComboboxSelected>>", self._preview_preset_group)

        options_frame = ttk.Frame(tab)
        options_frame.pack(fill="x", padx=5, pady=5)

        self.preset_append_mode = tk.BooleanVar(value=True)
        ttk.Radiobutton(options_frame, text=self.tr("append_to_tree", "追加到现有树"),
                        variable=self.preset_append_mode, value=True).pack(side="left")
        ttk.Radiobutton(options_frame, text=self.tr("replace_tree", "替换现有树"),
                        variable=self.preset_append_mode, value=False).pack(side="left", padx=10)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill="x", padx=5, pady=10)
        ttk.Button(btn_frame, text=self.tr("apply_preset_group_btn", "应用预设组"), command=self._apply_preset_group).pack(side="left", padx=5)

        self._refresh_preset_groups()

    def _browse_cleanup_file(self):
        f = filedialog.askopenfilename(filetypes=[("ADOFAI files", "*.adofai")])
        if f:
            self.cleanup_file_var.set(f)
            self._auto_backup_path()

    def _use_current_file(self):
        if hasattr(self.parent, 'in_ent'):
            self.cleanup_file_var.set(self.parent.in_ent.get())
            self._auto_backup_path()
        else:
            messagebox.showwarning(self.tr("hint", "提示"), self.tr("cannot_get_input", "无法获取当前输入文件"))

    def _auto_backup_path(self):
        p = self.cleanup_file_var.get()
        if not p:
            return
        dir_ = Path(p).parent
        name = Path(p).stem
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f'{name}_backup_{ts}.adofai'
        self.cleanup_backup_var.set(str(dir_ / backup_name))

    def _browse_vfx_file(self):
        f = filedialog.askopenfilename(filetypes=[("ADOFAI files", "*.adofai")])
        if f:
            self.vfx_file_var.set(f)

    def _use_current_file_vfx(self):
        if hasattr(self.parent, 'in_ent'):
            self.vfx_file_var.set(self.parent.in_ent.get())
        else:
            messagebox.showwarning(self.tr("hint", "提示"), self.tr("cannot_get_input", "无法获取当前输入文件"))

    def _edit_keywords(self, mode: str):
        """编辑关键词对话框"""
        dialog = tk.Toplevel(self.parent)
        dialog.title(self.tr("edit_keywords_title", "编辑{}关键词").format(self.tr("foreground" if mode == "foreground" else "background", "前景" if mode == "foreground" else "背景")))
        dialog.geometry("500x300")

        text = tk.Text(dialog, wrap=tk.WORD)
        text.pack(fill="both", expand=True, padx=5, pady=5)
        text.insert(1.0, "\n".join(self.vfx_keywords[mode]))

        def save():
            content = text.get(1.0, tk.END).strip()
            self.vfx_keywords[mode] = [k.strip() for k in content.split("\n") if k.strip()]
            dialog.destroy()

        ttk.Button(dialog, text=self.tr("save", "保存"), command=save).pack(pady=5)

    def _run_cleanup(self):
        """执行清理"""
        file_path = self.cleanup_file_var.get()
        if not file_path or not Path(file_path).exists():
            messagebox.showerror(self.tr("error", "错误"), self.tr("select_valid_adofai", "请选择有效的ADOFAI文件"))
            return

        tool = self.cleanup_tool.get()
        backup_path = self.cleanup_backup_var.get()

        def worker():
            if tool == "empty_move":
                success = self.engine.run_empty_move_cleaner(file_path, backup_path)
            else:
                success, _ = self.engine.run_unused_deco_cleaner(
                    file_path, backup_path, dry_run=self.cleanup_dry_run.get()
                )
            if success:
                self.log_q.put((self.tr("cleanup_complete_msg", "清理完成"), "SUCCESS"))

        threading.Thread(target=worker, daemon=True).start()

    def _run_vfx(self):
        """执行VFX制作"""
        file_path = self.vfx_file_var.get()
        if not file_path or not Path(file_path).exists():
            messagebox.showerror(self.tr("error", "错误"), self.tr("select_valid_adofai", "请选择有效的ADOFAI文件"))
            return

        mode = self.vfx_mode.get()
        stem = Path(file_path).stem
        default_name = f"{stem}_{self.tr('foreground_suffix', '前景') if mode == 'foreground' else self.tr('background_suffix', '背景')}.adofai"

        output_path = filedialog.asksaveasfilename(
            defaultextension=".adofai",
            initialfile=default_name,
            filetypes=[("ADOFAI files", "*.adofai")]
        )
        if not output_path:
            return

        method = self.vfx_method.get()

        def worker():
            if method == "vvfxp":
                success = self.engine.run_video_vfx_pro(file_path, output_path, mode)
            else:
                success = self.engine.run_video_vfx(
                    file_path, output_path, mode, self.vfx_keywords
                )
            if success:
                self.log_q.put((self.tr("vfx_complete_msg", "VFX制作完成: {}").format(output_path), "SUCCESS"))

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_preset_groups(self):
        """刷新预设组列表"""
        if self.preset_loader:
            presets = self.preset_loader()
            self.preset_group_combo["values"] = list(presets.keys())

    def _preview_preset_group(self, event=None):
        """预览预设组内容"""
        group_name = self.preset_group_var.get()
        if not group_name or not self.preset_loader:
            return

        presets = self.preset_loader()
        if group_name not in presets:
            return

        self.preset_preview.config(state="normal")
        self.preset_preview.delete(1.0, tk.END)

        group_data = presets[group_name]
        preview_text = self.tr("group_preview_format", "【{}】包含 {} 个子预设:\n\n").format(group_name, len(group_data))

        for name, values in group_data.items():
            count = len(values) if isinstance(values, list) else 1
            preview_text += self.tr("sub_preset_item", "• {}: {} 项\n").format(name, count)
            if isinstance(values, list):
                for v in values[:3]:
                    preview_text += self.tr("preset_value_item", "    - {}\n").format(v)
                if len(values) > 3:
                    preview_text += self.tr("more_items", "    ... 还有 {} 个\n").format(len(values) - 3)
            else:
                preview_text += self.tr("preset_value_item", "    - {}\n").format(values)

        self.preset_preview.insert(1.0, preview_text)
        self.preset_preview.config(state="disabled")

    def _apply_preset_group(self):
        """应用预设组到树控件"""
        if not self.tree_widget:
            messagebox.showerror(self.tr("error", "错误"), self.tr("not_connected_to_tree", "未连接到关键词树控件"))
            return

        group_name = self.preset_group_var.get()
        if not group_name:
            messagebox.showwarning(self.tr("hint", "提示"), self.tr("please_select_preset_group", "请先选择预设组"))
            return

        if not self.preset_append_mode.get():
            for item in self.tree_widget.get_children():
                self.tree_widget.delete(item)

        presets = self.preset_loader()
        if group_name not in presets:
            messagebox.showerror(self.tr("error", "错误"), self.tr("preset_group_not_exist", "预设组不存在"))
            return

        success = self.engine.apply_preset_group(presets[group_name], self.tree_widget,
                                                 append=self.preset_append_mode.get())
        if success:
            messagebox.showinfo(self.tr("success", "成功"), self.tr("preset_group_applied_msg", "已应用预设组: {}\n所有关键词已作为主串添加").format(group_name))
