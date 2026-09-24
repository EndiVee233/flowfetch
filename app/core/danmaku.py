"""哔哩哔哩弹幕下载与转换。

yt-dlp 不提供弹幕下载，这里直接调用哔哩哔哩的公开接口：

1. view 接口按 bvid 取分P列表，得到每一P的 cid；
2. dm/list.so 接口按 cid 取弹幕，返回 deflate 压缩的 XML；
3. 按需写出 xml / json / ass 三种格式。

XML 的 p 属性依次为：出现时间, 模式, 字号, 颜色, 时间戳, 弹幕池, 发送者, 行号。
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.request
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

VIEW_API = "https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
DM_API = "https://api.bilibili.com/x/v1/dm/list.so?oid={cid}"

_D_RE = re.compile(r'<d p="([^"]+)">(.*?)</d>', re.S)
_BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
_P_RE = re.compile(r"[?&]p=(\d+)")

# 弹幕模式
MODE_SCROLL = (1, 2, 3)
MODE_BOTTOM = 4
MODE_TOP = 5
MODE_REVERSE = 6


def _ssl():
    try:
        return ssl.create_default_context()
    except Exception:
        return ssl._create_unverified_context()  # type: ignore[attr-defined]


def _get(url: str, raw: bool = False):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    req.add_header("Referer", "https://www.bilibili.com/")
    with urllib.request.urlopen(req, timeout=25, context=_ssl()) as resp:
        data = resp.read()
    if raw:
        return data
    return json.loads(data.decode("utf-8", "replace"))


def parse_url(url: str) -> Tuple[str, int]:
    """从视频链接里取出 (bvid, 分P序号)。"""
    match = _BV_RE.search(url or "")
    bvid = match.group(1) if match else ""
    page = _P_RE.search(url or "")
    return bvid, int(page.group(1)) if page else 1


def fetch_cid(bvid: str, page: int = 1, cookies: Optional[Dict[str, str]] = None) -> int:
    data = _get(VIEW_API.format(bvid=bvid))
    pages = ((data.get("data") or {}).get("pages") or [])
    for item in pages:
        if int(item.get("page") or 0) == page:
            return int(item.get("cid") or 0)
    if pages:
        return int(pages[0].get("cid") or 0)
    return 0


def fetch_xml(cid: int) -> str:
    raw = _get(DM_API.format(cid=cid), raw=True)
    try:
        return zlib.decompress(raw, -zlib.MAX_WBITS).decode("utf-8", "replace")
    except zlib.error:
        return raw.decode("utf-8", "replace")


def parse_xml(xml: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for match in _D_RE.finditer(xml or ""):
        parts = match.group(1).split(",")
        if len(parts) < 8:
            continue
        text = match.group(2)
        text = (text.replace("&amp;", "&").replace("&lt;", "<")
                    .replace("&gt;", ">").replace("&quot;", '"')
                    .replace("&#39;", "'"))
        try:
            out.append({
                "time": float(parts[0]),
                "mode": int(parts[1]),
                "size": int(parts[2]),
                "color": int(parts[3]),
                "timestamp": int(parts[4]),
                "pool": int(parts[5]),
                "uid": parts[6],
                "rowid": parts[7],
                "text": text,
            })
        except ValueError:
            continue
    out.sort(key=lambda d: d["time"])
    return out


def write_json(items: List[Dict[str, Any]], path: Path) -> None:
    payload = {
        "code": 0,
        "count": len(items),
        "data": [{
            "id": it["rowid"],
            "progress": int(it["time"] * 1000),
            "mode": it["mode"],
            "fontsize": it["size"],
            "color": it["color"],
            "midHash": it["uid"],
            "content": it["text"],
            "ctime": it["timestamp"],
            "pool": it["pool"],
        } for it in items],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:d}:{minutes:02d}:{secs:05.2f}"


def _ass_color(rgb: int) -> str:
    r = (rgb >> 16) & 0xFF
    g = (rgb >> 8) & 0xFF
    b = rgb & 0xFF
    return f"&H00{b:02X}{g:02X}{r:02X}"


def write_ass(items: List[Dict[str, Any]], path: Path,
              width: int = 1920, height: int = 1080, title: str = "") -> None:
    """把弹幕写成 ASS 字幕（滚动弹幕按泳道避让）。"""
    font_size = max(20, int(height / 40))
    lane_height = int(font_size * 1.35)
    lanes = max(1, int((height * 0.85) // lane_height))
    scroll_duration = 8.0
    static_duration = 4.0

    lane_free: List[float] = [0.0] * lanes          # 滚动弹幕泳道占用到的时间
    top_used: List[float] = [0.0] * lanes
    bottom_used: List[float] = [0.0] * lanes

    def take(lane_time: List[float], now: float, hold: float) -> Optional[int]:
        for i, free_at in enumerate(lane_time):
            if free_at <= now:
                lane_time[i] = now + hold
                return i
        return None

    header = [
        "[Script Info]",
        f"Title: {title}",
        "ScriptType: v4.00+",
        "WrapStyle: 2",
        "PlayResX: %d" % width,
        "PlayResY: %d" % height,
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Danmaku,Microsoft YaHei UI,{font_size},&H00FFFFFF,&H00FFFFFF,"
        f"&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,2,1,7,0,0,0,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text",
    ]

    events: List[str] = []
    for it in items:
        text = (it["text"] or "").replace("\\", "＼").replace("{", "｛").replace("}", "｝")
        text = text.replace("\n", " ")
        if not text.strip():
            continue
        start = it["time"]
        color = _ass_color(it["color"]) if it["color"] else "&H00FFFFFF"
        mode = it["mode"]

        if mode in MODE_SCROLL or mode == MODE_REVERSE:
            lane = take(lane_free, start, scroll_duration * 0.6)
            if lane is None:
                continue
            y = lane_height // 2 + lane * lane_height + 4
            if mode == MODE_REVERSE:
                tags = (f"\\move({int(width * 0.12)},{y},{width + 200},{y})"
                        f"\\c{color}\\alpha&H19&")
            else:
                tags = (f"\\move({width + 200},{y},{int(-width * 0.15)},{y})"
                        f"\\c{color}\\alpha&H19&")
            end = start + scroll_duration
        elif mode == MODE_TOP:
            lane = take(top_used, start, static_duration)
            if lane is None:
                continue
            y = lane_height // 2 + lane * lane_height + 4
            tags = f"\\an8\\pos({width // 2},{y})\\c{color}"
            end = start + static_duration
        else:
            lane = take(bottom_used, start, static_duration)
            if lane is None:
                continue
            y = height - (lane_height // 2 + lane * lane_height + 4)
            tags = f"\\an2\\pos({width // 2},{y})\\c{color}"
            end = start + static_duration

        events.append("Dialogue: 0,%s,%s,Danmaku,,0,0,0,,{%s}%s"
                      % (_ass_time(start), _ass_time(end), tags, text))

    path.write_text("\n".join(header + events) + "\n", encoding="utf-8")


def download(url: str, base: Path, want_xml: bool = False, want_json: bool = False,
             want_ass: bool = False, title: str = "") -> List[str]:
    """下载指定分P的弹幕并写出需要的格式，返回实际生成的文件名列表。

    base 是不含扩展名的目标路径，生成的文件形如 base.danmaku.xml。
    """
    if not (want_xml or want_json or want_ass):
        return []
    bvid, page = parse_url(url)
    if not bvid:
        return []
    cid = fetch_cid(bvid, page)
    if not cid:
        return []
    items = parse_xml(fetch_xml(cid))
    if not items:
        return []
    written: List[str] = []
    if want_xml:
        target = Path(str(base) + ".danmaku.xml")
        target.write_text(fetch_xml(cid), encoding="utf-8")
        written.append(target.name)
    if want_json:
        target = Path(str(base) + ".danmaku.json")
        write_json(items, target)
        written.append(target.name)
    if want_ass:
        target = Path(str(base) + ".danmaku.ass")
        write_ass(items, target, title=title)
        written.append(target.name)
    return written
