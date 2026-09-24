"""下载任务的数据模型。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Slot

from .helpers import human_duration, human_eta, human_size, human_speed
from .thumbs import cached_url

# 状态常量
QUEUED = "queued"
ANALYZING = "analyzing"
DOWNLOADING = "downloading"
PROCESSING = "processing"
PAUSED = "paused"
COMPLETED = "completed"
FAILED = "failed"
CANCELED = "canceled"

STATUS_TEXT = {
    QUEUED: "排队中",
    ANALYZING: "解析中",
    DOWNLOADING: "下载中",
    PROCESSING: "处理中",
    PAUSED: "已暂停",
    COMPLETED: "已完成",
    FAILED: "已失败",
    CANCELED: "已取消",
}


@dataclass
class Task:
    id: str
    url: str
    title: str = "正在解析…"
    uploader: str = ""
    thumbnail: str = ""
    duration: float = 0.0
    status: str = QUEUED
    detail: str = ""
    progress: float = 0.0
    downloaded: int = 0
    total: int = 0
    speed: float = 0.0
    eta: Optional[int] = None
    error: str = ""
    error_kind: str = ""
    format_label: str = "自动选择最佳画质"
    audio_only: bool = False
    filepath: str = ""
    output_dir: str = ""
    playlist_index: int = 0
    playlist_count: int = 0
    added_at: float = field(default_factory=time.time)
    finished_at: float = 0.0
    canceled: bool = False
    preset: str = "best"
    format_id: str = ""
    sub_langs: str = ""
    # 字幕输出格式："" 跟随全局设置；"原始" 保持网站格式；srt / vtt / ass / lrc
    sub_format: str = ""
    # 封面下载方式："" 跟随全局设置；"none" 不下载；"original" 原图；
    # "640" / "320" 下载后缩放到对应宽度
    cover_mode: str = ""
    # 解析时走的是匿名（不带登录凭据）模式：下载时要保持一致，
    # 否则会出现「解析成功但下载被拒」的错配
    anonymous: bool = False
    # 历史记录展示用：complete=完整（已合并）, video_only=仅视频, audio_only=仅音频
    kind: str = "complete"
    extra: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    def as_history(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "uploader": self.uploader,
            "thumbnail": self.thumbnail,
            "duration": self.duration,
            "filepath": self.filepath,
            "output_dir": self.output_dir,
            "total": self.total,
            "audio_only": self.audio_only,
            "kind": self.kind,
            "sub_langs": self.sub_langs,
            "cover_mode": self.cover_mode,
            "format_label": self.format_label,
            "finished_at": self.finished_at or time.time(),
            "status": self.status,
        }

    def progress_text(self) -> str:
        if self.status == FAILED:
            return self.error_kind or "下载失败"
        if self.status == CANCELED:
            return "已取消"
        if self.status == PAUSED:
            return f"已暂停 · {self.progress * 100:.1f}%" if self.total > 0 else "已暂停"
        if self.status == QUEUED:
            return "等待开始"
        # 已完成与下载中都是百分比：完成时 progress 已经是 1.0，无需单独分支
        return f"{self.progress * 100:.1f}%"

    def size_text(self) -> str:
        if self.total > 0:
            return f"{human_size(self.downloaded)} / {human_size(self.total)}"
        if self.downloaded > 0:
            return "已下载 " + human_size(self.downloaded)
        return "—"


class TaskModel(QAbstractListModel):
    """供 QML ListView 使用的任务列表模型。"""

    IdRole = Qt.UserRole + 1
    UrlRole = Qt.UserRole + 2
    TitleRole = Qt.UserRole + 3
    UploaderRole = Qt.UserRole + 4
    ThumbRole = Qt.UserRole + 5
    StatusRole = Qt.UserRole + 6
    StatusTextRole = Qt.UserRole + 7
    ProgressRole = Qt.UserRole + 8
    ProgressTextRole = Qt.UserRole + 9
    SizeTextRole = Qt.UserRole + 10
    SpeedTextRole = Qt.UserRole + 11
    EtaTextRole = Qt.UserRole + 12
    ErrorRole = Qt.UserRole + 13
    FormatRole = Qt.UserRole + 14
    FilePathRole = Qt.UserRole + 15
    OutputDirRole = Qt.UserRole + 16
    DurationTextRole = Qt.UserRole + 17
    DetailRole = Qt.UserRole + 18
    PlaylistRole = Qt.UserRole + 19
    AudioOnlyRole = Qt.UserRole + 20
    AddedAtRole = Qt.UserRole + 21
    ActiveRole = Qt.UserRole + 22
    ErrorKindRole = Qt.UserRole + 23

    _ROLES = {
        IdRole: b"taskId",
        UrlRole: b"url",
        TitleRole: b"title",
        UploaderRole: b"uploader",
        ThumbRole: b"thumbnail",
        StatusRole: b"status",
        StatusTextRole: b"statusText",
        ProgressRole: b"progress",
        ProgressTextRole: b"progressText",
        SizeTextRole: b"sizeText",
        SpeedTextRole: b"speedText",
        EtaTextRole: b"etaText",
        ErrorRole: b"error",
        FormatRole: b"formatLabel",
        FilePathRole: b"filePath",
        OutputDirRole: b"outputDir",
        DurationTextRole: b"durationText",
        DetailRole: b"detail",
        PlaylistRole: b"playlistLabel",
        AudioOnlyRole: b"audioOnly",
        AddedAtRole: b"addedAt",
        ActiveRole: b"isActive",
        ErrorKindRole: b"errorKind",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._tasks: List[Task] = []

    # -- Qt 接口 -------------------------------------------------------
    def roleNames(self) -> Dict[int, bytes]:
        return dict(self._ROLES)

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: B008
        if parent.isValid():
            return 0
        return len(self._tasks)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._tasks)):
            return None
        t = self._tasks[index.row()]
        mapping = {
            self.IdRole: t.id,
            self.UrlRole: t.url,
            self.TitleRole: t.title,
            self.UploaderRole: t.uploader,
            self.ThumbRole: cached_url(t.thumbnail),
            self.StatusRole: t.status,
            self.StatusTextRole: self._status_text(t),
            self.ProgressRole: t.progress,
            self.ProgressTextRole: t.progress_text(),
            self.SizeTextRole: t.size_text(),
            self.SpeedTextRole: human_speed(t.speed) if t.status == DOWNLOADING else "—",
            self.EtaTextRole: human_eta(t.eta) if t.status == DOWNLOADING else "—",
            self.ErrorRole: t.error,
            self.ErrorKindRole: t.error_kind,
            self.FormatRole: t.format_label,
            self.FilePathRole: t.filepath,
            self.OutputDirRole: t.output_dir,
            self.DurationTextRole: human_duration(t.duration) if t.duration else "",
            self.DetailRole: t.detail,
            self.PlaylistRole: (
                f"第 {t.playlist_index}/{t.playlist_count} 项"
                if t.playlist_count else ""
            ),
            self.AudioOnlyRole: t.audio_only,
            self.AddedAtRole: t.added_at,
            self.ActiveRole: t.status in (ANALYZING, DOWNLOADING, PROCESSING),
        }
        return mapping.get(role)

    @staticmethod
    def _status_text(t: Task) -> str:
        if t.status == DOWNLOADING and t.detail:
            return t.detail
        if t.status == PROCESSING and t.detail:
            return t.detail
        return STATUS_TEXT.get(t.status, t.status)

    # -- 数据操作 ------------------------------------------------------
    def add(self, task: Task) -> int:
        row = len(self._tasks)
        self.beginInsertRows(QModelIndex(), row, row)
        self._tasks.append(task)
        self.endInsertRows()
        return row

    def index_of(self, task_id: str) -> int:
        for i, t in enumerate(self._tasks):
            if t.id == task_id:
                return i
        return -1

    def get(self, task_id: str) -> Optional[Task]:
        idx = self.index_of(task_id)
        return self._tasks[idx] if idx >= 0 else None

    def touch(self, task_id: str) -> None:
        idx = self.index_of(task_id)
        if idx < 0:
            return
        mi = self.index(idx, 0)
        self.dataChanged.emit(mi, mi)

    def remove(self, task_id: str) -> None:
        idx = self.index_of(task_id)
        if idx < 0:
            return
        self.beginRemoveRows(QModelIndex(), idx, idx)
        self._tasks.pop(idx)
        self.endRemoveRows()

    def replaceThumb(self, original: str, local: str) -> None:
        """封面下载完成后刷新相关行。"""
        if not original:
            return
        for task in self._tasks:
            if task.thumbnail == original:
                self.touch(task.id)

    @Slot(str)
    def removeById(self, task_id: str) -> None:
        self.remove(task_id)

    @Slot()
    def clearFinished(self) -> None:
        keep = [t for t in self._tasks if t.status in (DOWNLOADING, PROCESSING, QUEUED, ANALYZING, PAUSED)]
        if len(keep) == len(self._tasks):
            return
        self.beginResetModel()
        self._tasks = keep
        self.endResetModel()

    @Slot()
    def clearAll(self) -> None:
        self.beginResetModel()
        self._tasks = []
        self.endResetModel()

    def queued(self) -> List[Task]:
        return [t for t in self._tasks if t.status == QUEUED]

    def active_count(self) -> int:
        return len([t for t in self._tasks if t.status in (ANALYZING, DOWNLOADING, PROCESSING)])

    def all_tasks(self) -> List[Task]:
        return list(self._tasks)

    @Slot(result=int)
    def count(self) -> int:
        return len(self._tasks)
