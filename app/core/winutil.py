"""Windows 原生窗口效果（圆角、深色标题栏、云母材质背景）。"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWA_BORDER_COLOR = 34

DWMWA_COLOR_DEFAULT = 0xFFFFFFFF
DWMWA_COLOR_NONE = 0xFFFFFFFE

DWMWCP_DEFAULT = 0
DWMWCP_DONOTROUND = 1
DWMWCP_ROUND = 2
DWMWCP_ROUNDSMALL = 3

DWMSBT_AUTO = 0
DWMSBT_NONE = 1
DWMSBT_MAINWINDOW = 2      # 云母 Mica
DWMSBT_TRANSIENTWINDOW = 3  # 亚克力 Acrylic
DWMSBT_TABBEDWINDOW = 4     # Mica Alt

SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020
SWP_NOACTIVATE = 0x0010


def _dwm_set(hwnd: int, attr: int, value: int) -> bool:
    try:
        dwmapi = ctypes.windll.dwmapi
    except Exception:
        return False
    val = ctypes.c_int(value)
    try:
        res = dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd), ctypes.c_uint(attr),
            ctypes.byref(val), ctypes.sizeof(val),
        )
        return res == 0
    except Exception:
        return False


def _refresh(hwnd: int) -> None:
    try:
        ctypes.windll.user32.SetWindowPos(
            wintypes.HWND(hwnd), None, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
        )
    except Exception:
        pass


def colorref(r: int, g: int, b: int) -> int:
    """Windows COLORREF 为 0x00BBGGRR。"""
    return (b << 16) | (g << 8) | r


def apply_window_style(hwnd: int, dark: bool = True, rounded: bool = True,
                       backdrop: int = DWMSBT_NONE,
                       border: int | None = None) -> dict:
    """应用窗口效果，返回实际生效的项目。"""
    if not sys.platform.startswith("win") or not hwnd:
        return {}
    result = {"dark": False, "rounded": False, "backdrop": False, "border": False}

    # Windows 11 才有圆角与材质；旧系统调用会失败但无害。
    result["dark"] = _dwm_set(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if dark else 0)
    if rounded:
        result["rounded"] = (
            _dwm_set(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)
            or _dwm_set(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUNDSMALL)
        )
    result["backdrop"] = _dwm_set(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, backdrop)
    # 让系统 1px 描边跟随主题，避免出现中性灰边框
    if border is None:
        border = colorref(0x2A, 0x33, 0x42) if dark else colorref(0xDC, 0xE2, 0xEE)
    result["border"] = _dwm_set(hwnd, DWMWA_BORDER_COLOR, border)
    _refresh(hwnd)
    return result


def windows_build() -> int:
    if not sys.platform.startswith("win"):
        return 0
    try:
        return int(ctypes.windll.ntdll.RtlGetVersion.__class__ and 0) or _build()
    except Exception:
        return 0


def _build() -> int:
    try:
        ver = sys.getwindowsversion()
        return ver.build
    except Exception:
        return 0
