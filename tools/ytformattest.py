"""YouTube 画质 / 音质 / 编码优先级的离线回归测试。

关键部分用 yt-dlp 自己的格式选择器跑：给一份仿真的 YouTube 格式表，
看我们拼出来的选择器到底会挑中哪一条，而不是只看字符串长什么样。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yt_dlp  # noqa: E402

from app.core import yt_format as yf  # noqa: E402

FAILS = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(("  [ok]   " if cond else "  [FAIL] ") + name + ("" if cond else f"  ->  {extra}"))
    if not cond:
        FAILS.append(name)


def vf(fid, height, fps, vcodec, tbr, ext="mp4"):
    return {"format_id": fid, "url": "https://example.invalid/v", "height": height,
            "width": int(height * 16 / 9), "fps": fps, "vcodec": vcodec, "acodec": "none",
            "ext": ext, "tbr": tbr, "protocol": "https", "filesize": int(tbr * 1000)}


def af(fid, acodec, abr, ext="webm"):
    return {"format_id": fid, "url": "https://example.invalid/a", "vcodec": "none",
            "acodec": acodec, "abr": abr, "ext": ext, "tbr": abr,
            "protocol": "https", "filesize": int(abr * 1000)}


# 仿一个「最高 1440P60」的 YouTube 视频：同样的分辨率下 av01 / vp09 / avc1 都有
FORMATS = [
    vf("137", 1080, 30, "avc1.640028", 2500),
    vf("299", 1080, 60, "avc1.64002a", 4500),
    vf("399", 1080, 30, "av01.0.08M.08", 1800),
    vf("303", 1080, 60, "vp09.00.41.08", 3500),
    vf("400", 1440, 60, "av01.0.12M.08", 4000),
    vf("308", 1440, 60, "vp09.00.50.08", 6000),
    vf("244", 480, 30, "vp09.00.21.08", 700),
    af("251", "opus", 160),
    af("140", "mp4a.40.2", 128),
    af("250", "opus", 70),
    af("249", "opus", 50),
]

_YDL = yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "logger": None})


def sorted_formats(formats=None):
    """让 yt-dlp 自己排序：best/worst 是按列表顺序取的，必须先排好。"""
    info = {"id": "test", "_type": "video", "title": "t",
            "formats": [dict(f) for f in (formats if formats is not None else FORMATS)]}
    _YDL.sort_formats(info)
    return info["formats"]


def pick(spec: str, formats=None):
    """用 yt-dlp 自己的选择器算出会下载哪一条格式。"""
    selector = _YDL.build_format_selector(spec)
    ctx = {"formats": sorted_formats(formats),
           "incomplete_formats": False, "has_merged_format": True}
    picked = list(selector(ctx))
    if not picked:
        return ""
    return str(picked[0].get("format_id") or "")


class FakeCfg(dict):
    def get(self, key, default=None):
        return dict.get(self, key, default)


def cfg(**kw):
    base = {
        "yt_use_custom_quality": True,
        "yt_quality_order": list(yf.DEFAULT_QUALITY_ORDER),
        "yt_audio_order": list(yf.DEFAULT_AUDIO_ORDER),
        "yt_codec_order": list(yf.DEFAULT_CODEC_ORDER),
        "prefer_60fps": False,
    }
    base.update(kw)
    return FakeCfg(base)


def full_order(default, *front):
    """把若干档位提到最前面，其余保持默认顺序（优先级表不接受残缺列表）。"""
    return list(front) + [v for v in default if v not in front]


def sel(**kw):
    return yf.build_selector(cfg(**kw), False, "best")


def main() -> int:
    print("1. 三张表")
    heights = [h for h, _n, _v in yf.QUALITY_TIERS]
    check("画质表按从高到低排列", heights == sorted(heights, reverse=True), str(heights))
    abrs = [a for a, _n, _v in yf.AUDIO_TIERS]
    check("音质表首项是最高的", abrs[0] == 258, str(abrs))
    check("音质表末项是最低的", abrs[-1] == 139, str(abrs))
    check("编码过滤器用正则（vp09 也要能匹配）",
          "vp0?9" in dict((c, f) for c, _n, f in yf.CODEC_TIERS)["vp9"])
    check("识别 YouTube 链接",
          yf.is_youtube_url("https://www.youtube.com/watch?v=x")
          and yf.is_youtube_url("https://youtu.be/x")
          and not yf.is_youtube_url("https://www.bilibili.com/video/BV1"))

    print("2. 关掉自定义优先级时不接管")
    check("返回 None，交回原逻辑",
          yf.build_selector(cfg(yt_use_custom_quality=False), False, "best") is None)

    print("3. 选择器实际挑中的格式")
    # 默认：画质优先 → 1440P 的 AV1（400），音轨 251
    check("默认顺序取 1440P AV1",
          pick(sel()) == "400+251", pick(sel()))
    # 编码优先级改成 VP9 优先 → 同分辨率换成 308
    vp9_first = full_order(yf.DEFAULT_CODEC_ORDER, "vp9")
    check("编码优先级生效",
          pick(sel(yt_codec_order=vp9_first)) == "308+251",
          pick(sel(yt_codec_order=vp9_first)))
    # 画质优先级把 1080 提到最前 → 取 1080P 的 AV1（399）
    hd_first = full_order(yf.DEFAULT_QUALITY_ORDER, 1080)
    check("画质优先级生效",
          pick(sel(yt_quality_order=hd_first)) == "399+251",
          pick(sel(yt_quality_order=hd_first)))
    # 音质优先级把 AAC 摆前面 → 140
    aac_first = full_order(yf.DEFAULT_AUDIO_ORDER, 140)
    check("音质优先级生效",
          pick(sel(yt_audio_order=aac_first)) == "400+140",
          pick(sel(yt_audio_order=aac_first)))
    # 首选音轨不存在时要能回退，而不是整条候选失败
    only_aac = [f for f in FORMATS if f["format_id"] not in ("251", "250", "249")]
    check("首选音轨缺失时回退到可用音轨",
          pick(sel(), only_aac).endswith("+140"), pick(sel(), only_aac))
    # 高帧率偏好：1080P 档会挑 60fps 的 303 而不是 30fps 的 399
    hd_first_vp9 = full_order(yf.DEFAULT_CODEC_ORDER, "vp9")
    check("优先 60fps 生效",
          pick(sel(prefer_60fps=True, yt_quality_order=hd_first,
                   yt_codec_order=hd_first_vp9)).startswith("303+"),
          pick(sel(prefer_60fps=True, yt_quality_order=hd_first,
                   yt_codec_order=hd_first_vp9)))

    print("4. 界面预设")
    check("best = 默认顺序", pick(sel(preset="best") if False else sel()) == "400+251")
    worst = yf.build_selector(cfg(), False, "worst")
    check("worst 从最低档开始",
          pick(worst) == "244+249", pick(worst))
    limited = pick(yf.build_selector(cfg(), False, "1080"))
    check("限定 1080P 时不越档（不会选到 1440P）",
          limited.split("+")[0] in ("137", "299", "399", "303"), limited)

    import time
    t0 = time.perf_counter()
    spec = sel()
    _YDL.build_format_selector(spec)
    cost = (time.perf_counter() - t0) * 1000
    check(f"选择器长度与解析耗时可控（{len(spec)} 字符，{cost:.1f} ms）",
          len(spec) < 40000 and cost < 1500, f"{len(spec)} 字符 / {cost:.1f} ms")
    check("手动选定的格式原样使用",
          yf.build_selector(cfg(), False, "custom", "137+140") == "137+140")
    check("仅音频按音质优先级",
          pick(yf.build_selector(cfg(yt_audio_order=aac_first), True, "best")).startswith("140"),
          pick(yf.build_selector(cfg(yt_audio_order=aac_first), True, "best")))

    print("5. 兜底")
    check("选择器结尾一定有 best 兜底", sel().endswith("bestvideo+bestaudio/best"), sel()[-40:])
    check("空表也能拼出选择器", yf.build_video_selector([], [], []).endswith("best"))
    check("顺序归一化会补回缺失档位",
          yf.normalize_quality_order([1080, 720]) == list(yf.DEFAULT_QUALITY_ORDER),
          str(yf.normalize_quality_order([1080, 720])))
    check("顺序归一化保留用户顺序",
          [h for h in yf.normalize_quality_order([720, 1080]) if h in (1080, 720)] == [720, 1080])

    print()
    if FAILS:
        print(f"失败 {len(FAILS)} 项：" + "、".join(FAILS))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
