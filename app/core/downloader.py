"""yt-dlp 引擎封装：解析、下载、队列调度。"""
from __future__ import annotations

import os
import re
import threading
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from . import taskmodel as TM
from .bili_format import build_selector as build_bili_selector
from .bili_format import quality_by_name
from .yt_format import build_selector as build_yt_selector
from .yt_format import is_youtube_url
from .bilibili import COOKIE_FILE as BILI_COOKIE_FILE
from .bilibili import is_bilibili_url
from .config import Settings
from .danmaku import download as download_danmaku
from .errors import describe as describe_error
from .errors import format_detail
from .guestcookie import guest_cookie_path
from .helpers import ensure_dir, human_duration, human_size
from .taskmodel import Task, TaskModel
from .weblogin import snapshot_for_url
# yt_dlp 一律从 core.ytdlp 取：那里负责「没装就先装上」，模块导入期不会崩
from .ytdlp import available as ytdlp_available
from .ytdlp import yt_dlp


def _cover_resizer_base() -> Any:
    """封面缩放后处理器的基类。

    **必须在调用时取、不能在模块导入期取**：打包分发时 yt-dlp 是首次启动才下载的，
    导入期拿不到它，基类就会退化成 object，表现为「封面 640/320 选项静默失效」。
    """
    try:
        from yt_dlp.postprocessor import FFmpegThumbnailsConvertorPP
        return FFmpegThumbnailsConvertorPP
    except Exception:
        return None


def _build_cover_resizer_class(base: type):
    """用 yt-dlp 的基类**在运行期**造出封面缩放 PP。

    不能先写成 object 的子类再改 `__bases__` —— CPython 会因实例布局不兼容
    拒绝重绑（且 `super()` 仍会去找 `__class__` 单元格里的旧基类），
    结果就是「看起来注册成功、实际一实例化就 TypeError」。
    """

    class _CoverResizer(  # noqa: D101
            base):  # type: ignore[misc, valid-type]
        """下载封面后按指定宽度缩放（不改变比例）。

        仅在用户显式选择了 640 / 320 等分辨率时挂上；任何异常都被吞掉，
        保证最坏情况下只是保留原图，不会让整个下载任务失败。
        """

        def __init__(self, downloader=None, width: int = 0):
            super().__init__(downloader)
            self._width = int(width or 0)

        def run(self, info):  # noqa: D401
            if self._width <= 0:
                return [], info
            try:
                files_to_delete, info = super().run(info)
            except Exception:
                files_to_delete, info = [], info
            width = self._width
            for thumb in (info.get("thumbnails") or []):
                fp = thumb.get("filepath")
                if not fp or not os.path.exists(fp):
                    continue
                try:
                    # 临时文件必须保留合法扩展名：ffmpeg 靠扩展名推断输出格式，
                    # 用 .tmp 结尾会报 "Error opening output files: Invalid argument"。
                    ext = os.path.splitext(fp)[1] or ".jpg"
                    tmp = f"{fp}.resized{ext}"
                    self.real_run_ffmpeg(
                        [(fp, [])],
                        [(tmp, ["-vf", f"scale={width}:-1", "-y"])],
                    )
                    if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
                        os.replace(tmp, fp)
                except Exception:
                    if os.path.exists(tmp):
                        try:
                            os.remove(tmp)
                        except Exception:
                            pass
            return files_to_delete, info

    return _CoverResizer


# 封面缩放 PP 的类：yt-dlp 就绪后由 _register_cover_resizer() 填上
_CoverResizerPP: Any = None


def _register_cover_resizer() -> bool:
    """把封面缩放 PP 注册进 yt-dlp 的注册表（幂等）。"""
    global _CoverResizerPP
    base = _cover_resizer_base()
    if base is None:
        return False
    try:
        if _CoverResizerPP is None:
            _CoverResizerPP = _build_cover_resizer_class(base)
        import yt_dlp.postprocessor as _yt_pp
        _yt_pp.postprocessors.value["CoverResizerPP"] = _CoverResizerPP
    except Exception:
        return False
    return True


def _cover_resizer_class():
    """取（必要时补建）封面缩放 PP 类；引擎未就绪时返回 None。"""
    if not _ensure_cover_resizer():
        return None
    return _CoverResizerPP


# 把自定义封面缩放后处理器注册进 yt-dlp 的 PP 注册表，
# 这样只要在 postprocessors 里传 {"key": "CoverResizer", "width": 640} 即可启用。
# 引擎就绪时这里会注册成功；否则等 build_options 真正要挂 PP 时再补注册。
_COVER_RESIZER_READY = _register_cover_resizer()


def _ensure_cover_resizer() -> bool:
    """确保封面缩放 PP 已注册（引擎晚于程序启动才就绪时补一次）。"""
    global _COVER_RESIZER_READY
    if _COVER_RESIZER_READY:
        return True
    _COVER_RESIZER_READY = _register_cover_resizer()
    return _COVER_RESIZER_READY


def describe_hint(raw: str, fallback: str = "解析失败") -> str:
    return describe_error(raw, fallback)[1]

# 站点 -> 最近一次「登录凭据被 YouTube 拒绝」的时间戳。
# 被拒后短期内不再重复尝试，省掉一次注定失败的解析。
_LOGIN_COOKIE_BAD: Dict[str, float] = {}
_BAD_TTL = 2 * 3600

# yt-dlp 对哔哩哔哩会把「视频支持、但当前账号拿不到」的画质打进日志，例如：
#   Format(s) 4K 超高清, 1080P 高码率 are missing; you have to become a
#   premium member to download them.
# 解析器只把这些画质的「名字」告诉我们（support_formats 里的 new_description），
# 拿到它就能把弹窗里的状态区分成「视频没有这一档」和「账号拿不到这一档」。
_MISSING_FORMATS = re.compile(r"Format\(s\)\s+(.+?)\s+are missing", re.I)


def parse_missing_qualities(lines: Iterable[str]) -> List[int]:
    """从 yt-dlp 的日志里取出「视频有、账号拿不到」的画质档位。"""
    out: List[int] = []
    for line in lines:
        match = _MISSING_FORMATS.search(line or "")
        if not match:
            continue
        for name in match.group(1).split(","):
            qn = quality_by_name(name.strip())
            if qn and qn not in out:
                out.append(qn)
    return out


def _site_key(url: str) -> str:
    """取域名的主域部分作为站点标识（如 www.youtube.com -> youtube.com）。"""
    try:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return ""
    if not host:
        return ""
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def mark_login_cookie_bad(url: str) -> None:
    key = _site_key(url)
    if key:
        _LOGIN_COOKIE_BAD[key] = time.time()


def _login_cookie_usable(url: str) -> bool:
    key = _site_key(url)
    if not key:
        return True
    stamp = _LOGIN_COOKIE_BAD.get(key)
    return stamp is None or (time.time() - stamp) > _BAD_TTL

try:  # yt-dlp 公开的取消异常
    from yt_dlp.utils import DownloadCancelled
except Exception:  # pragma: no cover
    class DownloadCancelled(Exception):  # type: ignore
        pass

_ANSI = re.compile("\x1b\\[[0-9;]*m")

