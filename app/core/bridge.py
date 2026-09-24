"""QML 与 Python 之间的桥接对象。"""
from __future__ import annotations

import csv
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtCore import Property, QObject, QThread, Signal, Slot
from PySide6.QtGui import QGuiApplication

from .. import APP_NAME, APP_TAGLINE, __version__
from . import taskmodel as TM
from . import bili_format, yt_format
from .bilibili import BilibiliAuth
from .config import Settings
from .deps import DependencyManager
from .downloader import Analyzer, DownloadEngine
from .thumbs import ThumbFetcher
from .helpers import app_data_dir, default_download_dir, human_size, open_in_explorer
from .history import HistoryModel
from .taskmodel import Task, TaskModel
from .weblogin import WebLoginManager
from .guestcookie import GuestCookieWorker, find_browser, guest_cookie_path
# yt_dlp 一律从 core.ytdlp 取（惰性代理），打包后引擎缺失也不会在导入期崩
from .ytdlp import available as ytdlp_available
from .ytdlp import installed_version as ytdlp_installed_version

URL_RE = re.compile(r"https?://[^\s\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]+", re.I)
# 链接尾部常见的标点（. , ; ) ] } " '）
_TRAILING = ".,;)]}" + chr(34) + chr(39)


def _join_list(value) -> str:
    """把 QML 传来的字符串或数组统一成逗号分隔的字符串。"""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ",".join(str(x).strip() for x in value if str(x).strip())
    return str(value).strip()


