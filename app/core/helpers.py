"""通用工具函数：单位换算、格式化、路径处理。"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

_UNITS = ("B", "KB", "MB", "GB", "TB", "PB")


def human_size(num, suffix: str = "B") -> str:
    """把字节数转换成人性化字符串。"""
    try:
        num = float(num)
    except (TypeError, ValueError):
        return "—"
    if num <= 0:
        return "0 B"
    idx = 0
    while num >= 1024 and idx < len(_UNITS) - 1:
        num /= 1024.0
        idx += 1
    if idx == 0:
        return f"{int(num)} {suffix}"
    return f"{num:.2f} {_UNITS[idx]}"


def human_speed(bps) -> str:
    if not bps or bps <= 0:
        return "—"
    return human_size(bps) + "/s"


def human_duration(seconds) -> str:
    """00:00 / 1:02:03 形式的时长。"""
    try:
        seconds = int(float(seconds))
    except (TypeError, ValueError):
        return "—"
    if seconds < 0:
        return "—"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def human_eta(seconds) -> str:
    if seconds is None:
        return "—"
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "—"
    if seconds < 0:
        return "—"
    if seconds < 60:
        return f"{seconds} 秒"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m} 分 {s:02d} 秒"
    h, m = divmod(m, 60)
    return f"{h} 小时 {m:02d} 分"


def human_count(n) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "—"
    return f"{n:,}"


_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(name: str, fallback: str = "未命名") -> str:
    name = _INVALID.sub("_", (name or "").strip()).strip(" .")
    return name[:120] or fallback


def ensure_dir(path: str) -> str:
    p = Path(os.path.expandvars(os.path.expanduser(path)))
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def open_in_explorer(path: str, select: bool = False) -> None:
    """在资源管理器中打开文件或文件夹。"""
    p = Path(path)
    if not p.exists():
        p = p.parent
    if not p.exists():
        return
    target = str(p)
    try:
        if select and p.is_file():
            subprocess.Popen(["explorer", "/select,", target])
        else:
            os.startfile(target)  # type: ignore[attr-defined]
    except Exception:
        try:
            subprocess.Popen(["explorer", target])
        except Exception:
            pass


def default_download_dir() -> str:
    downloads = Path.home() / "Downloads"
    if downloads.is_dir():
        return str(downloads / "yt-dlp 下载")
    return str(Path.home() / "yt-dlp 下载")


def is_frozen() -> bool:
    """是否运行在 PyInstaller 等打包出来的 exe 里。"""
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """打包后的资源根目录（PyInstaller 的 _MEIPASS），未打包时就是程序根目录。"""
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        return Path(meipass)
    return app_root()


def app_root() -> Path:
    """程序根目录（app 包的上一级）。

    打包成 exe 后 `__file__` 指向临时解包目录，那个目录会被清理、也不该被写，
    因此这里返回 exe 自己所在的目录 —— 它才是用户眼里的「安装目录」。
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def resource_dir(name: str) -> Path:
    """取打包进来的资源目录（如 qml、assets）。

    打包时资源放在 _MEIPASS 下；开发时它们跟随 app 包。两种情形都先看
    `_MEIPASS/<name>`，再回退到 `app/<name>`，避免两种布局各写一份判断。
    """
    candidates = [bundle_root() / name, app_root() / "app" / name,
                  Path(__file__).resolve().parent.parent / name]
    for path in candidates:
        if path.is_dir():
            return path
    return candidates[-1]


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    p = Path(base) / "YtDlpGui"
    p.mkdir(parents=True, exist_ok=True)
    return p


def app_cache_dir() -> Path:
    p = app_data_dir() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def is_windows() -> bool:
    return sys.platform.startswith("win")
