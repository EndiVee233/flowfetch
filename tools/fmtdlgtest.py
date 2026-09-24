"""格式弹窗的「档位 → 编码」两级选择逻辑的离线测试。

用真实的 sanitize_result 产出格式表，再驱动 FormatDialog 的 QML 函数，
验证换档位时编码栏确实会刷新、切换编码时结果确实会变。
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import (Q_ARG, Property, QMetaObject, QObject, Qt, QUrl,  # noqa: E402
                              Slot)
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core import yt_format as yf  # noqa: E402
from app.core.downloader import sanitize_result  # noqa: E402

FAILS = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(("  [ok]   " if cond else "  [FAIL] ") + name + ("" if cond else f"  ->  {extra}"))
    if not cond:
        FAILS.append(name)


class FakeBackend(QObject):
    """格式弹窗只用到这两张表（用来排编码顺序）"""

    def __init__(self) -> None:
        super().__init__()
        # Theme 单例要读字体名，没有 settings 会刷一堆 QML 警告
        self._settings = FakeSettings()
        self._settings.setParent(self)

    @Property(QObject, constant=True)
    def settings(self):
        return self._settings

    @Property(str, constant=True)
    def fontFamily(self):
        return "Microsoft YaHei UI"

    @Property(str, constant=True)
    def iconFamily(self):
        return "Segoe Fluent Icons"

    @Slot(result="QVariantList")
    def ytCodecTable(self):
        return yf.codec_table()

    @Slot(result="QVariantList")
    def ytAudioTable(self):
        return yf.audio_table()


class FakeSettings(QObject):
    @Slot(str, "QVariant", result="QVariant")
    def get(self, key, default=None):
        return default


def vf(fid, w, h, fps, vcodec, tbr):
    return {"format_id": fid, "url": "https://example.invalid/v", "width": w, "height": h,
            "fps": fps, "vcodec": vcodec, "acodec": "none", "ext": "mp4",
            "tbr": tbr, "protocol": "https", "filesize": int(tbr * 1000)}


def af(fid, acodec, abr, ext, size):
    return {"format_id": fid, "url": "https://example.invalid/a", "vcodec": "none",
            "acodec": acodec, "abr": abr, "tbr": abr, "ext": ext,
            "protocol": "https", "filesize": size}


RAW = [
    vf("401", 3840, 2160, 60, "av01.0.12M.08", 8000),
    vf("315", 3840, 2160, 60, "vp09.00.51.08", 17000),
    vf("400", 2560, 1440, 60, "av01.0.12M.08", 4000),
    vf("308", 2560, 1440, 60, "vp09.00.50.08", 6000),
    vf("399", 1920, 1080, 30, "av01.0.08M.08", 1800),
    vf("248", 1920, 1080, 30, "vp09.00.41.08", 2500),
    vf("137", 1920, 1080, 30, "avc1.640028", 2600),
    af("251", "opus", 128, "webm", 9730000),
    af("140", "mp4a.40.2", 129, "m4a", 9800000),
    af("250", "opus", 65, "webm", 4950000),
    af("139", "mp4a.40.2", 48, "m4a", 3690000),
]


def main() -> int:
    app = QApplication(sys.argv)
    QQuickStyle.setStyle("Basic")

    info = {"id": "test", "title": "测试视频", "webpage_url": "https://www.youtube.com/watch?v=test",
            "duration": 60, "extractor_key": "Youtube", "formats": RAW}
    media = sanitize_result(info, info["webpage_url"])
    formats = media["formats"]
    check("sanitize_result 给出了编码键与编码名",
          all(("codecKey" in f and "codec" in f) for f in formats),
          str(formats[0]))

    backend = FakeBackend()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(ROOT / "tools" / "fmtdlgtest.qml")))
    if not engine.rootObjects():
        print("QML 加载失败")
        return 1
    win = engine.rootObjects()[0]
    dialog = win.findChild(QObject, "dialog")
    if dialog is None:
        print("找不到 FormatDialog")
        return 1

    check("backend 上下文可用", bool(win.property("backendOk")))
    dialog.setProperty("formats", formats)
    QMetaObject.invokeMethod(dialog, "open", Qt.DirectConnection)
    # opened 信号要等弹出动画开始后才发出来，多转几圈事件循环
    for _ in range(15):
        app.processEvents()
        time.sleep(0.02)

    def read(prop):
        """QML 里的 JS 数组/对象会以 QJSValue 返回，先转成 Python 值。"""
        value = dialog.property(prop)
        if hasattr(value, "toVariant"):
            value = value.toVariant()
        return value

    def groups(prop):
        return [dict(g) for g in (read(prop) or [])]

    def picked(prop):
        value = read(prop)
        return dict(value) if value else None

    print("1. 档位分组")
    vg = groups("videoGroupRows")
    ag = groups("audioGroupRows")
    check("视频按分辨率+帧率去重后只剩 3 档", len(vg) == 3, str([g["label"] for g in vg]))
    check("档位从高到低排列",
          [g["label"] for g in vg] == ["3840x2160 · 60FPS", "2560x1440 · 60FPS", "1920x1080 · 30FPS"],
          str([g["label"] for g in vg]))
    check("音频按码率档归并（129K 的 AAC 与 128K 的 Opus 同档）", len(ag) == 3,
          str([g["label"] for g in ag]))
    check("同一档位里列出两种音频编码",
          sorted(g["label"] for g in groups("audioCodecRows")) == ["AAC", "Opus"],
          str([g["label"] for g in groups("audioCodecRows")]))
    check("档位行带上了编码数量与体积", "种编码" in vg[0]["sub"] and "起" in vg[0]["sub"],
          vg[0]["sub"])
    check("单个档位下只列该档位可用的编码",
          sorted(g["label"] for g in groups("videoCodecRows")) == ["AV1", "VP9"],
          str([g["label"] for g in groups("videoCodecRows")]))

    print("2. 打开时的默认选择")
    check("默认选最高档", dialog.property("videoKey") == "3840x2160@60",
          str(dialog.property("videoKey")))
    check("默认编码按设置里的编码优先级排（AV1 第一）",
          dialog.property("videoCodec") == "av01", str(dialog.property("videoCodec")))
    check("音频默认选最高码率档", dialog.property("audioKey") == "128",
          str(dialog.property("audioKey")))
    check("音频默认编码是 Opus（音质表里排在 AAC 前）",
          dialog.property("audioCodec") == "opus", str(dialog.property("audioCodec")))

    print("3. 换档位 → 编码栏刷新")
    QMetaObject.invokeMethod(dialog, "pickVideoGroup", Qt.DirectConnection,
                             Q_ARG("QVariant", "2560x1440@60"))
    app.processEvents()
    vc = groups("videoCodecRows")
    check("1440P 档只列出该档位可用的编码",
          sorted(g["label"] for g in vc) == ["AV1", "VP9"], str([g["label"] for g in vc]))
    check("换档后自动选中 AV1", dialog.property("videoCodec") == "av01",
          str(dialog.property("videoCodec")))
    check("选中的格式跟着换成 1440P 的 AV1", (picked("pickedVideo") or {}).get("formatId") == "400",
          str((picked("pickedVideo") or {}).get("formatId")))

    print("4. 换编码 → 下载目标跟着变")
    dialog.setProperty("videoCodec", "vp9")
    app.processEvents()
    check("选中 1440P 的 VP9", (picked("pickedVideo") or {}).get("formatId") == "308",
          str((picked("pickedVideo") or {}).get("formatId")))
    check("组合 ID 同步更新", dialog.property("resultId") == "308+251",
          str(dialog.property("resultId")))
    check("说明文字带上编码", "VP9" in str(dialog.property("resultLabel")),
          str(dialog.property("resultLabel")))

    print("5. 1080P 档的三种编码")
    QMetaObject.invokeMethod(dialog, "pickVideoGroup", Qt.DirectConnection,
                             Q_ARG("QVariant", "1920x1080@30"))
    app.processEvents()
    vc = groups("videoCodecRows")
    check("1080P 档列出 AV1 / VP9 / H.264",
          sorted(g["label"] for g in vc) == ["AV1", "H.264", "VP9"], str([g["label"] for g in vc]))

    print("6. 「不使用」与音频联动")
    QMetaObject.invokeMethod(dialog, "pickVideoGroup", Qt.DirectConnection,
                             Q_ARG("QVariant", ""))
    app.processEvents()
    check("视频清空后没有选中格式", picked("pickedVideo") is None)
    check("编码栏随之清空", groups("videoCodecRows") == [])
    check("结果只剩音频", str(dialog.property("resultId")).startswith("251"),
          str(dialog.property("resultId")))

    QMetaObject.invokeMethod(dialog, "pickAudioGroup", Qt.DirectConnection,
                             Q_ARG("QVariant", "64"))
    app.processEvents()
    check("换成低码率档后编码栏刷新",
          [g["label"] for g in groups("audioCodecRows")] == ["Opus"],
          str([g["label"] for g in groups("audioCodecRows")]))
    check("选中 65K 的 Opus", (picked("pickedAudio") or {}).get("formatId") == "250",
          str((picked("pickedAudio") or {}).get("formatId")))

    print()
    if FAILS:
        print(f"失败 {len(FAILS)} 项：" + "、".join(FAILS))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