class Bridge(QObject):
    """暴露给 QML 的统一入口。"""

    mediaReady = Signal(dict)
    mediaFailed = Signal(str, str, str)   # 友好标题, 建议, 原始信息
    toast = Signal(str, str, str)
    analyzeStateChanged = Signal()
    taskDone = Signal(str, str, str, str)   # 任务 id, 标题, 状态, 失败原因
    clipboardUrl = Signal(str)
    mediaThumbReady = Signal(str, str)   # 原始封面地址, 本地缓存地址

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = Settings(self)
        self._tasks = TaskModel(self)
        self._history = HistoryModel(self)
        self._engine = DownloadEngine(self._settings, self._tasks, self)
        self._analyzer = Analyzer(self._settings, self)
        self._thumbs = ThumbFetcher(self)
        self._thumbs.ready.connect(self._on_thumb_ready)
        self._deps = DependencyManager(self._settings, self)
        self._bilibili = BilibiliAuth(self)
        self._bilibili.changed.connect(self._on_bili_changed)
        self._weblogin = WebLoginManager(self)
        self._weblogin.changed.connect(self._on_weblogin_changed)
        self._weblogin.loginSucceeded.connect(self._on_weblogin_ok)
        self._weblogin.failed.connect(
            lambda msg: self.toast.emit("error", "登录失败", msg))
        self._deps.changed.connect(self._sync_ffmpeg)
        self._deps.progress.connect(lambda *_a: self.analyzeStateChanged.emit())
        self._deps.finished.connect(self._on_dep_finished)
        self._sync_ffmpeg()
        self._analyzing = False
        self._last_analyze_url = ""
        self._guest_thread: QThread | None = None
        self._guest_busy = False
        self._dark = True
        self._font_family = "Microsoft YaHei UI"
        self._icon_family = "Segoe Fluent Icons"

        self._analyzer.done.connect(self._on_analyze_done)
        self._analyzer.failed.connect(self._on_analyze_failed)
        self._engine.taskDone.connect(self._on_task_done)

    # ------------------------------------------------------------------
    # 子对象
    # ------------------------------------------------------------------
    @Property(QObject, constant=True)
    def settings(self) -> Settings:
        return self._settings

    @Property(QObject, constant=True)
    def tasks(self) -> TaskModel:
        return self._tasks

    @Property(QObject, constant=True)
    def history(self) -> HistoryModel:
        return self._history

    @Property(QObject, constant=True)
    def engine(self) -> DownloadEngine:
        return self._engine

    @Property(QObject, constant=True)
    def deps(self) -> DependencyManager:
        return self._deps

    @Property(QObject, constant=True)
    def bilibili(self) -> BilibiliAuth:
        return self._bilibili

    @Property(QObject, constant=True)
    def thumbs(self) -> ThumbFetcher:
        return self._thumbs

    @Property(QObject, constant=True)
    def weblogin(self) -> WebLoginManager:
        return self._weblogin

    def _on_weblogin_changed(self) -> None:
        self.analyzeStateChanged.emit()

    def _on_weblogin_ok(self, site: str, label: str) -> None:
        self.toast.emit("success", f"{label} 登录成功",
                        "凭据已保存到本机，之后无需再次登录。")
        # 登录后可访问的内容会变多，重新解析一次当前链接
        if self._last_analyze_url:
            self.reanalyze()

    # ------------------------------------------------------------------
    # 访客 Cookie：自动获取，用于规避短时间批量下载的限流
    # ------------------------------------------------------------------
    @Slot(result="QVariantMap")
    def guestCookieStatus(self) -> Dict[str, Any]:
        path = guest_cookie_path()
        count = 0
        if path is not None:
            try:
                for line in path.read_text(encoding="utf-8",
                                           errors="replace").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("#") and not line.startswith("#HttpOnly_"):
                        continue
                    count += 1
            except OSError:
                pass
        last = float(self._settings.get("guest_cookie_updated_at") or 0)
        return {
            "available": path is not None,
            "count": count,
            "hasBrowser": find_browser() != "",
            "busy": self._guest_busy,
            "updatedAt": last,
        }

    @Slot()
    def autoFetchGuestCookie(self) -> None:
        """需要时才自动获取：文件缺失，或已超过 7 天未更新。"""
        if not self._settings.get("guest_cookie_enabled", True):
            return
        if self._guest_busy:
            return
        path = guest_cookie_path()
        if path is not None:
            last = float(self._settings.get("guest_cookie_updated_at") or 0)
            if time.time() - last < 7 * 86400:
                return
        self.refreshGuestCookies()

    @Slot()
    def refreshGuestCookies(self) -> None:
        """通过 CDP 从本机浏览器重新获取访客 Cookie。"""
        if self._guest_thread is not None and self._guest_thread.isRunning():
            return
        if not find_browser():
            self.toast.emit("warning", "无法自动获取 Cookie",
                            "未在本机找到 Chrome 或 Edge，可在设置中手动指定 Cookies 文件。")
            return
        self._guest_busy = True
        thread = GuestCookieWorker()   # 自身即后台线程，run() 在子线程执行
        thread.finished.connect(self._on_guest_cookies)
        thread.finished.connect(thread.deleteLater)
        self._guest_thread = thread
        thread.start()
        self.analyzeStateChanged.emit()

    def _on_guest_cookies(self, count: int, error: str) -> None:
        self._guest_busy = False
        if error:
            self.toast.emit("warning", "未能自动获取 Cookie", error)
        else:
            self._settings.set("guest_cookie_updated_at", time.time())
            self._settings.save()
            self.toast.emit("success", "已更新访客 Cookie",
                            f"共 {count} 项，可降低批量下载时的限流概率。")
        thread = self._guest_thread
        if thread is not None:
            thread.quit()
            thread.wait(3000)
            thread.deleteLater()
        self._guest_thread = None
        self.analyzeStateChanged.emit()

    def _on_thumb_ready(self, original: str, local: str) -> None:
        self._tasks.replaceThumb(original, local)
        self._history.replaceThumb(original, local)
        self.mediaThumbReady.emit(original, local)

    def _on_bili_changed(self) -> None:
        self.analyzeStateChanged.emit()

    # ------------------------------------------------------------------
    # 哔哩哔哩画质 / 音质 / 编码优先级
    # ------------------------------------------------------------------
    @Slot(result="QVariantList")
    def biliQualityTable(self) -> List[Dict[str, Any]]:
        return bili_format.quality_table()

    @Slot(result="QVariantList")
    def biliAudioTable(self) -> List[Dict[str, Any]]:
        return bili_format.audio_table()

    @Slot(result="QVariantList")
    def biliCodecTable(self) -> List[Dict[str, Any]]:
        return bili_format.codec_table()

    @Slot(result="QVariantList")
    def ytQualityTable(self) -> List[Dict[str, Any]]:
        return yt_format.quality_table()

    @Slot(result="QVariantList")
    def ytAudioTable(self) -> List[Dict[str, Any]]:
        return yt_format.audio_table()

    @Slot(result="QVariantList")
    def ytCodecTable(self) -> List[Dict[str, Any]]:
        return yt_format.codec_table()

    # 三张表各自的默认顺序：重置时用，也是补齐老配置时的依据
    _PRIORITY_DEFAULTS = {
        "bili_quality_order": bili_format.DEFAULT_QUALITY_ORDER,
        "bili_audio_order": bili_format.DEFAULT_AUDIO_ORDER,
        "bili_codec_order": bili_format.DEFAULT_CODEC_ORDER,
        "yt_quality_order": yt_format.DEFAULT_QUALITY_ORDER,
        "yt_audio_order": yt_format.DEFAULT_AUDIO_ORDER,
        "yt_codec_order": yt_format.DEFAULT_CODEC_ORDER,
    }

    def _move_priority(self, key: str, index: int, delta: int) -> None:
        """把优先级列表中的某一项上移或下移。"""
        if key not in self._PRIORITY_DEFAULTS:
            return
        items = list(self._settings.get(key) or self._PRIORITY_DEFAULTS[key])
        target = index + delta
        if index < 0 or index >= len(items) or target < 0 or target >= len(items):
            return
        items[index], items[target] = items[target], items[index]
        self.setSetting(key, items)

    def _reset_priority(self, key: str) -> None:
        if key in self._PRIORITY_DEFAULTS:
            self.setSetting(key, list(self._PRIORITY_DEFAULTS[key]))

    @Slot(str, int, int)
    def biliMovePriority(self, key: str, index: int, delta: int) -> None:
        self._move_priority(key, index, delta)

    @Slot(str)
    def biliResetPriority(self, key: str) -> None:
        self._reset_priority(key)

    @Slot(str, int, int)
    def ytMovePriority(self, key: str, index: int, delta: int) -> None:
        self._move_priority(key, index, delta)

    @Slot(str)
    def ytResetPriority(self, key: str) -> None:
        self._reset_priority(key)

    @Slot()
    def biliResetAll(self) -> None:
        for key in ("bili_quality_order", "bili_audio_order", "bili_codec_order"):
            self._reset_priority(key)

    @Slot()
    def _sync_ffmpeg(self) -> None:
        self._settings.set("_ffmpeg_resolved", self._deps.ffmpegDir)
        self.analyzeStateChanged.emit()

    def _on_dep_finished(self, kind: str, ok: bool, message: str) -> None:
        if kind == "check" or not message:
            return
        self.toast.emit("success" if ok else "error",
                        "组件已就绪" if ok else "组件操作失败", message)

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------
    @Property(str, constant=True)
    def appName(self) -> str:
        return APP_NAME

    @Property(str, constant=True)
    def appVersion(self) -> str:
        return __version__

    @Property(str, constant=True)
    def appTagline(self) -> str:
        return APP_TAGLINE

    @Property(str, constant=True)
    def ytdlpVersion(self) -> str:
        # 引擎缺失时返回「未安装」，界面照常可用（设置页可一键安装）
        return ytdlp_installed_version() if ytdlp_available() else "未安装"

    @Property(str, constant=True)
    def pythonVersion(self) -> str:
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    @Property(str, constant=True)
    def fontFamily(self) -> str:
        return self._font_family

    @Property(str, constant=True)
    def iconFamily(self) -> str:
        return self._icon_family

    @Property(bool, notify=analyzeStateChanged)
    def analyzing(self) -> bool:
        return self._analyzing

    @Property(str, notify=analyzeStateChanged)
    def lastAnalyzeUrl(self) -> str:
        """最近一次解析的链接。解析失败时界面上仍可据此判断站点。"""
        return self._last_analyze_url

    @Property(str, constant=True)
    def dataDir(self) -> str:
        return str(app_data_dir())

    @Property(bool, constant=True)
    def demoMode(self) -> bool:
        return bool(os.environ.get("LIUGUANG_DEMO"))

    @Property(bool, constant=True)
    def demoOpenFormat(self) -> bool:
        return bool(os.environ.get("LIUGUANG_DEMO_FORMAT"))

    @Property(bool, constant=True)
    def demoExpandSections(self) -> bool:
        return bool(os.environ.get("LIUGUANG_EXPAND"))

    @Property(bool, constant=True)
    def demoOpenLogin(self) -> bool:
        return bool(os.environ.get("LIUGUANG_DEMO_LOGIN"))

    @Property(bool, constant=True)
    def demoOpenBiliQuality(self) -> bool:
        return bool(os.environ.get("LIUGUANG_DEMO_BILI"))

    @Property(bool, constant=True)
    def demoOpenSubtitles(self) -> bool:
        return bool(os.environ.get("LIUGUANG_DEMO_SUBS"))

    @Property(int, constant=True)
    def demoScrollY(self) -> int:
        """仅用于截图/测试：把可滚动页面定位到指定位置。"""
        try:
            return max(0, int(os.environ.get("LIUGUANG_SCROLL_Y", "0")))
        except Exception:
            return 0

    @Property(int, constant=True)
    def startPage(self) -> int:
        try:
            return max(0, min(4, int(os.environ.get("LIUGUANG_PAGE", "0"))))
        except Exception:
            return 0

    @Slot()
    def seedDemo(self) -> None:
        """开发用：填充示例数据，便于检查界面。"""
        from .taskmodel import Task
        demo = [
            ("https://example.com/a", "【4K 修复版】城市夜景延时摄影 · 上海外滩", "光影工作室",
             TM.DOWNLOADING, 0.428, 268435456, 627048448, 5242880.0, 68, "1080P · MP4 · 完整音视频"),
            ("https://example.com/b", "深海纪录片：马里亚纳海沟全纪录", "自然观察",
             TM.DOWNLOADING, 0.873, 912680550, 1045426176, 3145728.0, 42, "4K · MP4 · H.265"),
            ("https://example.com/c", "钢琴曲集 · 安静的午后", "音乐频道",
             TM.QUEUED, 0.0, 0, 0, 0.0, None, "仅音频 · MP3"),
            ("https://example.com/d", "开源软件入门教程 第 12 讲", "代码实验室",
             TM.COMPLETED, 1.0, 134217728, 134217728, 0.0, None, "720P · MP4"),
            ("https://example.com/e", "旅行 Vlog · 川西环线第七天", "路过的风",
             TM.FAILED, 0.35, 52428800, 0, 0.0, None, "1080P · MP4"),
            ("https://example.com/g", "编程直播回放 · Rust 异步运行时剖析", "夜航船",
             TM.PAUSED, 0.312, 178257920, 571473920, 0.0, None, "1080P · MP4 · 完整音视频"),
        ]
        for url, title, uploader, status, prog, done, total, speed, eta, fmt in demo:
            task = Task(id=uuid.uuid4().hex[:12], url=url, title=title, uploader=uploader,
                        status=status, progress=prog, downloaded=done, total=total,
                        speed=speed, eta=eta, format_label=fmt,
                        audio_only=fmt.startswith("仅音频"),
                        kind="audio_only" if fmt.startswith("仅音频") else "complete")
            if status == TM.COMPLETED:
                task.filepath = str(Path(self._settings.get("output_dir")) / (title + ".mp4"))
                task.detail = "已完成"
                task.finished_at = time.time() - 320
                # 演示数据只放在内存里，不污染真实的历史记录文件
                self._history.add(task.as_history(), persist=False)
            elif status == TM.FAILED:
                task.error = "HTTP Error 403: Forbidden —— 该视频需要登录后才能下载，请在设置中配置 Cookies。"
                task.detail = "下载失败"
            elif status == TM.QUEUED:
                task.detail = ""
            elif status == TM.PAUSED:
                task.detail = "已暂停"
            self._tasks.add(task)
        self._history.add({
            "url": "https://example.com/f", "title": "纪录片 · 地球脉动 第二季 第一集",
            "uploader": "BBC Earth", "thumbnail": "", "filepath": "",
            "output_dir": self._settings.get("output_dir"), "total": 2147483648,
            "audio_only": False, "kind": "complete", "format_label": "4K",
            "finished_at": time.time() - 86400, "status": "completed",
        }, persist=False)

    @Property(str, constant=True)
    def defaultDir(self) -> str:
        return default_download_dir()

    @Property(str, notify=analyzeStateChanged)
    def ffmpegPath(self) -> str:
        return self._deps.ffmpegPath or "未检测到"

    @Property(bool, notify=analyzeStateChanged)
    def ffmpegAvailable(self) -> bool:
        return self._deps.ffmpegReady

    @Property(bool, constant=True)
    def systemDark(self) -> bool:
        try:
            from PySide6.QtCore import Qt
            hints = QGuiApplication.styleHints()
            return hints.colorScheme() == Qt.ColorScheme.Dark
        except Exception:
            return True

    # ------------------------------------------------------------------
    # 解析
    # ------------------------------------------------------------------
    @Slot(str)
    def analyze(self, text: str) -> None:
        urls = self.extractUrls(text)
        if not urls:
            self.mediaFailed.emit("没有检测到有效的链接", "请粘贴以 http:// 或 https:// 开头的完整链接。", "")
            return
        self._start_analyze(urls[0])

    def _start_analyze(self, url: str) -> None:
        if self._analyzing:
            return
        self._analyzing = True
        self._last_analyze_url = url
        self.analyzeStateChanged.emit()
        self._analyzer.start(url)

    @Slot()
    def reanalyze(self) -> None:
        if self._last_analyze_url:
            self._start_analyze(self._last_analyze_url)

    @Slot()
    def cancelAnalyze(self) -> None:
        self._analyzing = False
        self.analyzeStateChanged.emit()

    def _on_analyze_done(self, url: str, payload: Dict[str, Any]) -> None:
        self._analyzing = False
        self.analyzeStateChanged.emit()
        payload["sourceUrl"] = url
        # 封面大多带防盗链，交给后台线程带正确的 Referer 下载到本地缓存
        referer = str(payload.get("webpage_url") or url)
        thumb = str(payload.get("thumbnail") or "")
        payload["thumbnailLocal"] = self._thumbs.request(thumb, referer) if thumb else ""
        self.mediaReady.emit(payload)

    def _on_analyze_failed(self, url: str, message: str) -> None:
        self._analyzing = False
        self.analyzeStateChanged.emit()
        parts = str(message).split("\x00")
        title = parts[0] if parts else "解析失败"
        hint = parts[1] if len(parts) > 1 else ""
        raw = parts[2] if len(parts) > 2 else ""
        self.mediaFailed.emit(title, hint, raw)

    @Slot(str, result="QVariantList")
    def extractUrls(self, text: str) -> List[str]:
        if not text:
            return []
        found = URL_RE.findall(text)
        cleaned: List[str] = []
        for item in found:
            item = item.strip().rstrip(_TRAILING)
            if item and item not in cleaned:
                cleaned.append(item)
        if not cleaned:
            plain = text.strip()
            if plain and " " not in plain and "." in plain and "/" not in plain[:1]:
                cleaned = ["https://" + plain]
        return cleaned

    # ------------------------------------------------------------------
    # 下载
    # ------------------------------------------------------------------
    def _task_from_spec(self, spec: Dict[str, Any]) -> Task | None:
        url = str(spec.get("url") or "").strip()
        if not url:
            return None
        audio_only = bool(spec.get("audioOnly"))
        format_id = str(spec.get("formatId") or "")
        kind = str(spec.get("kind") or "").strip()
        if not kind:
            if audio_only:
                kind = "audio_only"
            elif "+" in format_id:
                kind = "complete"
            else:
                kind = "complete"
        return Task(
            id=uuid.uuid4().hex[:12],
            url=url,
            title=str(spec.get("title") or "正在解析…"),
            uploader=str(spec.get("uploader") or ""),
            thumbnail=str(spec.get("thumbnail") or ""),
            duration=float(spec.get("duration") or 0),
            audio_only=audio_only,
            preset=str(spec.get("preset") or ("audio" if audio_only else "best")),
            format_id=format_id,
            format_label=str(spec.get("formatLabel")
                              or ("仅音频" if audio_only else "自动选择最佳画质")),
            output_dir=str(spec.get("outputDir") or self._settings.get("output_dir")),
            playlist_index=int(spec.get("playlistIndex") or 0),
            playlist_count=int(spec.get("playlistCount") or 0),
            sub_langs=_join_list(spec.get("subLangs")),
            sub_format=str(spec.get("subFormat") or ""),
            cover_mode=str(spec.get("coverMode") or ""),
            anonymous=bool(spec.get("anonymous")),
            kind=kind,
        )

    @Slot("QVariantMap", result=str)
    def startDownload(self, spec: Dict[str, Any]) -> str:
        task = self._task_from_spec(spec)
        if task is None:
            return ""
        self._engine.enqueue(task)
        return task.id

    @Slot("QVariantList", result=int)
    def startBatch(self, specs: List[Dict[str, Any]]) -> int:
        count = 0
        for spec in specs or []:
            if not isinstance(spec, dict):
                continue
            task = self._task_from_spec(spec)
            if task is not None:
                self._engine.enqueue(task)
                count += 1
        return count

    def _on_task_done(self, task_id: str, *_args: Any) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        if task.thumbnail and not task.thumbnail.startswith("file://"):
            self._thumbs.request(task.thumbnail, task.url)
        if task.status == TM.COMPLETED:
            self._history.add(task.as_history())
            self.taskDone.emit(task_id, task.title, "completed", "")
            if self._settings.get("open_folder_when_done") and task.filepath:
                open_in_explorer(task.filepath, select=True)
        elif task.status == TM.CANCELED:
            self.taskDone.emit(task_id, task.title, "canceled", "")
        else:
            self.taskDone.emit(task_id, task.title, "failed", task.error_kind or "下载失败")

    @Slot(str)
    def cancelTask(self, task_id: str) -> None:
        self._engine.cancel(task_id)

    @Slot(str)
    def retryTask(self, task_id: str) -> None:
        self._engine.retry(task_id)

    @Slot(str)
    def pauseTask(self, task_id: str) -> None:
        self._engine.pause(task_id)

    @Slot(str)
    def resumeTask(self, task_id: str) -> None:
        self._engine.resume(task_id)

    @Slot(str)
    def removeTask(self, task_id: str) -> None:
        self._tasks.remove(task_id)

    @Slot()
    def clearFinished(self) -> None:
        self._tasks.clearFinished()

    @Slot()
    def clearTasks(self) -> None:
        self._tasks.clearAll()

    @Slot(str, "QVariantMap")
    def updateTask(self, task_id: str, patch: Dict[str, Any]) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        for key in ("preset", "format_id", "format_label", "output_dir"):
            if key in patch:
                setattr(task, key, patch[key])
        if "audio_only" in patch:
            task.audio_only = bool(patch["audio_only"])
        self._tasks.touch(task_id)

    @Slot()
    def cancelAll(self) -> None:
        self._engine.cancelAll()

    @Slot(result="QVariantMap")
    def stats(self) -> Dict[str, Any]:
        data = self._engine.stats()
        data["speedText"] = (human_size(data.get("speed")) + "/s") if data.get("speed") else "空闲"
        data["remainingText"] = human_size(data.get("remaining")) if data.get("remaining") else "0 B"
        return data

    @Slot(str, result="QVariantMap")
    def taskDetail(self, task_id: str) -> Dict[str, Any]:
        task = self._tasks.get(task_id)
        if task is None:
            return {}
        return {
            "id": task.id,
            "url": task.url,
            "title": task.title,
            "uploader": task.uploader,
            "thumbnail": task.thumbnail,
            "status": task.status,
            "error": task.error,
            "filepath": task.filepath,
            "outputDir": task.output_dir,
            "formatLabel": task.format_label,
            "playlistLabel": f"第 {task.playlist_index}/{task.playlist_count} 项" if task.playlist_count else "",
            "durationText": "",
            "log": "\n".join(task.extra.get("log", [])[-40:]),
        }

    # ------------------------------------------------------------------
    # 系统交互
    # ------------------------------------------------------------------
    @Slot(str)
    def openFolder(self, path: str) -> None:
        if path:
            open_in_explorer(path)

    @Slot(str)
    def revealFile(self, path: str) -> None:
        if path:
            open_in_explorer(path, select=True)

    @Slot(str)
    def openUrl(self, url: str) -> None:
        if not url:
            return
        try:
            os.startfile(url)  # type: ignore[attr-defined]
        except Exception:
            try:
                subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)
            except Exception:
                pass

    @Slot(result=str)
    def pasteFromClipboard(self) -> str:
        return QGuiApplication.clipboard().text() or ""

    @Slot(str)
    def copyText(self, text: str) -> None:
        QGuiApplication.clipboard().setText(text or "")

    @Slot(str, result=str)
    def detectClipboardUrl(self, current: str) -> str:
        urls = self.extractUrls(QGuiApplication.clipboard().text() or "")
        if urls and urls[0] != current:
            self.clipboardUrl.emit(urls[0])
            return urls[0]
        return ""

    @Slot(result=str)
    def chooseDirectoryDialog(self) -> str:
        from PySide6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(
            None, "选择保存目录", str(self._settings.get("output_dir")))
        return path or ""

    @Slot(str, result=str)
    def pickFile(self, kind: str) -> str:
        from PySide6.QtWidgets import QFileDialog
        if kind == "cookies":
            path, _ = QFileDialog.getOpenFileName(
                None, "选择 Cookies 文件", "",
                "Cookies 文件 (*.txt *.json);;所有文件 (*.*)")
            return path or ""
        if kind == "folder":
            return QFileDialog.getExistingDirectory(
                None, "选择目录", str(self._settings.get("output_dir"))) or ""
        if kind == "ffmpeg":
            # 只弹一个目录选择框：FFmpeg 压缩包解压后是 ffmpeg-x.y/bin/ffmpeg.exe，
            # 选到哪一层都会被 normalize_ffmpeg_dir 自动定位，也可以直接粘贴 exe 路径。
            return QFileDialog.getExistingDirectory(None, "选择 FFmpeg 所在的文件夹", "C:\\") or ""
        if kind == "history":
            path, _ = QFileDialog.getSaveFileName(
                None, "导出历史记录", "下载历史.csv", "CSV 文件 (*.csv)")
            return path or ""
        return ""

    # ------------------------------------------------------------------
    # 设置
    # ------------------------------------------------------------------
    @Slot(str, "QVariant")
    def setSetting(self, key: str, value: Any) -> None:
        self._settings.set(key, value)
        self._settings.save()

    @Slot(result="QVariantMap")
    def allSettings(self) -> Dict[str, Any]:
        return self._settings.all()

    @Slot()
    def resetSettings(self) -> None:
        self._settings.reset()

    @Slot(result=bool)
    def ffmpegCheck(self) -> bool:
        return bool(shutil.which("ffmpeg"))

    @Slot(result="QVariantList")
    def qualityPresets(self) -> List[Dict[str, str]]:
        return [
            {"key": "best", "label": "最佳画质", "desc": "自动挑选最高画质与音质"},
            {"key": "2160", "label": "4K", "desc": "2160p 及以下"},
            {"key": "1440", "label": "2K", "desc": "1440p 及以下"},
            {"key": "1080", "label": "1080P", "desc": "全高清"},
            {"key": "720", "label": "720P", "desc": "高清"},
            {"key": "480", "label": "480P", "desc": "标清"},
            {"key": "360", "label": "360P", "desc": "流畅"},
            {"key": "worst", "label": "最小体积", "desc": "占用空间最小"},
        ]

    # ------------------------------------------------------------------
    @Slot(str, str, str)
    def notify(self, level: str, title: str, message: str) -> None:
        self.toast.emit(level, title, message)

    @Slot(int, bool, result=str)
    def removeHistory(self, row: int, delete_file: bool) -> str:
        """删除一条历史记录，可选择同时删除本地文件。"""
        items = self._history.allItems()
        if row < 0 or row >= len(items):
            self._history.removeAt(row)
            return ""
        item = items[row]
        message = ""
        if delete_file:
            path = Path(str(item.get("filepath") or ""))
            try:
                if path.is_file():
                    path.unlink()
                    message = f"已删除文件 {path.name}"
                else:
                    message = "本地文件已不存在，仅删除了记录"
            except Exception as exc:  # noqa: BLE001
                message = f"删除文件失败：{exc}"
        self._history.removeAt(row)
        return message

    @Slot(str, result=str)
    def exportHistory(self, path: str) -> str:
        if not path:
            return ""
        items = self._history.allItems()
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.writer(fh)
                writer.writerow(["标题", "上传者", "链接", "文件位置", "大小(字节)", "完成时间"])
                for it in items:
                    writer.writerow([
                        it.get("title", ""), it.get("uploader", ""), it.get("url", ""),
                        it.get("filepath", ""), it.get("total", 0), it.get("finished_at", ""),
                    ])
        except Exception as exc:  # noqa: BLE001
            return f"导出失败：{exc}"
        return path

    @Slot()
    def quit(self) -> None:
        self._settings.save()
        self._history.save()
        QGuiApplication.quit()
