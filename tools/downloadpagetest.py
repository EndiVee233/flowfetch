"""DownloadPage「默认 / 自定义」胶囊的离线回归测试。

起因（用户反馈）：媒体卡上的「默认」胶囊点不掉 —— 它 `selected: useDefaults`、
`onClicked: useDefaults = true`，而右边三项又是 `enabled: !useDefaults`，
于是默认态一旦生效就把用户锁死了：既取消不了勾选，也点不动其它项。

本测试真加载 `app/qml/DownloadPage.qml`（宿主见 tools/downloadpagetest.qml），
用假 backend 驱动真实点击，断言：
1. 「默认」是个可切换的开关（勾选 → 取消 → 再勾选）；
2. 取消后右边三项仍然可用（不再被置灰锁死）；
3. 点右边任意一项会自动切到自定义；
4. 勾选「默认」时打包给下载队列的 spec 依旧走「跟随设置」那条路径。
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Property, QObject, Qt, QUrl, Slot  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core import bili_format as bf  # noqa: E402
from app.core import yt_format as yf  # noqa: E402
from app.core.config import default_settings  # noqa: E402
from app.core.downloader import sanitize_result  # noqa: E402

FAILS = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(("  [ok]   " if cond else "  [FAIL] ") + name + ("" if cond else f"  ->  {extra}"))
    if not cond:
        FAILS.append(name)


class FakeSettings(QObject):
    """只提供 DownloadPage / Theme 会读的那几个键。"""

    def __init__(self) -> None:
        super().__init__()
        self._data = default_settings()

    @Slot(str, "QVariant", result="QVariant")
    def get(self, key, default=None):
        return self._data.get(key, default)

    @Slot(result="QVariantMap")
    def all(self):
        return dict(self._data)

    @Slot(str, result="QVariant")
    def value(self, key):
        return self._data.get(key)


class FakeBilibili(QObject):
    @Property(bool, constant=True)
    def loggedIn(self) -> bool:
        return False

    @Property(str, constant=True)
    def statusText(self) -> str:
        return "未登录"


class FakeWebLogin(QObject):
    @Slot(str, result="QVariantMap")
    def siteStatus(self, site):
        return {"loggedIn": False, "label": "未登录", "site": site}


class FakeBackend(QObject):
    """记录界面回传的 spec，其余属性给足 DownloadPage 需要的上下文。"""

    def __init__(self) -> None:
        super().__init__()
        self._settings = FakeSettings()
        self._bilibili = FakeBilibili()
        self._weblogin = FakeWebLogin()
        self.last_spec = None
        self.last_batch = []
        self.toasts = []

    # —— 界面读的属性 ——
    @Property(QObject, constant=True)
    def settings(self):
        return self._settings

    @Property(QObject, constant=True)
    def bilibili(self):
        return self._bilibili

    @Property(QObject, constant=True)
    def weblogin(self):
        return self._weblogin

    @Property(str, constant=True)
    def fontFamily(self):
        return "Microsoft YaHei UI"

    @Property(str, constant=True)
    def iconFamily(self):
        return "Segoe Fluent Icons"

    @Property(bool, constant=True)
    def demoMode(self):
        return False

    @Property(bool, constant=True)
    def demoOpenFormat(self):
        return False

    @Property(bool, constant=True)
    def demoOpenBiliQuality(self):
        return False

    @Property(bool, constant=True)
    def demoOpenSubtitles(self):
        return False

    @Property(bool, constant=True)
    def demoExpandSections(self):
        return False

    @Property(bool, constant=True)
    def analyzing(self):
        return False

    @Property(str, constant=True)
    def defaultDir(self):
        return str(ROOT / "tools" / "_out")

    @Slot(result="QVariantMap")
    def allSettings(self):
        return dict(self._settings.all())

    # —— 档位表 ——
    @Slot(result="QVariantList")
    def biliQualityTable(self):
        return bf.quality_table()

    @Slot(result="QVariantList")
    def biliAudioTable(self):
        return bf.audio_table()

    @Slot(result="QVariantList")
    def biliCodecTable(self):
        return bf.codec_table()

    @Slot(result="QVariantList")
    def ytQualityTable(self):
        return yf.quality_table()

    @Slot(result="QVariantList")
    def ytAudioTable(self):
        return yf.audio_table()

    @Slot(result="QVariantList")
    def ytCodecTable(self):
        return yf.codec_table()

    @Slot(result="QVariantList")
    def qualityPresets(self):
        return [{"key": "best", "label": "最佳画质", "desc": ""}]

    # —— 界面会调用的动作 ——
    @Slot("QVariantMap", result=str)
    def startDownload(self, spec):
        self.last_spec = dict(spec)
        return "task-1"

    @Slot("QVariantList", result=int)
    def startBatch(self, specs):
        self.last_batch = [dict(s) for s in specs]
        return len(self.last_batch)

    @Slot(str, str, str)
    def notify(self, level, title, message):
        self.toasts.append((level, title, message))

    @Slot(str)
    def analyze(self, text):
        pass

    @Slot(str, result="QVariantList")
    def extractUrls(self, text):
        return []

    @Slot(str)
    def copyText(self, text):
        pass

    @Slot(str)
    def openFolder(self, path):
        pass


def pump(app, rounds: int = 12) -> None:
    for _ in range(rounds):
        app.processEvents()
        time.sleep(0.01)


def sample_media() -> dict:
    info = {
        "id": "test", "title": "测试视频", "uploader": "测试频道",
        "webpage_url": "https://www.youtube.com/watch?v=test", "duration": 60,
        "extractor_key": "Youtube",
        "formats": [
            {"format_id": "401", "url": "https://example.invalid/v", "width": 3840,
             "height": 2160, "fps": 60, "vcodec": "av01.0.12M.08", "acodec": "none",
             "ext": "mp4", "tbr": 8000, "protocol": "https"},
            {"format_id": "251", "url": "https://example.invalid/a", "vcodec": "none",
             "acodec": "opus", "abr": 128, "tbr": 128, "ext": "webm",
             "protocol": "https", "filesize": 9730000},
        ],
        "subtitles": {"en": [{"ext": "vtt", "url": "https://example.invalid/s.vtt"}]},
    }
    return sanitize_result(info, info["webpage_url"])


def main() -> int:
    app = QApplication(sys.argv)
    QQuickStyle.setStyle("Basic")

    backend = FakeBackend()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.addImportPath(str(ROOT / "app" / "qml"))
    engine.load(QUrl.fromLocalFile(str(ROOT / "tools" / "downloadpagetest.qml")))
    if not engine.rootObjects():
        print("QML 加载失败")
        return 1
    win = engine.rootObjects()[0]
    win.setProperty("cfg", backend.allSettings())
    page = win.findChild(QObject, "page")
    if page is None:
        print("找不到 DownloadPage")
        return 1
    chip = win.findChild(QObject, "defaultsChip")
    if chip is None:
        print("找不到「默认」胶囊（需要先有 media 才会渲染）")
        return 1
    pump(app)

    page.setProperty("media", sample_media())
    pump(app)

    def use_defaults() -> bool:
        return bool(page.property("useDefaults"))

    def chip_selected() -> bool:
        return bool(chip.property("selected"))

    def chip_enabled() -> bool:
        return bool(chip.property("enabled"))

    print("1. 初始态：默认勾选")
    check("useDefaults = true", use_defaults())
    check("胶囊显示为已选中", chip_selected())
    check("胶囊可点击（enabled）", chip_enabled())

    print("2. 点一次：应当取消勾选（用户反馈的 bug）")
    chip.metaObject().invokeMethod(chip, "clicked")
    pump(app, 4)
    check("useDefaults = false", not use_defaults(), use_defaults())
    check("胶囊显示为未选中", not chip_selected(), chip_selected())
    check("仍然可点击（能再勾回去）", chip_enabled())

    print("3. 再点一次：应当勾选回来")
    chip.metaObject().invokeMethod(chip, "clicked")
    pump(app, 4)
    check("useDefaults = true", use_defaults())
    check("胶囊显示为已选中", chip_selected())

    print("4. 取消后可以直接改自定义项（不再被置灰锁死）")
    chip.metaObject().invokeMethod(chip, "clicked")
    pump(app, 4)
    page.setProperty("coverMode", "original")
    page.setProperty("subLangs", ["zh-Hans"])
    pump(app, 4)
    check("封面改为原图后 useDefaults 仍为自定义",
          not use_defaults() and page.property("coverMode") == "original",
          f"{use_defaults()} / {page.property('coverMode')}")
    check("字幕记录生效", list(page.property("subLangs")) == ["zh-Hans"],
          str(page.property("subLangs")))

    print("5. 勾选「默认」时，spec 走「跟随设置」")
    chip.metaObject().invokeMethod(chip, "clicked")
    pump(app, 4)
    page.metaObject().invokeMethod(page, "startOne")
    pump(app, 6)
    spec = backend.last_spec
    check("已提交下载 spec", spec is not None, str(spec))
    if spec:
        check("preset = best", spec.get("preset") == "best", str(spec.get("preset")))
        check("formatLabel = 默认（跟随设置）",
              spec.get("formatLabel") == "默认（跟随设置）", str(spec.get("formatLabel")))
        check("封面/字幕交回设置（空串）",
              spec.get("coverMode") == "" and spec.get("subLangs") == ""
              and spec.get("subFormat") == "",
              f"{spec.get('coverMode')!r} / {spec.get('subLangs')!r}")
        check("outputDir 来自设置",
              spec.get("outputDir") == backend.allSettings().get("output_dir"),
              str(spec.get("outputDir")))

    print("6. 自定义态下，spec 带上本次选择")
    backend.last_spec = None
    chip.metaObject().invokeMethod(chip, "clicked")   # 切回自定义
    pump(app, 4)
    page.setProperty("coverMode", "640")
    page.setProperty("subLangs", ["en", "zh-Hans"])
    pump(app, 4)
    page.metaObject().invokeMethod(page, "startOne")
    pump(app, 6)
    spec2 = backend.last_spec
    check("已提交自定义 spec", spec2 is not None, str(spec2))
    if spec2:
        check("封面 mode = 640", spec2.get("coverMode") == "640", str(spec2.get("coverMode")))
        check("字幕 = en,zh-Hans", spec2.get("subLangs") == "en,zh-Hans",
              str(spec2.get("subLangs")))

    print()
    if FAILS:
        print(f"失败 {len(FAILS)} 项：" + "、".join(FAILS))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
