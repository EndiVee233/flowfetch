"""外部组件（FFmpeg / yt-dlp）的检测、下载与更新。

本程序不依赖系统 PATH 中的 FFmpeg：优先使用程序自带的组件目录，
缺少时会自动下载到用户配置目录下。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, Property, Signal, Slot

from .. import MANAGED_LIB_DIR
from .helpers import app_data_dir, app_root, is_windows

BIN_DIR = app_data_dir() / "bin"
LIB_DIR = MANAGED_LIB_DIR
IS_WIN = is_windows()
FFMPEG_EXE = "ffmpeg.exe" if IS_WIN else "ffmpeg"
FFPROBE_EXE = "ffprobe.exe" if IS_WIN else "ffprobe"

# FFmpeg 自动下载源，按顺序尝试
FFMPEG_SOURCES: List[Tuple[str, str]] = [
    ("gyan.dev", "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"),
    ("BtbN", "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
             "ffmpeg-master-latest-win64-gpl.zip"),
]
YTDLP_PYPI = "https://pypi.org/pypi/yt-dlp/json"
USER_AGENT = "YtDlpGui/1.0 (+desktop)"
TIMEOUT = 20


# ----------------------------------------------------------------------
# 基础工具
# ----------------------------------------------------------------------
def _ssl_context() -> ssl.SSLContext:
    try:
        return ssl.create_default_context()
    except Exception:
        return ssl._create_unverified_context()  # type: ignore[attr-defined]


def _request(url: str, method: str = "GET", headers: Optional[Dict[str, str]] = None):
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", USER_AGENT)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    return urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_context())


def _version_tuple(text: str) -> Tuple:
    parts = re.findall(r"\d+", text or "")
    return tuple(int(p) for p in parts[:6]) if parts else ()


def _human_size(num: float) -> str:
    units = ("B", "KB", "MB", "GB")
    idx = 0
    while num >= 1024 and idx < len(units) - 1:
        num /= 1024.0
        idx += 1
    return f"{num:.1f} {units[idx]}" if idx else f"{int(num)} B"


def normalize_ffmpeg_dir(raw: str) -> str:
    """把用户填写的路径规范成“包含 ffmpeg 可执行文件的目录”。

    允许直接指向 ffmpeg.exe / ffmpeg 本身。
    """
    if not raw:
        return ""
    p = Path(str(raw).strip().strip('"'))
    if not p.exists():
        return str(p)
    if p.is_file():
        return str(p.parent)
    if (p / FFMPEG_EXE).is_file():
        return str(p)
    nested = p / "bin"
    if (nested / FFMPEG_EXE).is_file():
        return str(nested)
    return str(p)


def probe_dir_ok(folder: str) -> bool:
    try:
        return bool(folder) and (Path(folder) / FFMPEG_EXE).is_file()
    except OSError:
        return False


def candidate_bin_dirs(configured: str = "", mode: str = "managed") -> List[Tuple[str, str]]:
    """返回 (目录, 来源说明) 列表，按优先级排列。

    不使用系统 PATH。managed 模式下只认本程序管理的目录；
    custom 模式下优先使用用户指定的目录，并在其失效时回退。
    """
    if mode == "custom":
        folder = normalize_ffmpeg_dir(configured)
        if probe_dir_ok(folder):
            return [(folder, "自定义路径")]
        # 自定义路径无效时不静默失败：回退到托管目录，并在界面上给出警告
        return [(str(BIN_DIR), "程序组件目录"), (str(app_root() / "bin"), "安装目录")]
    return [(str(BIN_DIR), "程序组件目录"), (str(app_root() / "bin"), "安装目录")]


def system_ffmpeg() -> str:
    """仅供界面提示：系统 PATH 中的 FFmpeg（本程序不会自动使用）。"""
    return shutil.which("ffmpeg") or ""


def ensure_package(name: str, import_name: str = "") -> bool:
    """确保某个纯 Python 包可用；缺失时从 PyPI 安装到程序组件目录。

    这样即使把程序打包分发，也不依赖用户环境里是否装过这些库。
    """
    import importlib
    import sys as _sys

    import_name = import_name or name.replace("-", "_")
    try:
        importlib.import_module(import_name)
        return True
    except Exception:
        pass

    try:
        with _request(f"https://pypi.org/pypi/{name}/json") as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
        url = ""
        for item in (data.get("urls") or []):
            fname = str(item.get("filename") or "")
            if item.get("packagetype") == "bdist_wheel" and fname.endswith(".whl"):
                url = str(item.get("url") or "")
                break
        if not url:
            return False
        LIB_DIR.mkdir(parents=True, exist_ok=True)
        archive = LIB_DIR / f"{name}-download.whl"
        with _request(url) as resp, open(archive, "wb") as fh:
            shutil.copyfileobj(resp, fh, 1024 * 256)
        DependencyManager._unpack_wheel(archive, {import_name})
        try:
            archive.unlink()
        except OSError:
            pass
        if str(LIB_DIR) not in _sys.path:
            _sys.path.insert(0, str(LIB_DIR))
        importlib.invalidate_caches()
        importlib.import_module(import_name)
        return True
    except Exception:
        return False


def resolve_ffmpeg(configured: str = "", mode: str = "managed") -> Tuple[str, str, str]:
    """返回 (ffmpeg 目录, ffmpeg 可执行文件路径, 来源说明)。"""
    for folder, label in candidate_bin_dirs(configured, mode):
        exe = Path(folder) / FFMPEG_EXE
        try:
            if exe.is_file():
                return folder, str(exe), label
        except OSError:
            continue
    return "", "", ""


def probe_ffmpeg_version(exe: str) -> str:
    if not exe:
        return ""
    try:
        flags = 0x08000000 if IS_WIN else 0  # CREATE_NO_WINDOW
        out = subprocess.run([exe, "-version"], capture_output=True, text=True,
                             timeout=15, creationflags=flags, encoding="utf-8",
                             errors="replace")
        first = (out.stdout or "").splitlines()[0] if out.stdout else ""
        match = re.search(r"ffmpeg version (\S+)", first)
        return match.group(1) if match else first.strip()[:40]
    except Exception:
        return ""


# ----------------------------------------------------------------------
class DependencyManager(QObject):
    """检测、下载与更新外部组件。"""

    changed = Signal()
    progress = Signal(str, int, str)      # 组件, 百分比, 说明
    finished = Signal(str, bool, str)     # 组件, 是否成功, 说明

    def __init__(self, settings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._busy = ""
        self._percent = 0
        self._message = ""
        self._ytdlp_latest = ""
        self._ffmpeg_latest = ""
        self._ffmpeg_dir = ""
        self._ffmpeg_exe = ""
        self._ffmpeg_source = ""
        self._ffmpeg_version = ""
        self._ffmpeg_mode = "managed"
        self._ffmpeg_custom_dir = ""
        self._ffmpeg_custom_ok = False
        self._refresh_local()

    # ------------------------------------------------------------------
    def _refresh_local(self) -> None:
        self._ffmpeg_mode = str(self._settings.get("ffmpeg_mode") or "managed")
        configured = str(self._settings.get("ffmpeg_dir") or "")
        self._ffmpeg_custom_dir = normalize_ffmpeg_dir(configured)
        self._ffmpeg_custom_ok = probe_dir_ok(self._ffmpeg_custom_dir)
        self._ffmpeg_dir, self._ffmpeg_exe, self._ffmpeg_source = resolve_ffmpeg(
            configured, self._ffmpeg_mode)
        self._ffmpeg_version = probe_ffmpeg_version(self._ffmpeg_exe)
        if not self._ffmpeg_version and self._ffmpeg_exe:
            self._ffmpeg_version = "未知版本"
        self.changed.emit()

    @Slot()
    def refresh(self) -> None:
        self._refresh_local()

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------
    @Property(bool, notify=changed)
    def ffmpegReady(self) -> bool:
        return bool(self._ffmpeg_exe)

    @Property(str, notify=changed)
    def ffmpegPath(self) -> str:
        return self._ffmpeg_exe or ""

    @Property(str, notify=changed)
    def ffmpegDir(self) -> str:
        return self._ffmpeg_dir or ""

    @Property(str, notify=changed)
    def ffmpegVersion(self) -> str:
        return self._ffmpeg_version or ""

    @Property(str, notify=changed)
    def ffmpegSource(self) -> str:
        return self._ffmpeg_source or ""

    @Property(str, notify=changed)
    def ffmpegStatusText(self) -> str:
        if not self._ffmpeg_exe:
            return "未安装"
        return f"{self._ffmpeg_version}（{self._ffmpeg_source}）"

    @Property(bool, notify=changed)
    def ffmpegOutdated(self) -> bool:
        return bool(self._ffmpeg_latest) and self._is_ffmpeg_outdated()

    def _is_ffmpeg_outdated(self) -> bool:
        stamp = float(self._settings.get("ffmpeg_remote_stamp") or 0)
        local = float(self._settings.get("ffmpeg_downloaded_at") or 0)
        return bool(stamp) and bool(local) and stamp > local + 3600

    @Property(str, notify=changed)
    def binDir(self) -> str:
        return str(BIN_DIR)

    @Property(str, notify=changed)
    def systemFfmpeg(self) -> str:
        return system_ffmpeg()

    # ---- FFmpeg 模式 -------------------------------------------------
    @Property(str, notify=changed)
    def ffmpegMode(self) -> str:
        return self._ffmpeg_mode

    @Property(bool, notify=changed)
    def ffmpegManaged(self) -> bool:
        return self._ffmpeg_mode != "custom"

    @Property(str, notify=changed)
    def ffmpegCustomDir(self) -> str:
        return self._ffmpeg_custom_dir

    @Property(bool, notify=changed)
    def ffmpegCustomValid(self) -> bool:
        return bool(self._ffmpeg_custom_ok)

    @Property(str, notify=changed)
    def ffmpegCustomStatus(self) -> str:
        if not self._ffmpeg_custom_dir:
            return "尚未选择路径"
        if not Path(self._ffmpeg_custom_dir).exists():
            return "找不到该路径"
        if not self._ffmpeg_custom_ok:
            return f"该目录下没有 {FFMPEG_EXE}"
        ver = probe_ffmpeg_version(str(Path(self._ffmpeg_custom_dir) / FFMPEG_EXE))
        return ("已检测到 " + ver) if ver else "已找到 ffmpeg，但无法读取版本"

    @Property(str, notify=changed)
    def ffmpegWarning(self) -> str:
        """自定义路径失效时的提示。"""
        if self._ffmpeg_mode == "custom" and not self._ffmpeg_custom_ok:
            return ("自定义的 FFmpeg 路径不可用，当前已回退到程序组件目录。"
                    "请重新选择，或改回“由本程序管理”。")
        return ""

    @Slot(str)
    def setMode(self, mode: str) -> None:
        mode = "custom" if mode == "custom" else "managed"
        self._settings.set("ffmpeg_mode", mode)
        self._settings.save()
        self._refresh_local()

    @Slot(str)
    def setCustomDir(self, path: str) -> None:
        self._settings.set("ffmpeg_dir", path or "")
        if not path:
            # 清空路径时自动回到托管模式，避免留下无效配置
            self._settings.set("ffmpeg_mode", "managed")
        else:
            self._settings.set("ffmpeg_mode", "custom")
        self._settings.save()
        self._refresh_local()

    @Slot(str, result="QVariantMap")
    def probeCustomPath(self, path: str) -> Dict[str, Any]:
        """用户浏览选择后立即给出校验结果。"""
        folder = normalize_ffmpeg_dir(path)
        ok = probe_dir_ok(folder)
        version = probe_ffmpeg_version(str(Path(folder) / FFMPEG_EXE)) if ok else ""
        return {"dir": folder, "ok": ok, "version": version}

    # ---- yt-dlp ------------------------------------------------------
    @Property(str, notify=changed)
    def ytdlpVersion(self) -> str:
        try:
            import yt_dlp
            return str(yt_dlp.version.__version__)
        except Exception:
            return "未安装"

    @Property(str, notify=changed)
    def ytdlpSourceText(self) -> str:
        """说明当前 yt-dlp 来自程序自带的组件目录，还是系统中的 pip 安装。"""
        try:
            import yt_dlp
            path = Path(yt_dlp.__file__).resolve()
        except Exception:
            return "未安装"
        try:
            path.relative_to(LIB_DIR.resolve())
            return "程序组件"
        except Exception:
            return "系统 Python 环境"

    @Property(str, notify=changed)
    def ytdlpLatest(self) -> str:
        return self._ytdlp_latest

    @Property(bool, notify=changed)
    def ytdlpOutdated(self) -> bool:
        if not self._ytdlp_latest:
            return False
        return _version_tuple(self._ytdlp_latest) > _version_tuple(self.ytdlpVersion)

    @Property(str, notify=changed)
    def ytdlpStatusText(self) -> str:
        if self.ytdlpOutdated:
            return f"已安装 {self.ytdlpVersion}，最新 {self._ytdlp_latest}"
        if self._ytdlp_latest:
            return f"{self.ytdlpVersion}（已是最新）"
        return self.ytdlpVersion

    # ---- 任务状态 ----------------------------------------------------
    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return bool(self._busy)

    @Property(str, notify=changed)
    def busyKind(self) -> str:
        return self._busy

    @Property(int, notify=changed)
    def busyPercent(self) -> int:
        return self._percent

    @Property(str, notify=changed)
    def busyMessage(self) -> str:
        return self._message

    @Property(bool, notify=changed)
    def updateAvailable(self) -> bool:
        return self.ytdlpOutdated or self.ffmpegOutdated

    @Property(str, notify=changed)
    def updateSummary(self) -> str:
        parts = []
        if self.ytdlpOutdated:
            parts.append(f"yt-dlp {self._ytdlp_latest}")
        if self.ffmpegOutdated:
            parts.append("FFmpeg 新版本")
        return "、".join(parts)

    # ------------------------------------------------------------------
    # 更新检查
    # ------------------------------------------------------------------
    @Slot(bool)
    def checkUpdates(self, force: bool = False) -> None:
        if self._busy:
            return
        last = float(self._settings.get("last_update_check") or 0)
        if not force and time.time() - last < 24 * 3600:
            return
        threading.Thread(target=self._check_worker, daemon=True,
                         name="dep-check").start()

    def _check_worker(self) -> None:
        ytdlp_latest = ""
        ffmpeg_stamp = 0.0
        try:
            with _request(YTDLP_PYPI) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
            ytdlp_latest = str((data.get("info") or {}).get("version") or "")
        except Exception:
            pass
        try:
            req = urllib.request.Request(FFMPEG_SOURCES[0][1], method="HEAD")
            req.add_header("User-Agent", USER_AGENT)
            with urllib.request.urlopen(req, timeout=TIMEOUT,
                                        context=_ssl_context()) as resp:
                stamp = resp.headers.get("Last-Modified")
            if stamp:
                ffmpeg_stamp = time.mktime(time.strptime(stamp, "%a, %d %b %Y %H:%M:%S %Z"))
        except Exception:
            pass

        self._ytdlp_latest = ytdlp_latest
        if ffmpeg_stamp:
            self._ffmpeg_latest = "remote"
            self._settings.set("ffmpeg_remote_stamp", ffmpeg_stamp)
        self._settings.set("last_update_check", time.time())
        self._settings.save()
        self.changed.emit()
        self.finished.emit("check", True, "")

    # ------------------------------------------------------------------
    # FFmpeg 安装 / 更新
    # ------------------------------------------------------------------
    @Slot()
    def installFfmpeg(self) -> None:
        if self._busy:
            return
        threading.Thread(target=self._install_ffmpeg_worker, daemon=True,
                         name="ffmpeg-install").start()

    def _set_busy(self, kind: str, percent: int, message: str) -> None:
        self._busy = kind
        self._percent = percent
        self._message = message
        self.progress.emit(kind, percent, message)
        self.changed.emit()

    def _install_ffmpeg_worker(self) -> None:
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        archive = BIN_DIR / "ffmpeg-download.zip"
        last_error = ""
        for name, url in FFMPEG_SOURCES:
            try:
                self._set_busy("ffmpeg", 0, f"正在从 {name} 下载 FFmpeg…")
                self._download(url, archive, "ffmpeg")
                self._set_busy("ffmpeg", 92, "正在解压组件…")
                self._extract_ffmpeg(archive)
                self._set_busy("ffmpeg", 99, "正在校验…")
                try:
                    archive.unlink()
                except OSError:
                    pass
                self._settings.set("ffmpeg_downloaded_at", time.time())
                self._settings.set("ffmpeg_remote_stamp", 0)
                self._settings.set("ffmpeg_dir", "")
                self._settings.save()
                self._refresh_local()
                self._busy = ""
                self._percent = 100
                self._message = ""
                self.changed.emit()
                self.finished.emit("ffmpeg", True, f"FFmpeg {self._ffmpeg_version} 已就绪")
                return
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                continue
        self._busy = ""
        self._message = ""
        self.changed.emit()
        self.finished.emit("ffmpeg", False, f"下载失败：{last_error}")

    def _download(self, url: str, target: Path, kind: str) -> None:
        tmp = Path(str(target) + ".part")
        started = time.monotonic()
        with _request(url) as resp, open(tmp, "wb") as fh:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            last_emit = 0.0
            while True:
                chunk = resp.read(262144)
                if not chunk:
                    break
                fh.write(chunk)
                done += len(chunk)
                now = time.monotonic()
                if now - last_emit > 0.4:
                    last_emit = now
                    elapsed = max(now - started, 0.1)
                    speed = done / elapsed
                    if total:
                        pct = int(done * 90 / total)
                        left = (total - done) / max(speed, 1)
                        self._set_busy(
                            kind, pct,
                            f"正在下载… {_human_size(done)} / {_human_size(total)}"
                            f"（{_human_size(speed)}/s，剩余约 {int(left // 60)} 分 {int(left % 60)} 秒）")
                    else:
                        self._set_busy(kind, 45,
                                       f"正在下载… {_human_size(done)}（{_human_size(speed)}/s）")
        if total and tmp.stat().st_size < total * 0.98:
            raise RuntimeError("下载未完成，请检查网络连接后重试")
        os.replace(tmp, target)

    def _extract_ffmpeg(self, archive: Path) -> None:
        wanted = {FFMPEG_EXE.lower(), FFPROBE_EXE.lower()}
        found = 0
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                name = Path(info.filename).name.lower()
                if name in wanted:
                    with zf.open(info) as src, open(BIN_DIR / Path(info.filename).name, "wb") as dst:
                        shutil.copyfileobj(src, dst, 1024 * 512)
                    found += 1
        if found == 0:
            raise RuntimeError("压缩包中未找到 ffmpeg.exe")

    # ------------------------------------------------------------------
    # yt-dlp 更新
    # ------------------------------------------------------------------
    @Slot()
    def updateYtdlp(self) -> None:
        if self._busy:
            return
        threading.Thread(target=self._update_ytdlp_worker, daemon=True,
                         name="ytdlp-update").start()

    def _update_ytdlp_worker(self) -> None:
        """下载 yt-dlp 官方 wheel 并解压到程序组件目录。

        不依赖 pip，也不修改用户的 Python 环境，因此在打包分发后同样可用。
        """
        self._set_busy("ytdlp", 3, "正在获取 yt-dlp 的最新版本信息…")
        wheel_url = ""
        version = ""
        try:
            with _request(YTDLP_PYPI) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
            version = str((data.get("info") or {}).get("version") or "")
            for item in (data.get("urls") or []):
                name = str(item.get("filename") or "")
                if item.get("packagetype") == "bdist_wheel" and name.endswith(".whl"):
                    wheel_url = str(item.get("url") or "")
                    break
        except Exception as exc:  # noqa: BLE001
            self._finish_busy()
            self.finished.emit("ytdlp", False, f"无法获取版本信息：{exc}")
            return

        if not wheel_url:
            self._finish_busy()
            self._fallback_pip_update()
            return

        archive = LIB_DIR / "yt-dlp-download.whl"
        LIB_DIR.mkdir(parents=True, exist_ok=True)
        try:
            self._set_busy("ytdlp", 5, f"正在下载 yt-dlp {version}…")
            self._download(wheel_url, archive, "ytdlp")
            self._set_busy("ytdlp", 92, "正在安装组件…")
            self._install_wheel(archive)
        except Exception as exc:  # noqa: BLE001
            try:
                archive.unlink()
            except OSError:
                pass
            self._finish_busy()
            self.finished.emit("ytdlp", False, f"更新失败：{exc}")
            return

        try:
            archive.unlink()
        except OSError:
            pass
        self._settings.set("ytdlp_updated_at", time.time())
        self._settings.set("ytdlp_installed_version", version)
        self._settings.save()
        self._finish_busy()
        self._percent = 100
        self.changed.emit()
        self.finished.emit("ytdlp", True, f"yt-dlp {version} 已安装，重新启动程序后生效")

    def _finish_busy(self) -> None:
        self._busy = ""
        self._message = ""
        self.changed.emit()

    def _install_wheel(self, wheel: Path) -> None:
        self._unpack_wheel(wheel, {"yt_dlp"})

    @staticmethod
    def _unpack_wheel(wheel: Path, packages: set) -> int:
        """把 wheel 中指定的包与元数据解压到组件目录，返回移动的条目数。"""
        staging = LIB_DIR / "_staging"
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(wheel) as zf:
            zf.extractall(staging)
        moved = 0
        for entry in list(staging.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name not in packages and not entry.name.endswith(".dist-info"):
                continue
            target = LIB_DIR / entry.name
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            shutil.move(str(entry), str(target))
            moved += 1
        shutil.rmtree(staging, ignore_errors=True)
        return moved

    def _fallback_pip_update(self) -> None:
        """极端情况下的兜底：直接调用 pip。"""
        self._set_busy("ytdlp", 20, "正在通过 pip 更新 yt-dlp…")
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade",
               "--disable-pip-version-check", "yt-dlp"]
        tail: List[str] = []
        try:
            flags = 0x08000000 if IS_WIN else 0
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace",
                                    creationflags=flags)
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.strip()
                if line:
                    tail.append(line)
                    tail = tail[-3:]
                    self._set_busy("ytdlp", 55, line[:110])
            code = proc.wait(timeout=600)
        except Exception as exc:  # noqa: BLE001
            self._finish_busy()
            self.finished.emit("ytdlp", False, f"更新失败：{exc}")
            return
        self._finish_busy()
        if code == 0:
            self._percent = 100
            self.changed.emit()
            self.finished.emit("ytdlp", True, "yt-dlp 已更新，重新启动程序后生效")
        else:
            self.finished.emit("ytdlp", False, "更新失败：" + " / ".join(tail[-2:]))

    # ------------------------------------------------------------------
    @Slot()
    def openBinFolder(self) -> None:
        from .helpers import open_in_explorer
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        open_in_explorer(str(BIN_DIR))