# 站点名称的规范写法
EXTRACTOR_NAMES = {
    "Youtube": "YouTube",
    "YoutubeTab": "YouTube",
    "BilibiliSpaceVideo": "哔哩哔哩",
    "BiliIntl": "哔哩哔哩",
    "Twitter": "X (Twitter)",
    "TikTok": "TikTok",
    "Weibo": "微博",
    "Douyin": "抖音",
    "Vimeo": "Vimeo",
    "Twitch": "Twitch",
}

# Postprocessor 名称 → 中文提示
PP_NAMES = {
    "FFmpegMergerPP": "正在合并音视频",
    "FFmpegExtractAudioPP": "正在提取音频",
    "FFmpegVideoConvertorPP": "正在转换视频格式",
    "FFmpegVideoRemuxerPP": "正在重新封装",
    "FFmpegMetadataPP": "正在写入元数据",
    "EmbedThumbnailPP": "正在嵌入封面",
    "FFmpegEmbedSubtitlePP": "正在嵌入字幕",
    "FFmpegThumbnailsConvertorPP": "正在转换封面",
    "FFmpegSubtitlesConvertorPP": "正在转换字幕",
    "FFmpegFixupStretchedPP": "正在修正时长",
    "FFmpegFixupM4aPP": "正在修正音频",
    "FFmpegFixupM3u8PP": "正在修正流",
    "FFmpegFixupTimestampPP": "正在校正时间戳",
    "FFmpegFixupDurationPP": "正在校正时长",
    "FFmpegFixupDuplicateMoovPP": "正在修正容器",
    "FFmpegCopyStreamPP": "正在复制流",
    "FFmpegSplitChaptersPP": "正在分割章节",
    "SponsorBlockPP": "正在获取章节标记",
    "ModifyChaptersPP": "正在移除赞助片段",
    "MoveFilesAfterDownloadPP": "正在整理文件",
    "XAttrMetadataPP": "正在写入扩展属性",
}


def _clean(text: str) -> str:
    text = _ANSI.sub("", str(text or ""))
    text = re.sub(r"^\s*ERROR:\s*", "", text, flags=re.I)
    return text.strip()


class _Logger:
    """把 yt-dlp 的日志转成 Qt 信号。"""

    def __init__(self, sink) -> None:
        self._sink = sink

    def debug(self, msg: str) -> None:
        if msg.startswith("[debug] "):
            return
        self._sink(_clean(msg))

    def info(self, msg: str) -> None:
        self._sink(_clean(msg))

    def warning(self, msg: str) -> None:
        self._sink(_clean(msg))

    def error(self, msg: str) -> None:
        self._sink(_clean(msg))


class _Signals(QObject):
    progress = Signal(str, dict)
    finished = Signal(str, dict)
    failed = Signal(str, str)
    logline = Signal(str, str)
    analyze_ok = Signal(str, dict)
    analyze_fail = Signal(str, str)


# ----------------------------------------------------------------------
# 选项构建
# ----------------------------------------------------------------------
def build_format_selector(preset: str, cfg: Settings, custom: str = "") -> str:
    if preset == "custom" and custom:
        return custom
    if preset == "audio":
        return "bestaudio/best"
    if preset == "worst":
        return "worstvideo*+worstaudio/worst"
    # 允许直接传入任意高度（例如 "240"），便于按实际可用的画质生成档位
    if str(preset).isdigit():
        height: Optional[int] = int(preset)
    else:
        height = {"best": None, "2160": 2160, "1440": 1440, "1080": 1080,
                  "720": 720, "480": 480, "360": 360}.get(preset)

    # 编码偏好交给各站点的编码优先级列表（YouTube / 哔哩哔哩各自一份），
    # 这里的通用规则只按分辨率和帧率挑。
    hf = f"[height<=?{height}]" if height else ""
    fps = "[fps>=50]" if cfg.get("prefer_60fps") else ""

    strict = f"bestvideo{hf}{fps}"
    loose = f"bestvideo{hf}{fps}"
    bare = f"bestvideo{hf}"
    simple = f"best[height<=?{height}]" if height else "best"
    chain = [
        f"{strict}+bestaudio",
        f"{loose}+bestaudio/bestaudio",
        f"{bare}+bestaudio/bestaudio",
        "bestvideo+bestaudio/best",
        simple,
        "best",
    ]
    # 去重，保持顺序
    seen, out = set(), []
    for item in chain:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return "/".join(out)


