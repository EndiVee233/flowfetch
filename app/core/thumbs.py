"""封面缓存。

yt-dlp 给出的封面地址大多带防盗链（哔哩哔哩的 i0.hdslb.com 必须带
Referer 才能访问），QML 的 Image 直接加载会失败。这里统一由 Python
带正确的请求头下载到本地缓存，界面上再引用本地文件。
"""
from __future__ import annotations

import hashlib
import ssl
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QObject, Signal

from .helpers import app_data_dir

CACHE_DIR = app_data_dir() / "cache" / "thumbs"
MAX_FILES = 400
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

_refs: Dict[str, str] = {}          # 原始地址 -> 本地 file:// 地址
_lock = threading.Lock()


def referer_for(url: str) -> str:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if "hdslb" in host or "bilibili" in host:
        return "https://www.bilibili.com/"
    if "ytimg" in host or "ggpht" in host or "youtube" in host:
        return "https://www.youtube.com/"
    return ""


def _file_for(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8", "replace")).hexdigest()[:20]
    ext = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"):
        ext = ".jpg"
    return CACHE_DIR / f"{digest}{ext}"


def _to_file_url(path: Path) -> str:
    return "file:///" + str(path).replace("\\", "/")


def cached_url(url: str) -> str:
    """如果本地已有缓存就返回本地地址，否则原样返回网络地址。"""
    if not url:
        return ""
    if url.startswith("file://"):
        return url
    cached = _refs.get(url)
    if cached:
        return cached
    path = _file_for(url)
    try:
        if path.is_file() and path.stat().st_size > 0:
            value = _to_file_url(path)
            with _lock:
                _refs[url] = value
            return value
    except OSError:
        pass
    return url


def _trim_cache() -> None:
    try:
        files = sorted(CACHE_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[MAX_FILES:]:
            old.unlink(missing_ok=True)
    except Exception:
        pass


def fetch(url: str, referer: str = "", timeout: int = 20) -> str:
    """下载封面到本地缓存，返回本地 file:// 地址；失败返回空串。"""
    if not url:
        return ""
    if url.startswith("file://"):
        return url

    path = _file_for(url)
    try:
        if path.is_file() and path.stat().st_size > 0:
            return cached_url(url)
    except OSError:
        pass

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url)
        request.add_header("User-Agent", UA)
        request.add_header("Accept", "image/avif,image/webp,image/png,image/*,*/*;q=0.8")
        ref = referer or referer_for(url)
        if ref:
            request.add_header("Referer", ref)
        with urllib.request.urlopen(request, timeout=timeout,
                                    context=ssl.create_default_context()) as resp:
            data = resp.read()
        if not data:
            return ""
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(path)
        value = _to_file_url(path)
        with _lock:
            _refs[url] = value
        _trim_cache()
        return value
    except Exception:
        return ""


class ThumbFetcher(QObject):
    """后台批量取封面。"""

    ready = Signal(str, str)   # 原始地址, 本地地址

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pending: set[str] = set()

    def request(self, url: str, referer: str = "") -> str:
        """立即返回当前可用的地址；没有缓存时在后台下载并在完成后发信号。"""
        if not url:
            return ""
        cached = cached_url(url)
        if cached != url:
            return cached
        with _lock:
            if url in self._pending:
                return url
            self._pending.add(url)
        threading.Thread(target=self._worker, args=(url, referer), daemon=True,
                         name="thumb").start()
        return url

    def _worker(self, url: str, referer: str) -> None:
        local = fetch(url, referer)
        with _lock:
            self._pending.discard(url)
        if local:
            self.ready.emit(url, local)
