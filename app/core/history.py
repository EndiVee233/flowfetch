"""下载历史记录（JSON 持久化）。"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtCore import (QAbstractListModel, QModelIndex, Property, Qt,
                            Signal, Slot)

from .config import HISTORY_PATH
from .helpers import human_duration, human_size
from .thumbs import cached_url


class HistoryModel(QAbstractListModel):
    TitleRole = Qt.UserRole + 1
    UrlRole = Qt.UserRole + 2
    UploaderRole = Qt.UserRole + 3
    ThumbRole = Qt.UserRole + 4
    FilePathRole = Qt.UserRole + 5
    OutputDirRole = Qt.UserRole + 6
    SizeRole = Qt.UserRole + 7
    TimeRole = Qt.UserRole + 8
    AudioRole = Qt.UserRole + 9
    DurationRole = Qt.UserRole + 10
    StatusRole = Qt.UserRole + 11
    KindRole = Qt.UserRole + 12

    _ROLES = {
        TitleRole: b"title",
        UrlRole: b"url",
        UploaderRole: b"uploader",
        ThumbRole: b"thumbnail",
        FilePathRole: b"filePath",
        OutputDirRole: b"outputDir",
        SizeRole: b"sizeText",
        TimeRole: b"timeText",
        AudioRole: b"audioOnly",
        DurationRole: b"durationText",
        StatusRole: b"status",
        KindRole: b"kind",
    }

    MAX_ITEMS = 1000

    changed = Signal()

    def __init__(self, parent=None, path: Path | None = None) -> None:
        super().__init__(parent)
        # 路径在构造时固定：与 Settings 同理，测试要指到临时文件时不该依赖模块全局，
        # 否则任何一次 save() 都可能写到用户真实的历史记录上。
        self._path = Path(path) if path is not None else HISTORY_PATH
        self._items: List[Dict[str, Any]] = []
        self.load()

    def roleNames(self) -> Dict[int, bytes]:
        return dict(self._ROLES)

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        it = self._items[index.row()]
        mapping = {
            self.TitleRole: it.get("title") or "未命名",
            self.UrlRole: it.get("url") or "",
            self.UploaderRole: it.get("uploader") or "",
            self.ThumbRole: cached_url(it.get("thumbnail") or ""),
            self.FilePathRole: it.get("filepath") or "",
            self.OutputDirRole: it.get("output_dir") or "",
            self.SizeRole: human_size(it.get("total")) if it.get("total") else "—",
            self.TimeRole: _time_text(it.get("finished_at")),
            self.AudioRole: bool(it.get("audio_only")),
            self.DurationRole: human_duration(it.get("duration")) if it.get("duration") else "",
            self.StatusRole: it.get("status") or "completed",
            self.KindRole: it.get("kind") or "complete",
        }
        return mapping.get(role)

    # ------------------------------------------------------------------
    def redirect(self, path: Path | str) -> None:
        """换一个历史记录文件并重新载入（开发工具用：避免自检污染用户数据）。"""
        self._path = Path(path)
        self._items = []
        self.load()
        self.changed.emit()

    def load(self) -> None:
        try:
            if self._path.exists():
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    self._items = [x for x in raw if isinstance(x, dict)]
        except Exception:
            self._items = []

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self._items, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self._path)
        except Exception:
            pass

    @Slot(str, result=int)
    def removeMatching(self, keyword: str) -> int:
        """删掉所有字段里含有关键字的记录，返回删除条数（开发工具清理自检记录用）。"""
        if not keyword:
            return 0
        keep = [it for it in self._items if keyword not in json.dumps(it, ensure_ascii=False)]
        removed = len(self._items) - len(keep)
        if not removed:
            return 0
        self.beginResetModel()
        self._items = keep
        self.endResetModel()
        self.save()
        self.changed.emit()
        return removed

    def add(self, record: Dict[str, Any], persist: bool = True) -> None:
        """加入一条记录。persist=False 时仅存在于内存中（供演示数据使用）。"""
        record.setdefault("finished_at", time.time())
        self.beginInsertRows(QModelIndex(), 0, 0)
        self._items.insert(0, record)
        self.endInsertRows()
        if len(self._items) > self.MAX_ITEMS:
            self.beginRemoveRows(QModelIndex(), self.MAX_ITEMS, len(self._items) - 1)
            del self._items[self.MAX_ITEMS:]
            self.endRemoveRows()
        if persist:
            self.save()
        self.changed.emit()

    def replaceThumb(self, original: str, local: str) -> None:
        """封面下载完成后刷新相关行。"""
        if not original:
            return
        for row, item in enumerate(self._items):
            if item.get("thumbnail") == original:
                index = self.index(row, 0)
                self.dataChanged.emit(index, index)

    @Slot(int)
    def removeAt(self, row: int) -> None:
        if 0 <= row < len(self._items):
            self.beginRemoveRows(QModelIndex(), row, row)
            self._items.pop(row)
            self.endRemoveRows()
            self.save()
            self.changed.emit()

    @Slot()
    def clear(self) -> None:
        if not self._items:
            return
        self.beginResetModel()
        self._items = []
        self.endResetModel()
        self.save()
        self.changed.emit()

    @Slot(result="QVariantList")
    def allItems(self) -> List[Dict[str, Any]]:
        return list(self._items)

    @Property(int, notify=changed)
    def count(self) -> int:
        return len(self._items)

    @Property("QVariantMap", notify=changed)
    def summary(self) -> Dict[str, Any]:
        total_bytes = sum(int(i.get("total") or 0) for i in self._items)
        return {
            "count": len(self._items),
            "totalSize": human_size(total_bytes) if total_bytes else "0 B",
        }


def _time_text(ts: Any) -> str:
    try:
        ts = float(ts)
    except (TypeError, ValueError):
        return ""
    now = time.time()
    delta = now - ts
    if delta < 60:
        return "刚刚"
    if delta < 3600:
        return f"{int(delta // 60)} 分钟前"
    if delta < 86400:
        return f"{int(delta // 3600)} 小时前"
    if delta < 86400 * 7:
        return f"{int(delta // 86400)} 天前"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
