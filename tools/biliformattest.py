"""哔哩哔哩画质档位表的离线回归测试。

覆盖三件事：
1. 档位表的顺序 / 文案与约定一致（界面上的「画质优先级」直接照抄这张表）；
2. 老的配置文件缺少新档位时会被补齐到正确位置 —— 画质 / 音质 / 编码三张表都要；
3. 生成出来的格式选择器真的带上了对应档位。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from app.core import config as cfgmod  # noqa: E402
from app.core import bili_format as bf  # noqa: E402

# 约定的档位表（顺序即默认优先级，来自 BBDown 的画质列表）
EXPECTED = [
    (127, "8K 超高清"),
    (126, "杜比视界"),
    (125, "HDR 真彩色"),
    (120, "4K 超高清"),
    (116, "1080P 60帧"),
    (112, "1080P 高码率"),
    (80, "1080P 高清"),
    (100, "AI智能修复"),
    (74, "720P 60帧"),
    (64, "720P 准高清"),
    (32, "480P 标清"),
    (16, "360P 流畅"),
    (6, "240P 极速"),
]

# 约定的音质 / 编码表（顺序即默认优先级）
EXPECTED_AUDIO = [
    (30251, "Hi-Res 无损", True),
    (30250, "杜比全景声", True),
    (30280, "192K", False),
    (30232, "132K", False),
    (30216, "64K", False),
]
EXPECTED_CODEC = [
    ("av1", "AV1"),
    ("hevc", "HEVC（H.265）"),
    ("avc", "AVC（H.264）"),
]

# 老版本保存下来的顺序：画质只有 12 档（没有 100），音质只有 4 档（没有 30251），
# 编码表里还残留着已经去掉的 "avc1"
LEGACY_QUALITY = [127, 126, 125, 120, 116, 112, 80, 74, 64, 32, 16, 6]
LEGACY_AUDIO = [30280, 30232, 30216, 99999]
LEGACY_CODEC = ["avc", "avc1", "hevc"]

FAILS = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(("  [ok]   " if cond else "  [FAIL] ") + name + ("" if cond else f"  ->  {extra}"))
    if not cond:
        FAILS.append(name)


def main() -> int:
    QCoreApplication(sys.argv)

    print("1. 档位表")
    actual = [(q, n) for q, n, _v in bf.QUALITY_TIERS]
    check("档位顺序与文案完全一致", actual == EXPECTED, str(actual))
    check("默认优先级 = 档位表顺序", bf.DEFAULT_QUALITY_ORDER == [q for q, _n in EXPECTED])
    check("qn=100 显示为 AI智能修复", bf.quality_name(100) == "AI智能修复", bf.quality_name(100))
    check("画质表带 vip 标记",
          bf.quality_table()[7] == {"value": 100, "label": "AI智能修复", "vip": True},
          str(bf.quality_table()[7]))

    print("2. 顺序归一化")
    merged = bf.normalize_quality_order(LEGACY_QUALITY)
    check("新档位插回默认位置（而不是追加到末尾）",
          merged == [q for q, _n in EXPECTED], str(merged))
    check("空值回落到默认顺序", bf.normalize_quality_order(None) == bf.DEFAULT_QUALITY_ORDER)
    check("丢弃未知档位并去重",
          bf.normalize_quality_order([120, 120, 999, 80]) ==
          [127, 126, 125, 120, 116, 112, 80, 100, 74, 64, 32, 16, 6],
          str(bf.normalize_quality_order([120, 120, 999, 80])))
    custom = bf.normalize_quality_order([80, 120, 6])
    check("用户已有的档位相对顺序不变",
          [v for v in custom if v in (80, 120, 6)] == [80, 120, 6], str(custom))

    print("2b. 音质 / 编码表也要归一化（此前只有画质表做了）")
    check("音质表内容一致",
          [(a, n, v) for a, n, v in bf.AUDIO_TIERS] == EXPECTED_AUDIO,
          str(bf.AUDIO_TIERS))
    check("编码表内容一致",
          [(c, n) for c, n, _f in bf.CODEC_TIERS] == EXPECTED_CODEC,
          str(bf.CODEC_TIERS))
    audio_fixed = bf.normalize_audio_order(LEGACY_AUDIO)
    check("老配置里的音质顺序被补齐到默认位置（不是追加到末尾）",
          audio_fixed == [a for a, _n, _v in EXPECTED_AUDIO], str(audio_fixed))
    check("音质表里的未知档位被丢掉，缺失档位回填",
          bf.normalize_audio_order([30280, 99999, 30232, 30216]) ==
          [30251, 30250, 30280, 30232, 30216],
          str(bf.normalize_audio_order([30280, 99999, 30232, 30216])))
    codec_fixed = bf.normalize_codec_order(LEGACY_CODEC)
    check("老配置里的编码顺序被补齐，已删除的 avc1 被丢掉",
          codec_fixed == ["av1", "avc", "hevc"], str(codec_fixed))
    check("用户排好的编码相对顺序保持不变",
          [v for v in bf.normalize_codec_order(["avc", "av1"]) if v in ("avc", "av1")] ==
          ["avc", "av1"], str(bf.normalize_codec_order(["avc", "av1"])))

    print("3. 格式选择器")
    sel = bf.build_video_selector([100], [30280], ["avc"])
    check("指定档位出现在选择器里", "bestvideo[quality=100]" in sel, sel[:80])
    check("没有落到别的档位", "quality=80" not in sel, sel[:80])
    sel_best = bf.build_selector({"bili_quality_order": LEGACY_QUALITY}, False, "best")
    check("自动挡会带上补齐后的新档位", "bestvideo[quality=100]" in (sel_best or ""),
          (sel_best or "")[:120])
    check("新档位的优先级在 1080P 高清之后",
          (sel_best or "").index("quality=100]") > (sel_best or "").index("quality=80]"))
    audio = bf.build_audio_selector([30216, 30280])
    check("音质 format_id 带引号（否则永不匹配）", 'format_id="30216"' in audio, audio[:80])

    # build_selector 内部也要兜一层归一化：配置文件躺在磁盘上没被界面改过时，
    # 下载用的顺序必须和设置界面显示的一致。
    stale = {"bili_audio_order": LEGACY_AUDIO, "bili_codec_order": LEGACY_CODEC}
    sel_stale = bf.build_selector(dict(stale, bili_quality_order=[80]), False, "best") or ""
    check("自动挡·补齐后的音质（30251 Hi-Res）参与组合",
          'format_id="30251"' in sel_stale, sel_stale[:120])
    check("自动挡·补齐后的编码（av1）参与组合",
          "[vcodec^=av01]" in sel_stale, sel_stale[:120])
    stale_audio = bf.build_selector(dict(stale, bili_quality_order=[80]), True, "best") or ""
    check("自动挡·仅音频也走补齐后的音质顺序",
          'format_id="30251"' in stale_audio, stale_audio[:120])

    print("4. 画质名 → qn")
    check("全称能认出来", bf.quality_by_name("4K 超高清") == 120, str(bf.quality_by_name("4K 超高清")))
    check("简称能认出来（display_desc）", bf.quality_by_name("4K") == 120)
    check("带空格的写法也能认", bf.quality_by_name("1080P60") == 116)
    check("认不出来时返回 None", bf.quality_by_name("玄学画质") is None)

    print("5. yt-dlp 日志里的「视频有、账号拿不到」")
    from app.core.downloader import parse_missing_qualities
    check("解析出缺失档位",
          parse_missing_qualities([
              "Format(s) 4K 超高清, 1080P 高码率 are missing; you have to "
              "become a premium member to download them."]) == [120, 112],
          str(parse_missing_qualities([
              "Format(s) 4K 超高清, 1080P 高码率 are missing; you have to "
              "become a premium member to download them."])))
    check("简称也认", parse_missing_qualities(["Format(s) 4K, HDR are missing;"]) == [120, 125])
    check("无关日志不误判", parse_missing_qualities(["[bilibili] 标题: 测试", "已合并"]) == [])
    check("认不出的名字被忽略", parse_missing_qualities(["Format(s) 玄学画质 are missing;"]) == [])

    print("6. 老配置迁移")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "settings.json"
        path.write_text(json.dumps({
            "bili_quality_order": LEGACY_QUALITY,
            "bili_audio_order": LEGACY_AUDIO,
            "bili_codec_order": LEGACY_CODEC,
            # 老配置里数值被界面存成了浮点
            "max_concurrent": 3.0,
            "window_width": 1152.0,
        }, ensure_ascii=False), encoding="utf-8")
        # 显式把配置路径交给 Settings：早先靠改模块级 CONFIG_PATH、再在 finally 里改回去，
        # 一旦 save() 发生在改回去之后，就会写到用户真实的 settings.json 上。
        settings = cfgmod.Settings(path=path)
        order = settings.get("bili_quality_order")
        audio_order = settings.get("bili_audio_order")
        codec_order = settings.get("bili_codec_order")
        check("老配置里的画质顺序被补齐", order == [q for q, _n in EXPECTED], str(order))
        check("老配置里的音质顺序被补齐",
              audio_order == [a for a, _n, _v in EXPECTED_AUDIO], str(audio_order))
        check("老配置里的编码顺序被补齐（保留用户排好的 avc 在 hevc 之前）",
              codec_order == ["av1", "avc", "hevc"], str(codec_order))
        check("其它字段不受影响", isinstance(settings.get("output_dir"), str))
        check("浮点写法被收敛成 int",
              settings.get("max_concurrent") == 3
              and isinstance(settings.get("max_concurrent"), int)
              and isinstance(settings.get("window_width"), int),
              f"{settings.get('max_concurrent')!r} / {settings.get('window_width')!r}")
        # 迁移结果要能落盘：下次启动读到的就是补齐后的顺序
        settings.save()
        check("配置写到了指定路径", settings.configPath() == str(path),
              settings.configPath())
        written = json.loads(path.read_text(encoding="utf-8"))
        check("补齐后的顺序被写回配置文件",
              written.get("bili_audio_order") == [a for a, _n, _v in EXPECTED_AUDIO]
              and written.get("bili_codec_order") == ["av1", "avc", "hevc"],
              f"{written.get('bili_audio_order')} / {written.get('bili_codec_order')}")

    print("7. 界面回写的数值类型收敛")
    with tempfile.TemporaryDirectory() as tmp:
        clean = Path(tmp) / "settings.json"
        settings = cfgmod.Settings(path=clean)
        settings.set("max_concurrent", 4.0)
        check("整数型设置：4.0 → int 4",
              settings.get("max_concurrent") == 4
              and isinstance(settings.get("max_concurrent"), int),
              repr(settings.get("max_concurrent")))
        settings.set("font_scale", 1)
        check("浮点型设置：1 → float 1.0",
              isinstance(settings.get("font_scale"), float),
              repr(settings.get("font_scale")))
        before = settings.get("socket_timeout")
        settings.set("socket_timeout", float("nan"))
        check("NaN 不会被写进配置", settings.get("socket_timeout") == before,
              repr(settings.get("socket_timeout")))
        settings.set("animations", 1)
        check("布尔型设置不被误当数字", settings.get("animations") == 1,
              repr(settings.get("animations")))
        settings.save()
        written = json.loads(clean.read_text(encoding="utf-8"))
        check("整份配置都能安全序列化", "NaN" not in clean.read_text(encoding="utf-8"),
              str(written.get("socket_timeout")))

    print()
    if FAILS:
        print(f"失败 {len(FAILS)} 项：" + "、".join(FAILS))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
