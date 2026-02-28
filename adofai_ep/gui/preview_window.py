# gui/preview_window.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import re
from pathlib import Path
from typing import List, Tuple

from processor import Mode, Processor
from config import Config
from i18n import I18n
i18n = I18n()

class PreviewWindow(tk.Toplevel):
    _instance = None  # 单例模式防止多开

    def __new__(cls, *args, **kwargs):
        if cls._instance is not None and cls._instance.winfo_exists():
            cls._instance.destroy()
        cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, parent, lines: List[str], mode, patterns: List[Tuple[str, List[str]]],
                 use_regex: bool, ignore_case: bool, repl: str, tree_widget=None):
        super().__init__(parent)
        self.title(i18n.tr().get("preview_title", "Processing Preview"))
        self.geometry("900x700")
        self.minsize(700, 500)

        # 保存参数
        self.lines = lines
        self.mode = mode
        self.patterns = patterns
        self.use_regex = use_regex
        self.ignore_case = ignore_case
        self.repl = repl
        self.tree_widget = tree_widget
        self.parent = parent

        # 配置
        self.cfg = Config()
        self.word_wrap = tk.BooleanVar(value=self.cfg.get("preview_word_wrap", True))
        self.max_lines = tk.IntVar(value=self.cfg.get("preview_max_lines", 1000))
        self.max_chars = tk.IntVar(value=self.cfg.get("preview_max_chars", 50000))
        self.search_text = tk.StringVar()
        tk.BooleanVar(value=self.cfg.get("preview_case_sensitive", False))
        self.current_search_index = 0
        self.search_results = []
        self.search_case_sensitive = tk.BooleanVar(value=False)

        self.original_content = ""
        self.edited_content = None

        self.setup_ui()
        self.start_preview()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_ui(self):
        """设置UI界面"""
        # 顶部控制栏
        control_frame = ttk.Frame(self)
        control_frame.pack(fill="x", padx=10, pady=5)

        left_control = ttk.Frame(control_frame)
        left_control.pack(side="left")

        ttk.Checkbutton(
            left_control,
            text=i18n.tr().get("preview_word_wrap", "Word wrap"),
            variable=self.word_wrap,
            command=self.toggle_word_wrap
        ).pack(side="left", padx=5)

        ttk.Button(
            left_control,
            text=i18n.tr().get("preview_settings", "Settings"),
            command=self.open_preview_settings
        ).pack(side="left", padx=5)

        # 搜索区域
        search_frame = ttk.LabelFrame(control_frame, text=i18n.tr().get("preview_search", "Search"))
        search_frame.pack(side="right", fill="x", expand=True)

        search_entry = ttk.Entry(search_frame, textvariable=self.search_text, width=30)
        search_entry.pack(side="left", padx=5)
        search_entry.bind("<Return>", lambda e: self.search_text_content())
        search_entry.bind("<KeyRelease>", lambda e: self.search_text_content() if len(e.widget.get()) >= 2 else None)

        ttk.Checkbutton(
            search_frame,
            text=i18n.tr().get("preview_case_sensitive", "Case sensitive"),
            variable=self.search_case_sensitive,
            command=self.search_text_content
        ).pack(side="left", padx=5)

        ttk.Button(search_frame, text=i18n.tr().get("preview_find_next", "Find next"), command=self.find_next).pack(side="left", padx=2)
        ttk.Button(search_frame, text=i18n.tr().get("preview_find_prev", "Find previous"), command=self.find_prev).pack(side="left", padx=2)

        self.search_result_var = tk.StringVar(value="")
        ttk.Label(search_frame, textvariable=self.search_result_var).pack(side="left", padx=10)

        # 文本预览区域
        text_container = ttk.Frame(self)
        text_container.pack(fill="both", expand=True, padx=10, pady=5)

        # 水平滚动条（放在文本下方）
        self.h_scrollbar = ttk.Scrollbar(text_container, orient="horizontal")
        self.h_scrollbar.pack(side="bottom", fill="x")

        # 垂直滚动条
        self.v_scrollbar = ttk.Scrollbar(text_container, orient="vertical")
        self.v_scrollbar.pack(side="right", fill="y")

        # 文本框
        self.text_widget = tk.Text(
            text_container,
            wrap=tk.WORD if self.word_wrap.get() else tk.NONE,
            width=80,
            height=25,
            font=("Consolas", 10),
            state="disabled",
            yscrollcommand=self.v_scrollbar.set,
            xscrollcommand=self.h_scrollbar.set
        )
        self.text_widget.pack(side="left", fill="both", expand=True)

        self.v_scrollbar.config(command=self.text_widget.yview)
        self.h_scrollbar.config(command=self.text_widget.xview)

        self.text_widget.bind("<KeyRelease>", self.on_text_changed)

        """搜索高亮标签"""
        # 所有匹配（淡蓝）
        self.text_widget.tag_configure("search",
                                       background="#cce5ff",
                                       foreground="#003366")

        # 当前选中（橙底黑字）
        self.text_widget.tag_configure("current_search",
                                       background="#ff9933",
                                       foreground="#000000")

        # 底部功能栏
        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(fill="x", padx=10, pady=5)

        self.line_count_var = tk.StringVar(value="正在处理...")
        ttk.Label(bottom_frame, textvariable=self.line_count_var).pack(side="left")

        self.progress = ttk.Progressbar(bottom_frame, mode="indeterminate")
        self.progress.pack(fill="x", expand=True, side="left", padx=5)

        ttk.Button(bottom_frame, text=i18n.tr().get("preview_import_selected", "Import selected keywords"), command=self.import_keywords).pack(side="right", padx=5)
        ttk.Button(bottom_frame, text=i18n.tr().get("preview_close", "Close"), command=self.on_close).pack(side="right")

        self.edit_btn = ttk.Button(bottom_frame, text=i18n.tr().get("preview_edit", "Edit Content"), command=self.toggle_edit_mode)
        self.edit_btn.pack(side="right", padx=5)

    def toggle_edit_mode(self):
        """切换文本框只读/可编辑状态"""
        if str(self.text_widget["state"]) == "disabled":
            self.text_widget.configure(state="normal")
            self.edit_btn.configure(text=i18n.tr().get("preview_save_changes", "Save Changes"))
        else:
            self.edited_content = self.text_widget.get(1.0, "end-1c")
            self.text_widget.configure(state="disabled")
            self.edit_btn.configure(text=i18n.tr().get("preview_edit", "Edit content"))

    def toggle_word_wrap(self):
        if self.word_wrap.get():
            self.text_widget.configure(wrap=tk.WORD)
            self.h_scrollbar.pack_forget()
        else:
            self.text_widget.configure(wrap=tk.NONE)
            self.h_scrollbar.pack(side="bottom", fill="x")

    def open_preview_settings(self):
        top = tk.Toplevel(self)
        top.title("预览设置")
        top.geometry("280x200")
        top.resizable(False, False)

        ttk.Label(top, text=i18n.tr().get("preview_max_lines", "Max preview lines:")).pack(pady=(10, 0))
        ttk.Entry(top, textvariable=self.max_lines).pack(pady=5)

        ttk.Label(top, text=i18n.tr().get("preview_max_chars", "Max preview chars:")).pack()
        ttk.Entry(top, textvariable=self.max_chars).pack(pady=5)

        ttk.Button(top, text=i18n.tr().get("btn_ok", "OK"), command=top.destroy).pack(pady=10)

    def search_text_content(self):
        """实时搜索 + 高亮 + 自动跳转"""
        search_term = self.search_text.get().strip()
        if not search_term:
            self.clear_search()
            return

        # 第一步：清除上一次高亮
        self.clear_search()

        try:
            # 必须先把 Text 设为 normal 才能修改 tag
            self.text_widget.configure(state="normal")
            content = self.text_widget.get(1.0, "end-1c")  # 去掉末尾换行

            # 支持正则 / 普通搜索
            flags = 0 if self.search_case_sensitive.get() else re.IGNORECASE
            pattern = re.compile(re.escape(search_term), flags)
            self.search_results = [(m.start(), m.end()) for m in pattern.finditer(content)]

            # 第二步：应用高亮
            for start, end in self.search_results:
                self.text_widget.tag_add("search", self._idx(start), self._idx(end))

            # 第三步：滚动到第一个匹配
            if self.search_results:
                self.current_search_index = 0
                self._jump_to_match()

            # 显示统计
            self.search_result_var.set(f"{len(self.search_results)} 个匹配")
        except Exception as e:
            self.search_result_var.set("搜索错误")
        finally:
            self.text_widget.configure(state="disabled")  # 恢复只读

    def _jump_to_match(self):
        """跳转到当前匹配并高亮"""
        if not self.search_results:
            return
        start, end = self.search_results[self.current_search_index]
        self.text_widget.see(self._idx(start))
        self.highlight_current_match()

    def _idx(self, pos):
        return f"1.0 + {pos} chars"

    def highlight_current_match(self):
        """高亮当前匹配（橙底黑字）"""
        self.text_widget.configure(state="normal")
        self.text_widget.tag_remove("current_search", "1.0", "end")
        if self.search_results:
            start, end = self.search_results[self.current_search_index]
            self.text_widget.tag_add("current_search", self._idx(start), self._idx(end))
        self.text_widget.configure(state="disabled")

    def find_next(self):
        if not self.search_results:
            return
        self.current_search_index = (self.current_search_index + 1) % len(self.search_results)
        self._jump_to_match()

    def find_prev(self):
        if not self.search_results:
            return
        self.current_search_index = (self.current_search_index - 1) % len(self.search_results)
        self._jump_to_match()

    def clear_search(self):
        self.text_widget.configure(state="normal")
        self.text_widget.tag_remove("search", 1.0, tk.END)
        self.text_widget.tag_remove("current_search", 1.0, tk.END)
        self.text_widget.configure(state="disabled")
        self.search_results.clear()
        self.current_search_index = 0
        self.search_result_var.set("")

    def import_keywords(self):
        if not self.tree_widget:
            messagebox.showwarning("警告", "无法导入，主窗口未连接")
            return

        try:
            self.text_widget.configure(state="normal")
            try:
                selected = self.text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)
            except tk.TclError:
                messagebox.showinfo("提示", "请先选中要导入的文本")
                return
            finally:
                self.text_widget.configure(state="disabled")

            lines = [line.strip() for line in selected.splitlines() if line.strip()]
            if not lines:
                messagebox.showinfo("提示", "没有找到有效的关键字")
                return

            if len(lines) > 10:
                if not messagebox.askyesno("确认", f"将导入 {len(lines)} 个关键字，是否继续？"):
                    return

            import_mode = messagebox.askyesno("导入方式", "是=追加到现有关键字，否=替换现有关键字")
            if not import_mode:
                self.tree_widget.delete(*self.tree_widget.get_children())

            for line in lines:
                self.tree_widget.insert("", "end", text=line)

            messagebox.showinfo("成功", f"已导入 {len(lines)} 个关键字")
            self.parent.focus()

        except Exception as e:
            messagebox.showerror("错误", f"导入失败: {str(e)}")

    def on_text_changed(self, event=None):
        self.edited_content = self.text_widget.get(1.0, tk.END)

    def save_preview_to_file(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.edited_content or self.original_content)
            messagebox.showinfo("已保存", f"已保存到：{path}")

    def start_preview(self):
        self.progress.start()
        threading.Thread(target=self.process_preview, daemon=True).start()

    def process_preview(self):
        try:
            lines = self.lines[:self.max_lines.get()]
            content = "".join(lines)
            if len(content) > self.max_chars.get():
                content = content[:self.max_chars.get()] + "\n【内容已截断】"
                lines = content.splitlines(keepends=True)

            processed = Processor.process(lines, self.mode, self.patterns, self.use_regex, self.ignore_case, self.repl)
            self.original_content = "".join(processed)
            self.after(0, self.update_preview, processed)
        except Exception as e:
            self.after(0, self.show_error, str(e))

    def update_preview(self, processed_lines):
        self.progress.stop()
        self.progress.pack_forget()

        self.text_widget.configure(state="normal")
        self.text_widget.delete(1.0, tk.END)
        self.text_widget.insert(1.0, "".join(processed_lines))
        self.text_widget.configure(state="disabled")

        line_count = len(processed_lines)
        original_count = len(self.lines[:self.max_lines.get()])
        self.line_count_var.set(f"结果: {line_count}/{original_count} 行")

    def show_error(self, msg):
        self.progress.stop()
        self.line_count_var.set("处理失败")
        self.text_widget.configure(state="normal")
        self.text_widget.delete(1.0, tk.END)
        self.text_widget.insert(1.0, f"预览处理失败:\n{msg}")
        self.text_widget.configure(state="disabled")

    def on_close(self):
        """关闭窗口前，如有改动提示保存"""
        # 如果正在编辑，先保存当前内容
        if str(self.text_widget["state"]) == "normal":
            self.edited_content = self.text_widget.get(1.0, "end-1c")

        # 判断是否真的改动过
        if self.edited_content is not None and self.edited_content != self.original_content:
            choice = messagebox.askyesnocancel("保存修改", "内容已修改，是否另存为文件？")
            if choice is True:
                self.save_preview_to_file()
            elif choice is None:
                return  # 取消关闭

        self.cfg.set("preview_word_wrap", self.word_wrap.get())
        self.cfg.set("preview_max_lines", self.max_lines.get())
        self.cfg.set("preview_max_chars", self.max_chars.get())
        self.cfg.set("preview_case_sensitive", self.search_case_sensitive.get())
        self.destroy()