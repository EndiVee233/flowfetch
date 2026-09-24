"""应用配置：JSON 持久化 + 变更通知。"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import QObject, Signal, Slot

from . import bili_format, yt_format
from .helpers import app_data_dir, default_download_dir

CONFIG_PATH = app_data_dir() / "settings.json"
HISTORY_PATH = app_data_dir() / "history.json"
CACHE_DIR = app_data_dir() / "cache"


def default_settings() -> Dict[str, Any]:
    return {
        # —— 常规 ——
        "output_dir": default_download_dir(),
        "temp_dir": "",
        "filename_template": "%(title)s [%(id)s].%(ext)s",
        "max_concurrent": 2,
        "max_concurrent_max": 8,
        "retries": 10,
        "concurrent_fragments": 4,

        # —— 外观 ——
        "theme": "dark",              # dark | light | system
        "accent": "violet",           # violet | blue | cyan | emerald | amber | rose
        "font_scale": 1.0,
        "rounded_window": True,
        "mica": True,
        "animations": True,
        "sidebar_compact": False,

        # —— 网络 ——
        "proxy": "",
        "cookie_file": "",
        "cookie_browser": "",
        # 优先使用“程序内登录”得到的凭据（Chrome/Edge 新版已无法从外部解密 Cookie）
        "weblogin_enabled": True,
        # 自动获取访客 Cookie：足以规避 YouTube 短时间批量下载的限流，无需登录
        "guest_cookie_enabled": True,
        "guest_cookie_updated_at": 0,
        "user_agent": "",
        "referer": "",
        "ratelimit_kib": 0,           # 0 = 不限速，单位 KiB/s
        "socket_timeout": 30,

        # —— 下载内容（对所有站点生效）——
        "container": "mp4",           # mp4 | mkv | webm | 原始
        "no_overwrites": False,
        "keep_original": False,
        "playlist_limit": 200,
        "playlist_reverse": False,
        # 字幕：勾了「下载字幕」就同时接受人工字幕与自动字幕，不再分两个开关
        "write_subs": False,
        "sub_langs": "zh-Hans,zh-CN,zh,en",
        # 字幕输出格式：原始 = 保持网站提供的格式；srt / vtt / ass / lrc 会用 FFmpeg 转换
        "sub_format": "原始",
        "embed_subs": False,
        # 封面与元数据
        "write_thumbnail": False,
        "embed_thumbnail": True,
        "embed_metadata": True,
        "write_infojson": False,
        "write_description": False,
        # 高帧率偏好（YouTube 那栏里也能改，两处同步）
        "prefer_60fps": True,
        "prefer_hdr": False,
        # SponsorBlock
        "sponsorblock": False,
        "sponsorblock_remove": True,
        "sponsorblock_cats": ["sponsor", "selfpromo", "interaction", "intro", "outro", "music_offtopic"],
        # FFmpeg 来源：managed = 由本程序下载并管理；custom = 使用用户已安装的 FFmpeg
        "ffmpeg_mode": "managed",
        "ffmpeg_dir": "",

        # —— YouTube 专用（只对 YouTube 链接生效）——
        "yt_use_custom_quality": True,
        "yt_quality_order": list(yt_format.DEFAULT_QUALITY_ORDER),
        "yt_audio_order": list(yt_format.DEFAULT_AUDIO_ORDER),
        "yt_codec_order": list(yt_format.DEFAULT_CODEC_ORDER),

        # —— 哔哩哔哩专用（只对哔哩哔哩链接生效）——
        "bili_use_custom_quality": True,
        # 优先级表的唯一来源在 bili_format.py / yt_format.py，避免两处各写一份
        "bili_quality_order": list(bili_format.DEFAULT_QUALITY_ORDER),
        "bili_audio_order": list(bili_format.DEFAULT_AUDIO_ORDER),
        "bili_codec_order": list(bili_format.DEFAULT_CODEC_ORDER),
        "bili_download_video": True,
        "bili_download_audio": True,
        "bili_auto_merge": True,
        "bili_mark_chapters": False,
        "bili_mark_ads": False,
        "bili_danmaku_xml": False,
        "bili_danmaku_ass": False,
        "bili_danmaku_json": False,
        "bili_write_subs": False,
        "bili_write_cover": False,
        "bili_sub_langs": "",
        "bili_cover_mode": "",
        "bili_write_json": False,
        "bili_existing": "overwrite",
        "bili_auto_start": True,

        # —— 行为 ——
        "notify_on_finish": True,
        "open_folder_when_done": False,
        "auto_start": True,
        "clipboard_watch": False,

        # —— 窗口 ——
        "window_width": 1180,
        "window_height": 760,
        "window_x": -1,
        "window_y": -1,
        "window_maximized": False,
    }


def _as_number(value: Any, kind: type) -> Any:
    """把界面传回来的数值收敛成整数或浮点。

    QML 的 `slider.value` / `Math.round(x)` 都是 real，经 `setSetting` 落盘后会变成
    3.0、1152.0 这种写法 —— 能用，但和默认值的 int 类型不一致，以后比较、判断都容易踩坑。
    挡掉 NaN / inf 是因为它们会被 json 写成裸的 NaN，下次读配置直接解析失败。
    """
    try:
        num = float(value)
    except (TypeError, ValueError):
        return value
    if not math.isfinite(num):
        return value
    return int(round(num)) if kind is int else num


def _serializable(value: Any) -> bool:
    """值能不能安全地写进 JSON。

    NaN / inf 会被 json 写成裸的 `NaN` / `Infinity`，而标准 JSON 读不回来 ——
    下次启动 json.loads 直接抛异常，整个配置文件作废（用户设置全丢）。
    这里挡在写入口，宁可丢掉这一个键也不能污染整份文件。
    """
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, (list, tuple)):
        return all(_serializable(item) for item in value)
    if isinstance(value, dict):
        return all(_serializable(item) for item in value.values())
    return True


class Settings(QObject):
    """配置对象，暴露给 QML。"""

    changed = Signal(str, "QVariant")

    def __init__(self, parent: QObject | None = None, path: Path | None = None) -> None:
        super().__init__(parent)
        # 路径在构造时就定下来：测试里常常要指到临时文件，如果这里每次去读模块级的
        # CONFIG_PATH，一旦有人把它改回去，save() 就会写到用户真实的 settings.json 上。
        self._path = Path(path) if path is not None else CONFIG_PATH
        self._data: Dict[str, Any] = default_settings()
        self.load()

    # ------------------------------------------------------------------
    def load(self) -> None:
        try:
            if self._path.exists():
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for key, value in raw.items():
                        template = self._data.get(key)
                        # 老配置文件里可能存着 3.0 / 1152.0 这类浮点写法，读回来顺手收敛一下
                        if isinstance(template, int) and not isinstance(template, bool) \
                                and isinstance(value, (int, float)) \
                                and not isinstance(value, bool):
                            value = _as_number(value, int)
                        self._data[key] = value
        except Exception:
            pass
        self._migrate()

    # 这些键存的是优先级顺序，需要与内置表保持同步
    _ORDER_FIXERS = {
        "bili_quality_order": staticmethod(bili_format.normalize_quality_order),
        "bili_audio_order": staticmethod(bili_format.normalize_audio_order),
        "bili_codec_order": staticmethod(bili_format.normalize_codec_order),
        "yt_quality_order": staticmethod(yt_format.normalize_quality_order),
        "yt_audio_order": staticmethod(yt_format.normalize_audio_order),
        "yt_codec_order": staticmethod(yt_format.normalize_codec_order),
    }

    # 已经取消的设置项：老配置文件里残留的值直接丢掉，避免越攒越乱
    _REMOVED_KEYS = ("audio_format", "audio_quality", "prefer_codec", "auto_subs")

    def _migrate(self) -> None:
        """把老版本保存的数据补齐到当前的内置档位表。

        档位表会随站点接口变化（例如哔哩哔哩后来新增的 qn=100 智能修复），
        老配置里缺少的新档位要插回默认顺序中的位置，否则界面上看不到它，
        下载时也不会考虑它。
        """
        for key in self._REMOVED_KEYS:
            self._data.pop(key, None)

        for key, fix in self._ORDER_FIXERS.items():
            if key not in self._data:
                continue
            value = self._data[key]
            fixed = fix(value if isinstance(value, list) else None)
            if fixed != value:
                self._data[key] = fixed

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {k: v for k, v in self._data.items() if _serializable(v)}
            tmp = self._path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp, self._path)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        template = self._data.get(key)
        numeric = (isinstance(template, (int, float))
                   and not isinstance(template, bool)
                   and isinstance(value, (int, float))
                   and not isinstance(value, bool))
        if numeric:
            if not math.isfinite(value):
                # NaN / inf 一律拒收：它既会被写成非法 JSON，也会顺着 all() 漏进界面
                return
            kind = float if isinstance(template, float) else int
            if not (kind is int and isinstance(value, int)):
                value = _as_number(value, kind)
        if self._data.get(key) == value:
            return
        self._data[key] = value
        self.changed.emit(key, value)

    @Slot(result="QVariantMap")
    def all(self) -> Dict[str, Any]:
        return dict(self._data)

    @Slot(str, result="QVariant")
    def value(self, key: str) -> Any:
        return self._data.get(key)

    @Slot(str, "QVariant")
    def update(self, key: str, value: Any) -> None:
        self.set(key, value)
        self.save()

    @Slot()
    def reset(self) -> None:
        self._data = default_settings()
        self.save()
        self.changed.emit("*", None)

    @Slot(result=str)
    def configPath(self) -> str:
        return str(self._path)
