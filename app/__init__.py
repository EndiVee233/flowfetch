"""yt-dlp 图形用户界面 —— 基于 yt-dlp 的桌面下载工具。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

__version__ = "1.0.0"
APP_NAME = "yt-dlp 图形用户界面"
APP_ID = "YtDlpGui"
APP_TAGLINE = "适用于 yt-dlp 的图形用户界面"


def _data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / APP_ID


# 程序自行维护的 yt-dlp 组件目录，优先级高于环境中已安装的版本。
# 这样 yt-dlp 可以随程序内更新，无需重新打包，也不受 pip / 系统 Python 影响。
MANAGED_LIB_DIR = _data_dir() / "lib"

if MANAGED_LIB_DIR.is_dir():
    _p = str(MANAGED_LIB_DIR)
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)
