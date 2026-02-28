from __future__ import annotations
import json
import re
import queue
import shutil
from typing import Set, List, Tuple, Dict
from enum import Enum

# 导入 i18n 支持
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from i18n import I18n


class ToolType(Enum):
    EMPTY_MOVE_CLEANER = "empty_move"
    UNUSED_DECO_CLEANER = "unused_deco"
    VIDEO_VFX = "vvfx"
    VFX_PRO = "vvfxp"


class ToolboxEngine:
    """工具箱核心引擎"""

    def __init__(self, log_queue: queue.Queue):
        self.log_q = log_queue
        self._stop_flag = False
        self.i18n = I18n()

    def tr(self, key: str, default: str = "") -> str:
        """获取翻译文本"""
        return self.i18n.tr().get(key, default)

    def log(self, msg: str, level: str = "INFO"):
        self.log_q.put((msg, level))

    def stop(self):
        self._stop_flag = True

    # ========== Empty Move Cleaner ==========
    def run_empty_move_cleaner(self, adofai_path: str, backup_path: str = None) -> bool:
        """删除空的MoveDecorations事件"""
        try:
            self.log(self.tr("scanning_empty_move", "开始扫描空MoveDecorations事件..."))

            # 备份
            if backup_path:
                self._backup_file(adofai_path, backup_path)

            with open(adofai_path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()

            # 收集所有存在的tag
            existing_tags: Set[str] = set()
            for line in lines:
                try:
                    ev = json.loads(line.strip().rstrip(','))
                    if ev.get('eventType') in {'AddDecoration', 'AddText', 'AddObject', 'AddParticle'}:
                        existing_tags.update(ev.get('tag', '').split())
                except:
                    continue

            self.log(self.tr("found_valid_tags", "发现 {} 个有效装饰tag").format(len(existing_tags)))

            # 找出空的MoveDecorations
            del_indices = []
            for idx, line in enumerate(lines):
                try:
                    ev = json.loads(line.strip().rstrip(','))
                    if ev.get('eventType') == 'MoveDecorations':
                        move_tags = set(ev.get('tag', '').split())
                        if not (move_tags & existing_tags):  # 无交集
                            del_indices.append(idx)
                except:
                    continue

            if not del_indices:
                self.log(self.tr("no_empty_move_found", "未发现空的MoveDecorations事件"), "INFO")
                return True

            # 删除（从后往前）
            for idx in reversed(del_indices):
                del lines[idx]

            # 保存
            with open(adofai_path, 'w', encoding='utf-8-sig') as f:
                f.writelines(lines)

            self.log(self.tr("deleted_empty_move", "已删除 {} 处空MoveDecorations").format(len(del_indices)), "SUCCESS")
            return True

        except Exception as e:
            self.log(self.tr("empty_move_failed", "EmptyMoveCleaner失败: {}").format(e), "ERROR")
            return False

    def _backup_file(self, src: str, dst: str):
        """创建文件备份"""
        try:
            shutil.copy2(src, dst)
            self.log(self.tr("backup_created", "已备份到: {}").format(dst))
        except Exception as e:
            self.log(self.tr("backup_failed", "备份失败: {}").format(e), "ERROR")

    # ========== Unused Decoration Cleaner ==========
    def run_unused_deco_cleaner(self, adofai_path: str, backup_path: str = None,
                                dry_run: bool = False) -> Tuple[bool, Dict]:
        """删除未被引用的装饰物"""
        try:
            self.log(self.tr("analyzing_deco_refs", "开始分析装饰物引用关系..."))

            # 备份
            if backup_path:
                self._backup_file(adofai_path, backup_path)

            with open(adofai_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()

            # 提取数组内容
            actions_content = self._find_array_content(content, 'actions')
            decorations_content = self._find_array_content(content, 'decorations')

            if not actions_content and not decorations_content:
                self.log(self.tr("no_arrays_found", "未找到actions或decorations数组，尝试整体解析..."), "WARN")
                actions_content = content
                decorations_content = content

            # 收集被引用的tag
            ref_events = []
            referenced_tags: Set[str] = set()

            REF_TYPES = {'MoveDecorations', 'SetText', 'EmitParticle', 'SetParticle', 'SetObject'}

            if actions_content:
                ref_events = self._parse_events_regex(actions_content, REF_TYPES)
                for ev_type, tag_str, _ in ref_events:
                    if tag_str:
                        referenced_tags.update(t for t in tag_str.strip().split() if t)

            self.log(self.tr("found_ref_events", "发现 {} 个引用事件，{} 个唯一tag").format(len(ref_events), len(referenced_tags)))

            # 处理hitboxDecoTag递归
            hitbox_tags: Set[str] = set()
            DECO_TYPES = {'AddDecoration', 'AddText', 'AddObject', 'AddParticle'}

            if decorations_content:
                all_decorations = self._parse_events_regex(decorations_content, DECO_TYPES)
                for ev_type, tag_str, obj_text in all_decorations:
                    dec_tags = set(t for t in tag_str.strip().split() if t)
                    if dec_tags & referenced_tags:  # 被引用
                        hitbox_str = self._extract_field(obj_text, "hitboxDecoTag")
                        if hitbox_str:
                            hitbox_tags.update(t for t in hitbox_str.strip().split() if t)

            referenced_tags.update(hitbox_tags)
            if hitbox_tags:
                self.log(self.tr("found_hitbox_tags", "发现 {} 个hitboxDecoTag").format(len(hitbox_tags)))

            # 分析装饰物
            to_delete = []
            to_keep = []

            if decorations_content:
                decorations = self._parse_events_regex(decorations_content, DECO_TYPES)
                for idx, (ev_type, tag_str, full_text) in enumerate(decorations):
                    dec_tags = set(t for t in tag_str.strip().split() if t)

                    if not dec_tags:
                        to_delete.append((idx, ev_type, [], full_text, 'no_tag'))
                    elif dec_tags & referenced_tags:
                        to_keep.append((idx, ev_type, dec_tags, full_text))
                    else:
                        to_delete.append((idx, ev_type, dec_tags, full_text, 'unused'))

            self.log(self.tr("deco_analysis_result", "保留 {} 个，删除 {} 个装饰物").format(len(to_keep), len(to_delete)))

            if dry_run:
                return True, {
                    'to_keep': to_keep,
                    'to_delete': to_delete,
                    'referenced_tags': referenced_tags
                }

            if not to_delete:
                self.log(self.tr("no_unused_deco", "未发现未使用的装饰物"))
                return True, {}

            # 执行删除
            new_decorations = decorations_content
            for idx, ev_type, tags, full_text, reason in reversed(to_delete):
                escaped = re.escape(full_text)
                pattern = r'(\s*,\s*)?' + escaped + r'(\s*,\s*)?'

                def replacer(m):
                    before, after = m.group(1) or '', m.group(2) or ''
                    if before and after:
                        return ','
                    return ''

                new_decorations, count = re.subn(pattern, replacer, new_decorations, count=1)
                if count == 0:
                    self.log(self.tr("warn_delete_failed", "警告: 未能删除索引 {} 的装饰物").format(idx), "WARN")

            # 替换回原内容
            if decorations_content:
                pattern = r'("decorations"\s*:\s*\[)[^\]]*(\])'

                def replace_deco(m):
                    return m.group(1) + new_decorations + m.group(2)

                new_content = re.sub(pattern, replace_deco, content, flags=re.DOTALL)
            else:
                new_content = content

            with open(adofai_path, 'w', encoding='utf-8-sig') as f:
                f.write(new_content)

            self.log(self.tr("cleanup_complete", "清理完成，删除 {} 个装饰物").format(len(to_delete)), "SUCCESS")
            return True, {'deleted': len(to_delete), 'kept': len(to_keep)}

        except Exception as e:
            self.log(self.tr("unused_deco_failed", "UnusedDecoCleaner失败: {}").format(e), "ERROR")
            import traceback
            self.log(traceback.format_exc(), "ERROR")
            return False, {}

    def _find_array_content(self, content: str, array_name: str) -> str:
        pattern = r'"%s"\s*:\s*\[' % re.escape(array_name)
        match = re.search(pattern, content)
        if not match:
            return ""
        start = match.end()
        bracket_count = 1
        idx = start
        while idx < len(content) and bracket_count > 0:
            if content[idx] == '[':
                bracket_count += 1
            elif content[idx] == ']':
                bracket_count -= 1
            elif content[idx] == '"':
                idx += 1
                while idx < len(content) and content[idx] != '"':
                    if content[idx] == '\\':
                        idx += 2
                    else:
                        idx += 1
            idx += 1
        return content[start:idx - 1]

    def _parse_events_regex(self, content: str, event_types: set) -> List[Tuple[str, str, str]]:
        type_pattern = '|'.join(event_types)
        pattern = r'\{\s*"floor"\s*:\s*[^,]+,\s*"eventType"\s*:\s*"(%s)"[^{}]*(?:\{[^{}]*\}[^{}]*)*\s*\}' % type_pattern
        matches = []
        for match in re.finditer(pattern, content, re.DOTALL):
            obj_text = match.group(0)
            event_type = match.group(1)
            tag = self._extract_field(obj_text, "tag")
            matches.append((event_type, tag, obj_text))
        return matches

    def _extract_field(self, obj_text: str, field: str) -> str:
        pattern = r'"%s"\s*:\s*"([^"]*)"' % re.escape(field)
        match = re.search(pattern, obj_text)
        return match.group(1) if match else ""

    def run_video_vfx(self, adofai_path: str, output_path: str,
                       mode: str, keywords: Dict[str, List[str]]) -> bool:
        try:
            self.log(self.tr("vvfx_start", "开始Video VFX制作模式: {}").format(mode))

            with open(adofai_path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()

            target_keywords = keywords.get(mode, [])
            if not target_keywords:
                self.log(self.tr("no_keywords_config", "未找到关键词配置"), "ERROR")
                return False

            filtered = []
            removed = 0

            for line in lines:
                should_remove = any(kw in line for kw in target_keywords)
                if should_remove:
                    removed += 1
                else:
                    filtered.append(line)

            with open(output_path, 'w', encoding='utf-8-sig') as f:
                f.writelines(filtered)

            self.log(self.tr("vvfx_complete", "完成: 删除 {} 行, 保留 {} 行").format(removed, len(filtered)), "SUCCESS")
            return True

        except Exception as e:
            self.log(self.tr("vvfx_failed", "Video VFX制作失败: {}").format(e), "ERROR")
            return False

    def run_video_vfx_pro(self, adofai_path: str, output_path: str, mode: str) -> bool:
        try:
            self.log(self.tr("vvfxp_start", "开始Video VFX Pro制作模式: {}").format(mode))

            with open(adofai_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()

            if mode == "foreground":
                blacklist = {"HallOfMirrors", "CustomBackground"}
            else:
                blacklist = {
                    "SetPlanetRotation", "ScalePlanets", "HallOfMirrors",
                    "ColorTrack", "AnimateTrack", "RecolorTrack", "MoveTrack",
                    "SetObject", "SetFilter", "Bloom", "ScreenTile",
                    "ScreenScroll", "SetFrameRate"
                }

            event_pattern = re.compile(r'^\s*\{[^}]*"eventType"\s*:\s*"(\w+)"[^}]*\},?$', re.M)
            kill_list = []

            for m in event_pattern.finditer(content):
                et = m.group(1)
                raw = m.group(0)

                # 特殊处理Flash和SetFilterAdvanced
                if et in {"Flash", "SetFilterAdvanced"}:
                    if mode == "foreground" and "Background" in raw:
                        kill_list.append(raw)
                        continue
                    if mode == "background" and "Foreground" in raw:
                        kill_list.append(raw)
                        continue

                if et in blacklist:
                    kill_list.append(raw)

            tmp = content
            for raw in kill_list:
                tmp = tmp.replace(raw, "")

            self.log(self.tr("vvfxp_removed_events", "删除 {} 个事件").format(len(kill_list)))

            # 装饰物深度过滤
            deco_pattern = re.compile(r'^\s*\{[^}]*"depth"\s*:\s*([-+]?\d+(?:\.\d+)?)[^}]*\},?$', re.M)

            for m in deco_pattern.finditer(tmp):
                depth = float(m.group(1))
                raw = m.group(0)

                keep = False
                if mode == "foreground":
                    keep = self._should_keep_fg(raw, depth)
                else:
                    keep = self._should_keep_bg(raw, depth)

                if not keep:
                    tmp = tmp.replace(raw, "")

            with open(output_path, 'w', encoding='utf-8-sig') as f:
                f.write(tmp)

            self.log(self.tr("vvfxp_complete", "Video VFX Pro制作处理完成"), "SUCCESS")
            return True

        except Exception as e:
            self.log(self.tr("vvfxp_failed", "VFX制作 Pro失败: {}").format(e), "ERROR")
            import traceback
            self.log(traceback.format_exc(), "ERROR")
            return False

    def _should_keep_fg(self, raw: str, depth: float) -> bool:
        """前景模式：负深度保留，非负深度根据masking判断"""
        if depth < 0:
            return True
        return self._check_masking_fg(raw, depth)

    def _should_keep_bg(self, raw: str, depth: float) -> bool:
        """背景模式：非负深度保留，负深度根据masking判断"""
        if depth >= 0:
            return True
        return self._check_masking_bg(raw, depth)

    def _check_masking_fg(self, raw: str, depth: float) -> bool:
        mtype = self._quick_val(raw, "maskingType")
        if mtype is None or mtype == "None":
            return False
        if mtype == "Mask":
            if not self._quick_val(raw, "useMaskingDepth", False):
                return True
            front = self._quick_val(raw, "maskingFrontDepth", 0.0)
            back = self._quick_val(raw, "maskingBackDepth", 0.0)
            low, high = sorted([front, back])
            if low >= 0:
                return False
            if high <= 0:
                return True
            return True  # 跨0保留
        if mtype in {"VisibleInsideMask", "VisibleOutsideMask"}:
            return False
        return True

    def _check_masking_bg(self, raw: str, depth: float) -> bool:
        mtype = self._quick_val(raw, "maskingType")
        if mtype is None or mtype == "None":
            return False
        if mtype == "Mask":
            if not self._quick_val(raw, "useMaskingDepth", False):
                return True
            front = self._quick_val(raw, "maskingFrontDepth", 0.0)
            back = self._quick_val(raw, "maskingBackDepth", 0.0)
            low, high = sorted([front, back])
            if low >= 0:
                return True
            if high <= 0:
                return False
            return True
        if mtype in {"VisibleInsideMask", "VisibleOutsideMask"}:
            return False
        return True

    def _quick_val(self, raw: str, key: str, default=None):
        m = re.search(rf'"{key}"\s*:\s*("?)([^",}}]+)\1', raw)
        if not m:
            return default
        v = m.group(2)
        if v in {"true", "True"}: return True
        if v in {"false", "False"}: return False
        try:
            return int(v)
        except ValueError:
            try:
                return float(v)
            except ValueError:
                return v

    def apply_preset_group(self, preset_data: Dict, tree_widget, append: bool = True) -> bool:
        """应用整个预设组到树控件 - 默认作为主串（不带子串）"""
        try:
            count = 0
            for sub_name, values in preset_data.items():
                if not isinstance(values, list):
                    values = [values]
                for v in values:
                    tree_widget.insert("", "end", text=v)
                    count += 1
            self.log(self.tr("preset_group_applied", "已应用预设组: {} 个关键词（全部作为主串）").format(count))
            return True
        except Exception as e:
            self.log(self.tr("preset_group_failed", "应用预设组失败: {}").format(e), "ERROR")
            return False