def build_postprocessors(task: Task, cfg: Settings) -> List[Dict[str, Any]]:
    pps: List[Dict[str, Any]] = []
    audio_only = task.audio_only
    container = str(cfg.get("container", "mp4"))

    # 仅音频的任务在格式弹窗里就选定了具体音轨，下到的就是那一条流，
    # 不再做「统一转成 mp3」这类二次转码。
    if not audio_only and container in ("mp4", "mkv") and not cfg.get("keep_original"):
        pps.append({"key": "FFmpegVideoRemuxer", "preferedformat": container})

    if cfg.get("sponsorblock"):
        cats = cfg.get("sponsorblock_cats") or []
        if isinstance(cats, str):
            cats = [c.strip() for c in cats.split(",") if c.strip()]
        if cats:
            pps.append({"key": "SponsorBlock", "categories": cats, "when": "after_filter"})
            if cfg.get("sponsorblock_remove") and not audio_only:
                pps.append({"key": "ModifyChapters", "remove_sponsor_segments": cats})

    if cfg.get("embed_metadata"):
        pps.append({"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": True})
    if cfg.get("embed_thumbnail"):
        pps.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
    if cfg.get("embed_subs") and not audio_only:
        pps.append({"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})
    return pps


def build_options(task: Task, cfg: Settings, hook, pp_hook, logger) -> Dict[str, Any]:
    out_dir = ensure_dir(task.output_dir or cfg.get("output_dir"))
    temp_dir = cfg.get("temp_dir") or ""
    paths: Dict[str, str] = {"home": out_dir}
    if temp_dir:
        paths["temp"] = ensure_dir(temp_dir)

    opts: Dict[str, Any] = {
        "paths": paths,
        "outtmpl": {"default": cfg.get("filename_template") or "%(title)s.%(ext)s"},
        "trim_file_name": 200,
        "windowsfilenames": True,
        "restrictfilenames": False,
        "quiet": True,
        "no_warnings": False,
        "noprogress": True,
        "nocolor": True,
        "consoletitle": False,
        "logger": logger,
        "progress_hooks": [hook],
        "postprocessor_hooks": [pp_hook],
        "ignoreerrors": False,
        "retries": int(cfg.get("retries", 10) or 10),
        "fragment_retries": int(cfg.get("retries", 10) or 10),
        "file_access_retries": 3,
        "concurrent_fragment_downloads": max(1, int(cfg.get("concurrent_fragments", 4) or 1)),
        "socket_timeout": float(cfg.get("socket_timeout", 30) or 30),
        "nopart": False,
        "continuedl": True,
        "overwrites": not bool(cfg.get("no_overwrites")),
        "nooverwrites": bool(cfg.get("no_overwrites")),
        "noplaylist": True,
        "writethumbnail": bool(cfg.get("write_thumbnail") or cfg.get("embed_thumbnail")),
        "writesubtitles": bool(cfg.get("write_subs")),
        # 「下载字幕」一并接受人工字幕与自动生成字幕
        "writeautomaticsub": bool(cfg.get("write_subs")),
        "subtitleslangs": [s.strip() for s in str(cfg.get("sub_langs", "")).replace(";", ",").split(",") if s.strip()],
        "writeinfojson": bool(cfg.get("write_infojson")),
        "writedescription": bool(cfg.get("write_description")),
        "postprocessors": build_postprocessors(task, cfg),
    }

    if not task.audio_only and not cfg.get("keep_original"):
        container = str(cfg.get("container", "mp4"))
        if container in ("mp4", "mkv", "webm"):
            opts["merge_output_format"] = container

    rate = int(cfg.get("ratelimit_kib", 0) or 0)
    if rate > 0:
        opts["ratelimit"] = rate * 1024

    proxy = str(cfg.get("proxy") or "").strip()
    if proxy:
        opts["proxy"] = proxy

    # anonymous 表示解析时登录态被拒、已降级；下载要沿用同一模式，
    # 否则会出现「解析成功但下载被拒」的错配
    opts.update(_cookie_options(cfg, task.url, guest_only=task.anonymous))

    # 优先使用程序自行解析出的 FFmpeg 目录（不依赖系统 PATH）
    ffmpeg_dir = str(cfg.get("_ffmpeg_resolved") or cfg.get("ffmpeg_dir") or "").strip()
    if ffmpeg_dir:
        opts["ffmpeg_location"] = ffmpeg_dir

    headers = {}
    ua = str(cfg.get("user_agent") or "").strip()
    if ua:
        headers["User-Agent"] = ua
    referer = str(cfg.get("referer") or "").strip()
    if referer:
        headers["Referer"] = referer
    if headers:
        opts["http_headers"] = headers

    on_bilibili = is_bilibili_url(task.url)
    bili_selector = (build_bili_selector(cfg, task.audio_only, task.preset, task.format_id)
                     if on_bilibili else None)
    # YouTube 用同一套「分辨率 × 音轨 × 编码」优先级；其余站点维持原来的规则
    yt_selector = (build_yt_selector(cfg, task.audio_only, task.preset, task.format_id)
                   if (not on_bilibili and is_youtube_url(task.url)) else None)
    if bili_selector:
        opts["format"] = bili_selector
    elif yt_selector:
        opts["format"] = yt_selector
    elif task.preset == "custom" and task.format_id:
        # 手动指定的格式永远优先于「仅音频」的兜底选择
        opts["format"] = task.format_id
    elif task.audio_only:
        opts["format"] = "bestaudio/best"
    else:
        opts["format"] = build_format_selector(task.preset, cfg)

    if on_bilibili:
        _apply_bilibili_options(opts, cfg)

    # ── 字幕：优先用本次下载单独选的语言，其次哔哩哔哩层默认 ──────────
    _sub = str(getattr(task, "sub_langs", "") or "").strip()
    if not _sub and on_bilibili and cfg.get("bili_write_subs"):
        _sub = str(cfg.get("bili_sub_langs") or "").strip()
    if _sub:
        opts["subtitleslangs"] = [s.strip() for s in _sub.replace(";", ",").split(",") if s.strip()]
        opts["writesubtitles"] = True
        # YouTube 上大量视频只有「自动字幕」：不放开自动字幕的话，
        # 用户在弹窗里明明选了语言，一个文件也下不到。
        opts["writeautomaticsub"] = True
    elif on_bilibili and cfg.get("bili_write_subs"):
        # 勾选了下载字幕但未指定语言 → 下载全部可用语言
        opts["writesubtitles"] = True
        opts["writeautomaticsub"] = True

    if opts.get("writesubtitles") or opts.get("writeautomaticsub"):
        # ── 字幕输出格式：本次任务优先，其次全局默认 ──────────────
        _sub_fmt = str(getattr(task, "sub_format", "") or "").strip()
        if not _sub_fmt:
            _sub_fmt = str(cfg.get("sub_format") or "").strip()
        if _sub_fmt and _sub_fmt not in ("原始", "best"):
            # 首选目标格式，网站没提供时先下别家格式，再由 FFmpeg 转过去
            opts["subtitlesformat"] = f"{_sub_fmt}/best"
            opts["convertsubtitles"] = _sub_fmt
        else:
            opts["subtitlesformat"] = "best"

    # ── 封面：优先用本次下载单独选的方式，其次哔哩哔哩层默认 ──────────
    _cover = str(getattr(task, "cover_mode", "") or "").strip()
    if not _cover and on_bilibili:
        _cover = str(cfg.get("bili_cover_mode") or "").strip()
        if not _cover and cfg.get("bili_write_cover"):
            _cover = "original"
    if _cover == "none":
        opts["writethumbnail"] = False
    elif _cover:
        opts["writethumbnail"] = True
        # 单独要封面文件时别让它被「嵌入封面」顺手删掉：
        # EmbedThumbnail 默认把刚下下来的图嵌进视频之后就删掉原图。
        for _pp in opts.get("postprocessors", []):
            if _pp.get("key") == "EmbedThumbnail":
                _pp["already_have_thumbnail"] = True
        _cw = 0
        try:
            _cw = int(_cover)
        except ValueError:
            _cw = 0
        # 封面缩放 PP 需要 yt-dlp 的 FFmpegThumbnailsConvertorPP 作基类；
        # 引擎若是在本次启动后才装好的（打包版首次启动），这里补注册一次。
        if _cw > 0 and _ensure_cover_resizer():
            opts.setdefault("postprocessors", []).append(
                {"key": "CoverResizer", "width": _cw})
    return opts


def _apply_bilibili_options(opts: Dict[str, Any], cfg: Settings) -> None:
    """哔哩哔哩专有的下载选项，只对哔哩哔哩链接生效。"""
    if str(cfg.get("bili_existing") or "overwrite") == "skip":
        opts["nooverwrites"] = True
        opts["overwrites"] = False
    if cfg.get("bili_write_cover"):
        opts["writethumbnail"] = True
    if cfg.get("bili_write_subs"):
        opts["writesubtitles"] = True
    if cfg.get("bili_write_json"):
        opts["writeinfojson"] = True
    if cfg.get("bili_mark_chapters"):
        opts["embedchapters"] = True
    if cfg.get("bili_mark_ads"):
        opts["sponsorblock"] = True


def analyze_options(cfg: Settings, logger, url: str = "",
                    use_cookies: bool = True,
                    guest_only: bool = False) -> Dict[str, Any]:
    opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "noprogress": True,
        "nocolor": True,
        "logger": logger,
        "socket_timeout": float(cfg.get("socket_timeout", 30) or 30),
        "playlistend": int(cfg.get("playlist_limit", 200) or 200),
        "ignoreerrors": False,
        "extractor_retries": 2,
        "cachedir": False,
    }
    proxy = str(cfg.get("proxy") or "").strip()
    if proxy:
        opts["proxy"] = proxy
    # 带上 URL，哔哩哔哩链接才会使用扫码登录得到的 Cookies，
    # 否则即使账号是大会员也只能看到 1080P。
    opts.update(_cookie_options(cfg, url, use_cookies=use_cookies,
                                guest_only=guest_only))
    if cfg.get("playlist_reverse"):
        opts["playlistreverse"] = True
    return opts


def _cookie_options(cfg: Settings, url: str,
                    use_cookies: bool = True,
                    guest_only: bool = False) -> Dict[str, Any]:
    """决定使用哪个 Cookies 来源，优先级从高到低：

    1. 哔哩哔哩：程序内扫码登录得到的 Cookies（否则只能解析到 1080P）
    2. 自动获取的访客 Cookie：默认主力来源，真实浏览器会话、不会被 Bot
       检测，专门用来规避短时间批量下载的 429 限流
    3. 程序内登录凭据（YouTube 等）：仅用于会员 / 年龄限制等必须登录的
       内容；普通视频带上反而会触发「需要重新加载」被拒
    4. 用户手动指定的 cookies.txt
    5. 回退：直接让 yt-dlp 从浏览器读取（新浏览器上大概率会失败）

    guest_only=True 表示跳过登录凭据、只用访客 Cookie，
    用于「登录态被拒」时的自动降级。
    """
    out: Dict[str, Any] = {}
    # 哔哩哔哩的凭据是画质前提，任何模式都必须带上，不参与降级
    if is_bilibili_url(url) and BILI_COOKIE_FILE.exists():
        out["cookiefile"] = str(BILI_COOKIE_FILE)
        return out

    cookie_file = ""
    # 1) 访客 Cookie 作为 YouTube 的默认来源：它是真实浏览器会话，
    #    不会被判定为机器人，专门用来规避短时间批量下载的限流（429）。
    #    优先于登录凭据，因为带登录态的请求反而会被 YouTube 以
    #    “需要重新加载”为由拒绝。
    if cfg.get("guest_cookie_enabled", True):
        guest = guest_cookie_path()
        if guest:
            cookie_file = str(guest)

    # 2) 程序内登录凭据（YouTube 等）：仅用于会员 / 年龄限制等必须登录的
    #    内容。正常情况下不主动使用，避免触发 bot 检测。
    if not cookie_file and (use_cookies and not guest_only
            and cfg.get("weblogin_enabled", True)
            and _login_cookie_usable(url)):
        cookie_file = snapshot_for_url(url)

    # 3) 用户手动指定的 cookies.txt
    if not cookie_file and use_cookies and not guest_only:
        cookie_file = str(cfg.get("cookie_file") or "").strip()

    if cookie_file and os.path.exists(cookie_file):
        out["cookiefile"] = cookie_file
        return out

    if use_cookies and not guest_only:
        browser = str(cfg.get("cookie_browser") or "").strip()
        if browser:
            out["cookiesfrombrowser"] = (browser, None, None, None)
    return out


_PREFIX_RE = re.compile(r"^p(\d+)\s+")


def _entry_title(entry: Dict[str, Any], top_title: str, index: int) -> str:
    """整理分P标题：去掉重复的合集标题，把 p01 缩写为 P1。"""
    raw = str(entry.get("title") or "").strip()
    if raw and top_title and raw.startswith(top_title):
        raw = raw[len(top_title):].strip()
    if not raw:
        raw = str(entry.get("part") or entry.get("id") or "").strip()
    match = _PREFIX_RE.match(raw)
    if match:
        raw = f"P{int(match.group(1))} · " + raw[match.end():].strip()
    return raw or f"第 {index} 项"


def _entry_url(entry: Dict[str, Any], base: str = "") -> str:
    url = entry.get("webpage_url") or entry.get("original_url") or ""
    if url:
        return url
    raw = entry.get("url") or ""
    ie_key = str(entry.get("ie_key") or "")
    vid = entry.get("id") or ""
    if ie_key == "Youtube" and vid:
        return f"https://www.youtube.com/watch?v={vid}"
    if raw.startswith("http"):
        return raw
    if vid and ie_key:
        return f"https://www.youtube.com/watch?v={vid}" if raw == vid else raw
    return raw or base


_CODEC_TEXTS = {
    "av01": "AV1", "vp09": "VP9", "vp9": "VP9", "vp8": "VP8",
    "avc1": "H.264", "h264": "H.264", "hvc1": "H.265", "hev1": "H.265", "h265": "H.265",
    "opus": "Opus", "vorbis": "Vorbis", "mp4a": "AAC", "aac": "AAC", "mp3": "MP3",
    "flac": "FLAC", "ec-3": "E-AC-3", "ac-3": "AC-3", "dtse": "DTS", "alac": "ALAC",
}


# 同一种编码在不同站点写法不同，统一归一到一个键上，
# 界面上「按编码分组」和设置里的编码优先级都靠它对齐。
_CODEC_KEYS = {
    "vp09": "vp9", "vp8": "vp8",
    "hvc1": "hevc", "hev1": "hevc", "h265": "hevc",
    "h264": "avc1",
    "mp4a": "aac", "ec-3": "eac3", "ac-3": "ac3", "dtse": "dts",
}


def _codec_raw(f: Dict[str, Any]) -> str:
    for field in ("vcodec", "acodec"):
        raw = str(f.get(field) or "")
        if raw and raw != "none":
            return raw
    return ""


def codec_key(f: Dict[str, Any]) -> str:
    """归一化后的编码键（av01 / vp9 / avc1 / hevc / opus / aac …）。"""
    raw = _codec_raw(f)
    if not raw:
        return ""
    key = raw.split(".")[0].lower()
    return _CODEC_KEYS.get(key, key)


def codec_label(f: Dict[str, Any]) -> str:
    """把 vcodec / acodec 变成好认的编码名，供界面单独展示。"""
    raw = _codec_raw(f)
    if not raw:
        return ""
    key = raw.split(".")[0].lower()
    return _CODEC_TEXTS.get(key, key.upper())


def _format_label(f: Dict[str, Any], brief: bool = False) -> str:
    """生成格式说明。brief=True 时只保留分辨率/编码等关键信息，供分栏列表使用。"""
    parts: List[str] = []
    if f.get("resolution") and f["resolution"] != "audio only":
        parts.append(str(f["resolution"]))
    elif f.get("height"):
        parts.append(f"{f['height']}p")
    fps = f.get("fps")
    if fps and float(fps) >= 50:
        parts.append(f"{int(fps)}fps")
    if f.get("resolution") == "audio only" or (f.get("vcodec") in (None, "none") and f.get("acodec") not in (None, "none")):
        parts.append("仅音频")
    elif f.get("acodec") in (None, "none"):
        parts.append("仅视频")
    ext = f.get("ext")
    if ext:
        parts.append(str(ext).upper())
    # 精简标签里不放编码：编码在界面上单独做成标签，避免和分辨率挤成一行
    if not brief:
        vcodec = f.get("vcodec")
        if vcodec and vcodec != "none":
            parts.append(str(vcodec).split(".")[0])
    abr = f.get("abr")
    if abr:
        parts.append(f"{int(abr)}kbps")
    if brief:
        return " · ".join(parts)
    tbr = f.get("tbr")
    if tbr:
        parts.append(f"总码率 {int(tbr)}k")
    size = f.get("filesize") or f.get("filesize_approx")
    if size:
        parts.append(human_size(size))
    note = f.get("format_note")
    if note and note not in parts:
        parts.append(str(note))
    return " · ".join(parts)


class _ProgressThrottle:
    def __init__(self, interval: float = 0.12) -> None:
        self.interval = interval
        self._last = 0.0

    def ready(self) -> bool:
        now = time.monotonic()
        if now - self._last >= self.interval:
            self._last = now
            return True
        return False

    def reset(self) -> None:
        self._last = 0.0


class DownloadEngine(QObject):
    """负责队列调度与单任务下载。"""

    taskChanged = Signal(str)
    taskStarted = Signal(str)
    taskDone = Signal(str)
    statsChanged = Signal()

    def __init__(self, settings: Settings, model: TaskModel, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.model = model
        self.signals = _Signals()
        self._threads: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()
        self._ydls: Dict[str, Any] = {}
        # 被用户暂停的任务：既用于区分「暂停」与「取消」，也用于挡住暂停前排队的进度信号
        self._paused: set[str] = set()
        self._pump_pending = False

        self.signals.progress.connect(self._on_progress)
        self.signals.finished.connect(self._on_finished)
        self.signals.failed.connect(self._on_failed)
        self.signals.logline.connect(self._on_log)

    # ------------------------------------------------------------------
    # 任务创建
    # ------------------------------------------------------------------
    def new_task(self, url: str, **kwargs: Any) -> Task:
        return Task(
            id=uuid.uuid4().hex[:12],
            url=url.strip(),
            output_dir=kwargs.pop("output_dir", "") or str(self.settings.get("output_dir")),
            **kwargs,
        )

    def enqueue(self, task: Task) -> Task:
        self.model.add(task)
        self.taskChanged.emit(task.id)
        self.pump()
        return task

    @Slot()
    def pump(self) -> None:
        limit = max(1, int(self.settings.get("max_concurrent", 2) or 1))
        deferred = False
        with self._lock:
            # 已经退出的线程不必再占位，否则「继续下载」会误判为仍在运行
            for dead in [tid for tid, th in self._threads.items() if not th.is_alive()]:
                self._threads.pop(dead, None)
            running = len(self._threads)
            if running >= limit:
                return
            for task in self.model.queued():
                if running >= limit:
                    break
                thread = self._threads.get(task.id)
                if thread is not None and thread.is_alive():
                    # 旧线程（多为刚刚被暂停/取消的那条）还在收尾，稍后重新调度
                    deferred = True
                    continue
                task.status = TM.ANALYZING
                task.detail = "正在获取媒体信息"
                self.model.touch(task.id)
                thread = threading.Thread(target=self._run, args=(task,), daemon=True,
                                          name=f"dl-{task.id}")
                self._threads[task.id] = thread
                thread.start()
                running += 1
        self.statsChanged.emit()
        if deferred:
            self._schedulePump()

    def _schedulePump(self, delay: int = 180) -> None:
        """安排一次延迟调度：等待旧线程真正退出后再启动排队中的任务。"""
        if self._pump_pending:
            return
        self._pump_pending = True
        QTimer.singleShot(delay, self._pumpLater)

    def _pumpLater(self) -> None:
        self._pump_pending = False
        self.pump()

    def _is_paused(self, task_id: str) -> bool:
        """任务是否处于「已暂停」状态。

        下载线程里要判断暂停，不能只读 `task.canceled`：用户点暂停与文件正好下完
        可能撞在同一瞬间，那时取消标志还没来得及生效。以 `_paused` 这份显式记录为准。
        """
        with self._lock:
            return task_id in self._paused

    # ------------------------------------------------------------------
    def _run(self, task: Task) -> None:
        throttle = _ProgressThrottle()
        state = {"filename": "", "count": 0}

        def hook(d: Dict[str, Any]) -> None:
            if task.canceled:
                raise DownloadCancelled("用户已取消")
            # 暂停之后不应再往前走：暂停是「中断 + 保留断点」，继续时从头续传。
            # 取消标志有覆盖不到的小窗口（暂停信号刚发出、下载恰好在同一瞬间走完），
            # 这里再按 _paused 兜一层，否则用户会看到一条「已暂停」的任务自己跑完。
            if self._is_paused(task.id):
                raise DownloadCancelled("用户已暂停")
            status = d.get("status")
            info = d.get("info_dict") or {}
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done = d.get("downloaded_bytes") or 0
                if not throttle.ready():
                    return
                idx = info.get("playlist_index") or 0
                cnt = info.get("n_entries") or info.get("playlist_count") or task.playlist_count or 0
                self.signals.progress.emit(task.id, {
                    "status": TM.DOWNLOADING,
                    "downloaded": int(done),
                    "total": int(total),
                    "speed": float(d.get("speed") or 0),
                    "eta": d.get("eta"),
                    "detail": f"下载中 · 第 {idx}/{cnt} 项" if (idx and cnt and cnt > 1) else "下载中",
                    "playlist_index": idx,
                    "playlist_count": cnt,
                })
            elif status == "finished":
                throttle.reset()
                if d.get("filename"):
                    state["filename"] = d["filename"]
                info_now = info or {}
                if info_now.get("title"):
                    self.signals.progress.emit(task.id, {
                        "title": info_now.get("title"),
                        "thumbnail": info_now.get("thumbnail") or task.thumbnail,
                        "uploader": info_now.get("uploader") or info_now.get("channel") or task.uploader,
                        "duration": info_now.get("duration") or task.duration,
                    })
                self.signals.progress.emit(task.id, {
                    "status": TM.PROCESSING,
                    "progress": 1.0,
                    "detail": "正在处理",
                })

        def pp_hook(d: Dict[str, Any]) -> None:
            if task.canceled or self._is_paused(task.id):
                raise DownloadCancelled("用户已取消")
            name = str(d.get("postprocessor") or "")
            label = PP_NAMES.get(name)
            if not label:
                return
            if d.get("status") == "started":
                self.signals.progress.emit(task.id, {
                    "status": TM.PROCESSING,
                    "progress": 1.0,
                    "detail": label,
                })

        def sink(line: str) -> None:
            if line:
                self.signals.logline.emit(task.id, line)

        try:
            opts = build_options(task, self.settings, hook, pp_hook, _Logger(sink))
            self.signals.progress.emit(task.id, {
                "status": TM.ANALYZING,
                "detail": "正在获取媒体信息",
            })
            with yt_dlp.YoutubeDL(opts) as ydl:
                self._ydls[task.id] = ydl
                info = ydl.extract_info(task.url, download=True)
                final = self._final_path(ydl, info, state)

            if not task.canceled:
                wrote = self._write_danmaku(task, final)
                if wrote:
                    self.signals.logline.emit(task.id, "已写出弹幕：" + "、".join(wrote))

            if task.canceled:
                raise DownloadCancelled("用户已取消")
            self.signals.finished.emit(task.id, {"path": final, "info": _sanitize(info)})
        except DownloadCancelled:
            self.signals.failed.emit(task.id, "__canceled__")
        except yt_dlp.utils.DownloadError as exc:
            title, detail = format_detail(_clean(str(exc)), "下载失败")
            self.signals.failed.emit(task.id, detail + "\x00" + title)
        except Exception as exc:  # noqa: BLE001
            title, detail = format_detail(_clean(f"{type(exc).__name__}: {exc}"), "下载失败")
            self.signals.failed.emit(task.id, detail + "\x00" + title)
        finally:
            self._ydls.pop(task.id, None)

    def _write_danmaku(self, task: Task, final: str) -> List[str]:
        """哔哩哔哩专用：下载完成后按设置写出弹幕。"""
        cfg = self.settings
        want_xml = bool(cfg.get("bili_danmaku_xml"))
        want_json = bool(cfg.get("bili_danmaku_json"))
        want_ass = bool(cfg.get("bili_danmaku_ass"))
        if not (want_xml or want_json or want_ass):
            return []
        if not is_bilibili_url(task.url):
            return []
        try:
            base = Path(final).with_suffix("") if final else None
            if base is None:
                return []
            return download_danmaku(task.url, base, want_xml, want_json, want_ass, task.title)
        except Exception:
            return []   # 弹幕失败不影响下载结果

    @staticmethod
    def _final_path(ydl, info: Any, state: Dict[str, Any]) -> str:
        if not isinstance(info, dict):
            return state.get("filename", "")
        for item in (info.get("requested_downloads") or []):
            fp = item.get("filepath")
            if fp and os.path.exists(fp):
                return fp
        try:
            fp = ydl.prepare_filename(info)
        except Exception:
            fp = ""
        if fp and os.path.exists(fp):
            return fp
        if fp:
            base, _ = os.path.splitext(fp)
            for ext in (".mp4", ".mkv", ".webm", ".mp3", ".m4a", ".opus",
                        ".flac", ".wav", ".aac", ".ogg", ".mov", ".avi"):
                if os.path.exists(base + ext):
                    return base + ext
        if state.get("filename") and os.path.exists(state["filename"]):
            return state["filename"]
        return fp or state.get("filename", "")

    # ------------------------------------------------------------------
    # 主线程回调
    # ------------------------------------------------------------------
    def _on_progress(self, task_id: str, patch: Dict[str, Any]) -> None:
        task = self.model.get(task_id)
        if task is None:
            return
        # 暂停（或已被取消）之后，取消前发出的进度信号可能还在事件队列里，
        # 直接丢弃，否则状态会被改回「下载中」。
        if task.status == TM.PAUSED or task.canceled:
            return
        status = patch.get("status")
        if status == TM.DOWNLOADING and task.status != TM.DOWNLOADING:
            self.taskStarted.emit(task_id)
        if status:
            task.status = status
        for key in ("detail", "title", "thumbnail", "uploader"):
            if key in patch and patch[key]:
                setattr(task, key, patch[key])
        if "duration" in patch and patch["duration"]:
            task.duration = float(patch["duration"])
        downloaded = int(patch.get("downloaded") or 0)
        total = int(patch.get("total") or 0)
        if downloaded:
            task.downloaded = downloaded
        if total:
            task.total = total
        if total > 0:
            task.progress = min(1.0, downloaded / total)
        elif "progress" in patch:
            task.progress = float(patch["progress"])
        if "speed" in patch:
            task.speed = float(patch.get("speed") or 0)
        if "eta" in patch:
            task.eta = patch.get("eta")
        if patch.get("playlist_index"):
            task.playlist_index = int(patch["playlist_index"])
        if patch.get("playlist_count"):
            task.playlist_count = int(patch["playlist_count"])
        self.model.touch(task_id)
        self.statsChanged.emit()

    def _on_log(self, task_id: str, line: str) -> None:
        task = self.model.get(task_id)
        if task is None:
            return
        log: List[str] = task.extra.setdefault("log", [])
        log.append(line)
        if len(log) > 60:
            del log[:-60]

    def _on_finished(self, task_id: str, payload: Dict[str, Any]) -> None:
        task = self.model.get(task_id)
        if task is None:
            return
        # 暂停 / 取消之后迟到的「下载完成」必须丢掉：用户刚点了暂停，状态却被改成
        # 已完成，看着就像暂停没生效。文件其实已经下完，继续时会命中「已下载过」
        # 的分支，不会重复下载。
        if self._is_paused(task_id) or task.canceled or task.status in (TM.PAUSED, TM.CANCELED):
            return
        info = payload.get("info") or {}
        task.status = TM.COMPLETED
        task.progress = 1.0
        task.speed = 0.0
        task.eta = None
        task.detail = "已完成"
        task.filepath = payload.get("path") or ""
        if info.get("title"):
            task.title = info["title"]
        if info.get("thumbnail"):
            task.thumbnail = info["thumbnail"]
        if info.get("uploader"):
            task.uploader = info["uploader"]
        if info.get("duration"):
            task.duration = float(info["duration"])
        if not task.total and task.downloaded:
            task.total = task.downloaded
        task.finished_at = time.time()
        self.model.touch(task_id)
        self.taskDone.emit(task_id)
        self.statsChanged.emit()
        self.pump()

    def _on_failed(self, task_id: str, message: str) -> None:
        task = self.model.get(task_id)
        if task is None:
            return
        if message == "__canceled__":
            if self._is_paused(task_id):
                # 中断只是为了暂停：保留断点，等用户点「继续下载」
                task.status = TM.PAUSED
                task.detail = "已暂停"
                task.canceled = True
                task.speed = 0.0
                task.eta = None
                self.model.touch(task_id)
                self.statsChanged.emit()
                return
            if task.status in (TM.QUEUED, TM.PAUSED):
                # 用户已经点了「继续下载」（甚至又点了取消），只是旧线程还没退干净 ——
                # 这条取消是它留下的尾巴，按当前状态为准，别把刚恢复的任务打回已取消。
                queued = task.status == TM.QUEUED
                task.canceled = not queued
                self.model.touch(task_id)
                self.statsChanged.emit()
                if queued:
                    self.pump()
                return
            task.status = TM.CANCELED
            task.detail = "已取消"
            task.canceled = False
        else:
            detail, _, title = message.partition("\x00")
            task.status = TM.FAILED
            task.error = detail
            task.error_kind = title or "下载失败"
            task.detail = task.error_kind
            task.canceled = False
        task.speed = 0.0
        task.eta = None
        self.model.touch(task_id)
        self.taskDone.emit(task_id)
        self.statsChanged.emit()
        self.pump()

    # ------------------------------------------------------------------
    @Slot(str)
    def cancel(self, task_id: str) -> None:
        task = self.model.get(task_id)
        if task is None:
            return
        task.canceled = True
        if task.status in (TM.QUEUED, TM.PAUSED):
            self._paused.discard(task_id)
            task.status = TM.CANCELED
            task.detail = "已取消"
            task.canceled = False
            self.model.touch(task_id)
            self.statsChanged.emit()

    @Slot(str)
    def retry(self, task_id: str) -> None:
        task = self.model.get(task_id)
        if task is None:
            return
        self._paused.discard(task_id)
        task.canceled = False
        task.error = ""
        task.error_kind = ""
        task.progress = 0.0
        task.downloaded = 0
        task.speed = 0.0
        task.eta = None
        task.status = TM.QUEUED
        task.detail = ""
        self.model.touch(task_id)
        self.pump()

    @Slot()
    def cancelAll(self) -> None:
        for task in self.model.all_tasks():
            if task.status in (TM.QUEUED, TM.PAUSED, TM.ANALYZING,
                               TM.DOWNLOADING, TM.PROCESSING):
                self.cancel(task.id)

    @Slot(str)
    def pause(self, task_id: str) -> None:
        """暂停 = 中断当前下载（保留 .part 断点），继续时自动续传。"""
        task = self.model.get(task_id)
        if task is None:
            return
        if task.status in (TM.QUEUED, TM.PAUSED):
            # 还没真正开始：直接挂起，调度时会被跳过
            if task.status == TM.PAUSED:
                return
            self._paused.add(task_id)
            task.status = TM.PAUSED
            task.detail = "已暂停"
            self.model.touch(task_id)
            self.statsChanged.emit()
            return
        if task.status not in (TM.ANALYZING, TM.DOWNLOADING, TM.PROCESSING):
            return
        self._paused.add(task_id)
        # 置位后下载线程会在下一个回调点抛出取消，.part 断点保留
        task.canceled = True
        task.status = TM.PAUSED
        task.detail = "已暂停"
        task.speed = 0.0
        task.eta = None
        self.model.touch(task_id)
        self.statsChanged.emit()

    @Slot(str)
    def resume(self, task_id: str) -> None:
        """继续：重新排队，yt-dlp 会从 .part 断点续传。"""
        task = self.model.get(task_id)
        if task is None:
            return
        self._paused.discard(task_id)
        if task.status != TM.PAUSED:
            return
        task.canceled = False
        task.error = ""
        task.error_kind = ""
        task.status = TM.QUEUED
        task.detail = "等待开始"
        task.speed = 0.0
        task.eta = None
        self.model.touch(task_id)
        self.pump()

    @Slot(result="QVariantMap")
    def stats(self) -> Dict[str, Any]:
        tasks = self.model.all_tasks()
        active = [t for t in tasks if t.status == TM.DOWNLOADING]
        total_speed = sum(t.speed for t in active)
        remaining = sum(max(0, t.total - t.downloaded) for t in tasks
                        if t.status in (TM.DOWNLOADING, TM.QUEUED, TM.PAUSED))
        return {
            "active": len(active),
            "queued": len([t for t in tasks if t.status == TM.QUEUED]),
            "paused": len([t for t in tasks if t.status == TM.PAUSED]),
            "done": len([t for t in tasks if t.status == TM.COMPLETED]),
            "failed": len([t for t in tasks if t.status == TM.FAILED]),
            "speed": total_speed,
            "remaining": remaining,
            "total": len(tasks),
        }


def _sanitize(obj: Any, depth: int = 0) -> Any:
    if depth > 6:
        return None
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if not isinstance(k, str):
                continue
            try:
                out[k] = _sanitize(v, depth + 1)
            except Exception:
                continue
        return out
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v, depth + 1) for v in obj]
    return str(obj)


# ----------------------------------------------------------------------
class Analyzer(QObject):
    """后台解析 URL 元信息。"""

    done = Signal(str, dict)
    failed = Signal(str, str)

    def __init__(self, settings: Settings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.signals = _Signals()
        self.signals.analyze_ok.connect(self.done)
        self.signals.analyze_fail.connect(self.failed)

    def start(self, url: str) -> None:
        threading.Thread(target=self._work, args=(url,), daemon=True,
                         name="analyze").start()

    FLAT_LIMIT = 30   # 超过这个数量就不再二次解析，避免等待过久

    @staticmethod
    def _needs_full_pass(info: Any) -> bool:
        """flat 模式下拿不到标题时（例如哔哩哔哩的分P），改用完整解析。"""
        if not isinstance(info, dict):
            return False
        entries = [e for e in (info.get("entries") or []) if isinstance(e, dict)]
        if not entries or len(entries) > Analyzer.FLAT_LIMIT:
            return False
        named = sum(1 for e in entries if str(e.get("title") or "").strip())
        return named * 2 < len(entries)

    # 带登录凭据反而被拒时的错误特征。
    # YouTube 在收到某些 Cookie 后会要求 reload 或直接不返回格式，
    # 而不带 Cookie 的匿名请求反而是正常的。
    _RETRY_ANONYMOUS = re.compile(
        r"page needs to be reloaded|requested format is not available|"
        r"sign in to confirm|not a bot|failed to extract any player response|"
        r"no video formats found|unable to extract",
        re.I)

    # 「凭据被明确拒绝」的特征：这些错误才是登录 Cookie 惹的祸，
    # 只有它们才值得标记「登录 Cookie 暂时失效」。通用的机器人风控
    # （sign in to confirm / not a bot）属于限流，与登录无关，不应牵连。
    _COOKIE_HARMFUL = re.compile(
        r"page needs to be reloaded|requested format is not available|"
        r"failed to extract any player response",
        re.I)

    # 明确「无法访问」的错误：视频已删除 / 私享 / 地区限制 / 404。
    # 匿名重试若给出这类错误，说明问题不在凭据，应该用它上报，避免用
    # 含糊的风控报错误导用户去登录。
    _DEFINITIVE = re.compile(
        r"video unavailable|is unavailable|removed by the uploader|"
        r"has been deleted|no longer available|content is not available|"
        r"private video|this video is private|"
        r"not available in your country|not available from your location|"
        r"http error 404|404 not found|playlist does not exist",
        re.I)

    @staticmethod
    def _extract(opts: Dict[str, Any], url: str) -> Any:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    def _work(self, url: str) -> None:
        # 解析阶段平时不显示日志，但要留一份用于识别「视频有、账号拿不到」的画质
        lines: List[str] = []
        logger = _Logger(lines.append)
        first_error: Exception | None = None
        try:
            opts = analyze_options(self.settings, logger, url)
            info = self._extract(opts, url)
            if self._needs_full_pass(info):
                full = dict(opts)
                full["extract_flat"] = False
                full["playlistend"] = self.FLAT_LIMIT
                try:
                    richer = self._extract(full, url)
                    if any(isinstance(e, dict) and str(e.get("title") or "").strip()
                           for e in (richer.get("entries") or [])):
                        info = richer
                except Exception:  # noqa: BLE001
                    pass   # 二次解析失败就沿用 flat 结果
            payload = sanitize_result(info, url)
            payload["unavailableQualities"] = parse_missing_qualities(lines)
            self.signals.analyze_ok.emit(url, payload)
            return
        except Exception as exc:  # noqa: BLE001
            first_error = exc

        # 凭据可能「有害」：YouTube 拿到 Cookie 后反而拒绝服务。
        # 此时彻底去掉 Cookie 再解析一次，避免整个解析流程直接失败。
        if self._should_retry_anonymously(url, first_error):
            # 只有「凭据被明确拒绝」时才标记登录 Cookie 失效，避免把
            # 与凭据无关的机器人风控也算到登录头上，导致用户刚登录却被
            # 无谓地忽略两小时。
            if Analyzer._COOKIE_HARMFUL.search(_clean(str(first_error))):
                mark_login_cookie_bad(url)
            try:
                anon = analyze_options(self.settings, logger, url,
                                      use_cookies=False)
                info = self._extract(anon, url)
                payload = sanitize_result(info, url)
                payload["unavailableQualities"] = parse_missing_qualities(lines)
                payload["anonymous"] = True    # 下载阶段要沿用同样的降级模式
                self.signals.analyze_ok.emit(url, payload)
                return
            except Exception as anon_exc:  # noqa: BLE001
                # 降级也失败：若匿名给出的错误更「确定」（例如视频已删除、
                # 地区限制），就用它上报 —— 这比含糊的风控报错更有指导意义。
                if Analyzer._DEFINITIVE.search(_clean(str(anon_exc))):
                    first_error = anon_exc

        self._emit_failure(url, first_error)

    @staticmethod
    def _should_retry_anonymously(url: str, exc: Exception) -> bool:
        """是否值得改用匿名重试。哔哩哔哩依赖登录，匿名重试反而更差。"""
        if exc is None or is_bilibili_url(url):
            return False
        return bool(Analyzer._RETRY_ANONYMOUS.search(_clean(str(exc))))

    def _emit_failure(self, url: str, exc: Exception) -> None:
        """上报解析失败。

        hint 必须非空：界面把它当作正文显示，为空会导致错误被“吞掉”，
        用户只看到界面莫名其妙回到初始状态。
        """
        if isinstance(exc, yt_dlp.utils.DownloadError):
            raw = _clean(str(exc))
        else:
            raw = _clean(f"{type(exc).__name__}: {exc}")
        title, _detail = format_detail(raw, "解析失败")
        hint = describe_hint(raw) or "请稍后重试；展开下方“原始信息”可查看详细原因。"
        self.signals.analyze_fail.emit(url, title + "\x00" + hint + "\x00" + raw)


def sanitize_result(info: Any, url: str) -> Dict[str, Any]:
    """把 yt-dlp 的 info 字典整理成 QML 友好的结构。"""
    if not isinstance(info, dict):
        return {"type": "error", "url": url, "message": "无法解析该链接"}

    entries_raw = info.get("entries")
    if entries_raw:
        top_title = str(info.get("title") or "")
        entries = []
        for i, e in enumerate(entries_raw):
            if not isinstance(e, dict):
                continue
            entries.append({
                "index": i + 1,
                "id": str(e.get("id") or ""),
                "title": _entry_title(e, top_title, i + 1),
                "url": _entry_url(e, url),
                "thumbnail": str(e.get("thumbnail") or (e.get("thumbnails") or [{}])[-1].get("url") or ""),
                "uploader": str(e.get("uploader") or e.get("channel") or info.get("uploader") or info.get("title") or ""),
                "duration": float(e.get("duration") or 0),
                "durationText": human_duration(e.get("duration")) if e.get("duration") else "",
                "isLive": bool(e.get("is_live")),
            })
        if not entries:
            return {"type": "error", "url": url, "message": "播放列表为空或无法访问"}
        # 分P/合集在 flat 模式下没有顶层封面，退回用第一个项目的封面
        playlist_thumb = str(info.get("thumbnail") or "")
        if not playlist_thumb and entries:
            playlist_thumb = entries[0].get("thumbnail") or ""

        # 汇总各分P实际可用的 qn，供界面判断哪些档位可选
        qset = set()
        for entry in [e for e in entries_raw if isinstance(e, dict)][:8]:
            for fmt in (entry.get("formats") or []):
                if isinstance(fmt, dict) and fmt.get("quality"):
                    qset.add(int(fmt["quality"]))

        return {
            "type": "playlist",
            "url": url,
            "webpage_url": str(info.get("webpage_url") or url),
            "title": str(info.get("title") or "播放列表"),
            "uploader": str(info.get("uploader") or info.get("channel") or ""),
            "thumbnail": playlist_thumb,
            "entryCount": len(entries),
            "entries": entries,
            "extractor": str(info.get("extractor_key") or info.get("extractor") or ""),
            # 合集没有单一的时长/画质，这里补上字段避免界面取到 undefined
            "duration": 0.0,
            "durationText": "",
            "isLive": False,
            "formatCount": 0,
            "formats": [],
            "heights": [],
            "maxHeight": 0,
            "maxFps": 0.0,
            "isBilibili": is_bilibili_url(str(info.get("webpage_url") or url)),
            "qualities": sorted(qset, reverse=True),
            "audioQualities": [],
        }

    formats = []
    for f in (info.get("formats") or []):
        if not isinstance(f, dict):
            continue
        size = f.get("filesize") or f.get("filesize_approx") or 0
        estimated = False
        if not size:
            # 哔哩哔哩等站点只给码率，按 码率 × 时长 估算体积
            tbr = float(f.get("tbr") or 0)
            dur = float(info.get("duration") or 0)
            if tbr > 0 and dur > 0:
                size = int(tbr * 1000 * dur / 8)
                estimated = True
        formats.append({
            "formatId": str(f.get("format_id") or ""),
            "quality": int(f.get("quality") or 0),
            "ext": str(f.get("ext") or ""),
            "resolution": str(f.get("resolution") or ""),
            "height": int(f.get("height") or 0),
            "width": int(f.get("width") or 0),
            "fps": float(f.get("fps") or 0),
            "vcodec": str(f.get("vcodec") or ""),
            "acodec": str(f.get("acodec") or ""),
            "abr": float(f.get("abr") or 0),
            "tbr": float(f.get("tbr") or 0),
            "filesize": int(size or 0),
            "filesizeEstimated": estimated,
            "filesizeText": (("约 " + human_size(size)) if estimated else human_size(size))
                            if size else "未知",
            "codec": codec_label(f),
            "codecKey": codec_key(f),
            "label": _format_label(f),
            "shortLabel": _format_label(f, brief=True),
            "note": str(f.get("format_note") or ""),
            "hasVideo": f.get("vcodec") not in (None, "none"),
            "hasAudio": f.get("acodec") not in (None, "none"),
            "language": str(f.get("language") or ""),
            "protocol": str(f.get("protocol") or ""),
            "isDefault": bool(f.get("format_id") == info.get("format_id")),
        })
    formats.sort(key=lambda x: (-(x["height"] or 0), -(x["tbr"] or 0)))

    thumb = info.get("thumbnail") or ""
    if not thumb:
        thumbs = info.get("thumbnails") or []
        if thumbs:
            thumb = thumbs[-1].get("url") or ""

    extractor = str(info.get("extractor_key") or info.get("extractor") or "")
    extractor = EXTRACTOR_NAMES.get(extractor, extractor)

    # 实际可下载到的画质，用于让界面只显示真正可选的档位
    heights = sorted({int(f["height"]) for f in formats
                      if f["hasVideo"] and f["height"] > 0}, reverse=True)
    max_height = heights[0] if heights else 0
    max_fps = 0.0
    for f in formats:
        if f["hasVideo"] and int(f["height"] or 0) == max_height:
            max_fps = max(max_fps, float(f["fps"] or 0))

    # 哔哩哔哩：接口返回的 qn，用于判断哪些画质/音质档位真实可用
    qualities = sorted({f["quality"] for f in formats if f.get("quality")}, reverse=True)
    audio_qualities = sorted({f["formatId"] for f in formats if not f["hasVideo"]})

    # 字幕语言：手工字幕 + 自动生成字幕，去重后排序，供界面多选
    _subs = info.get("subtitles") or {}
    _auto = info.get("automatic_captions") or {}
    sub_langs = sorted(set(list(_subs.keys()) + list(_auto.keys())))

    return {
        "type": "video",
        "url": url,
        "webpage_url": str(info.get("webpage_url") or url),
        "id": str(info.get("id") or ""),
        "title": str(info.get("title") or "未知标题"),
        "uploader": str(info.get("uploader") or info.get("channel") or info.get("uploader_id") or ""),
        "thumbnail": str(thumb),
        "duration": float(info.get("duration") or 0),
        "durationText": human_duration(info.get("duration")) if info.get("duration") else "实时流" if info.get("is_live") else "",
        "viewCount": int(info.get("view_count") or 0),
        "likeCount": int(info.get("like_count") or 0),
        "uploadDate": str(info.get("upload_date") or ""),
        "description": str(info.get("description") or "")[:2000],
        "extractor": extractor,
        "isLive": bool(info.get("is_live")),
        "formats": formats,
        "formatCount": len(formats),
        "playlistCount": int(info.get("playlist_count") or 0),
        "heights": heights,
        "maxHeight": max_height,
        "maxFps": max_fps,
        "isBilibili": is_bilibili_url(str(info.get("webpage_url") or url)),
        "qualities": qualities,
        "audioQualities": audio_qualities,
        "subtitles": sub_langs,
    }
