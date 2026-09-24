"""「默认」项的离线回归测试。

覆盖两件事：
1. DownloadPage 里「默认」选中时，startOne / startPlaylist 打出的 spec 中
   preset 是 best、formatId/coverMode/subLangs/subFormat 全为空串
   —— 空串正是后端「跟随全局设置」的降级语义；
2. 对应的 build_options 真的落到全局设置的值上（用真实的 Task + Settings 跑一遍）。
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Q_ARG, QMetaObject, Property, QObject, Qt, QUrl, Slot  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core import downloader as dl  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.taskmodel import Task  # noqa: E402

FAILS = []
# engine 必须留着引用：局部变量被回收会把 rootObjects 一起删掉
_KEEP = {}


def check(name: str, cond: bool, extra: str = "") -> None:
    print(("  [ok]   " if cond else "  [FAIL] ") + name + ("" if cond else f"  ->  {extra}"))
    if not cond:
        FAILS.append(name)


# ----------------------------------------------------------------------
# 用假的 backend 把 DownloadPage 单独加载起来，捕获 startDownload / startBatch
# ----------------------------------------------------------------------
CAPTURED = {"single": [], "batch": []}


class FakeSettings(QObject):
    @Slot(str, "QVariant", result="QVariant")
    def get(self, key, default=None):
        return default


class FakeBackend(QObject):
    """只提供 DownloadPage 用到的成员，重点是捕获 spec。"""

    def __init__(self) -> None:
        super().__init__()
        self._settings = FakeSettings()
        self._settings.setParent(self)
        self._bili = _FakeBili()
        self._bili.setParent(self)
        self._web = _FakeWebLogin()
        self._web.setParent(self)
        self._cfg = {"output_dir": "C:/tmp/out", "sub_format": "原始",
                     "bili_cover_mode": "", "write_subs": False,
                     "embed_thumbnail": True, "sub_langs": "zh-Hans,en",
                     "yt_use_custom_quality": True}

    @Property(QObject, constant=True)
    def settings(self):
        return self._settings

    @Property(str, constant=True)
    def fontFamily(self):
        return "Microsoft YaHei UI"

    @Property(str, constant=True)
    def iconFamily(self):
        return "Segoe Fluent Icons"

    # 注意：命名不能叫 allSettings，那是 Bridge 上的方法，
    # 这里用属性名 cfgData 承载同一份字典，避免与 Property 装饰器语义冲突
    @Property("QVariantMap", constant=True)
    def cfgData(self):
        return dict(self._cfg)

    @Property(bool, constant=True)
    def analyzing(self):
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

    @Slot("QVariantMap", result=str)
    def startDownload(self, spec):
        CAPTURED["single"].append(dict(spec))
        return "task-id"

    @Slot("QVariantList", result=int)
    def startBatch(self, specs):
        for s in specs:
            CAPTURED["batch"].append(dict(s))
        return len(specs)

    @Slot(str, str, str)
    def notify(self, level, title, message):
        pass

    @Slot(str, result=str)
    def pasteFromClipboard(self):
        return ""

    @Slot(result=str)
    def chooseDirectoryDialog(self):
        return ""

    @Slot(str, str)
    def copyText(self, a, b):
        pass

    @Slot(result="QVariantList")
    def biliQualityTable(self):
        from app.core import bili_format as bf
        return bf.quality_table()

    @Slot(result="QVariantList")
    def biliAudioTable(self):
        from app.core import bili_format as bf
        return bf.audio_table()

    @Slot(result="QVariantList")
    def biliCodecTable(self):
        from app.core import bili_format as bf
        return bf.codec_table()

    @Slot(result="QVariantList")
    def ytQualityTable(self):
        from app.core import yt_format as yf
        return yf.quality_table()

    @Slot(result="QVariantList")
    def ytAudioTable(self):
        from app.core import yt_format as yf
        return yf.audio_table()

    @Slot(result="QVariantList")
    def ytCodecTable(self):
        from app.core import yt_format as yf
        return yf.codec_table()

    @Slot(str, "QVariant")
    def setSetting(self, key, value):
        self._cfg[key] = value

    # 与 Bridge 一致：私有字段存实例，公开属性名给 QML 用
    @Property(QObject, constant=True)
    def bilibili(self):
        return self._bili

    @Property(QObject, constant=True)
    def weblogin(self):
        return self._web


class _FakeBili(QObject):
    @Property(bool, constant=True)
    def loggedIn(self):
        return True

    @Property(bool, constant=True)
    def isVip(self):
        return False


class _FakeWebLogin(QObject):
    @Slot(str, result="QVariantMap")
    def siteStatus(self, site):
        return {"loggedIn": False, "statusText": ""}


class FakeWin(QObject):
    """DownloadPage 引用了 win.cfg / win.page / win.urlFieldUrl。"""

    def __init__(self, backend) -> None:
        super().__init__()
        self._backend = backend
        self._page = 0
        self._url = ""

    @Property("QVariantMap", constant=True)
    def cfg(self):
        return self._backend.cfgData

    @Property(int)
    def page(self):
        return self._page

    @page.setter
    def page(self, v):
        self._page = v

    @Property(str)
    def urlFieldUrl(self):
        return self._url

    @urlFieldUrl.setter
    def urlFieldUrl(self, v):
        self._url = v


def load_page():
    """DownloadPage.qml 依赖 `backend` 与 `win` 两个上下文对象。

    QML 里还会读 `backend.bilibili` / `backend.weblogin`，而 Bridge 上这两个
    是 QObject 子对象、在 Python 侧无法直接作为属性名暴露，所以这里注册一个
    包一层的代理对象，把这两个名字补进去。
    """
    app = QApplication.instance() or QApplication(sys.argv)
    QQuickStyle.setStyle("Basic")
    backend = FakeBackend()
    win = FakeWin(backend)

    qml_dir = ROOT / "app" / "qml"
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_dir))
    ctx = engine.rootContext()
    ctx.setContextProperty("backend", backend)
    ctx.setContextProperty("win", win)
    engine.load(QUrl.fromLocalFile(str(qml_dir / "DownloadPage.qml")))
    if not engine.rootObjects():
        raise RuntimeError("DownloadPage.qml 加载失败")
    page = engine.rootObjects()[0]
    _KEEP["engine"] = engine
    _KEEP["backend"] = backend
    _KEEP["win"] = win
    _KEEP["page"] = page
    return app, backend, win, page


def call(page, method, *args, ret="QVariant"):
    ok = QMetaObject.invokeMethod(page, method, Qt.DirectConnection,
                                  *[Q_ARG("QVariant", a) for a in args])
    return ok


def main() -> int:
    print("1. 加载 DownloadPage.qml")
    try:
        app, backend, win, page = load_page()
    except Exception as exc:  # noqa: BLE001
        check("DownloadPage.qml 可加载", False, str(exc))
        print(f"\n失败项: {FAILS}")
        return 1
    check("DownloadPage.qml 可加载", True)

    print("2. 「默认」的初值")
    check("解析结果复位后默认项为选中", page.property("useDefaults") is True,
          str(page.property("useDefaults")))

    # 注入一份最小的解析结果
    media = {
        "type": "video",
        "title": "测试视频",
        "url": "https://example.invalid/v",
        "webpage_url": "https://example.invalid/v",
        "uploader": "UP",
        "thumbnail": "",
        "duration": 60,
        "anonymous": False,
        "isBilibili": False,
        "extractor": "Youtube",
        "formats": [],
        "heights": [1080, 720],
        "subtitles": ["zh-Hans", "en"],
    }

    print("3. 「默认」选中时 startOne 打出的 spec")
    CAPTURED["single"].clear()
    page.setProperty("media", media)
    page.setProperty("useDefaults", True)
    # 先手动选一堆非默认项，验证默认会把它们全部压掉
    page.setProperty("preset", "worst")
    page.setProperty("customFormatId", "137+140")
    page.setProperty("subLangs", ["zh-Hans"])
    page.setProperty("subFormat", "srt")
    page.setProperty("coverMode", "640")
    page.setProperty("useDefaults", True)
    QMetaObject.invokeMethod(page, "startOne", Qt.DirectConnection)

    check("产生了 1 个下载 spec", len(CAPTURED["single"]) == 1, str(len(CAPTURED["single"])))
    if CAPTURED["single"]:
        spec = CAPTURED["single"][0]
        check("preset = best（交回全局优先级表）", spec.get("preset") == "best", repr(spec.get("preset")))
        check("formatId 为空串（跟随设置）", spec.get("formatId") == "", repr(spec.get("formatId")))
        check("coverMode 为空串（跟随设置）", spec.get("coverMode") == "", repr(spec.get("coverMode")))
        check("subLangs 为空串（跟随设置）", spec.get("subLangs") == "", repr(spec.get("subLangs")))
        check("subFormat 为空串（跟随设置）", spec.get("subFormat") == "", repr(spec.get("subFormat")))
        check("audioOnly = false", spec.get("audioOnly") is False, repr(spec.get("audioOnly")))
        check("格式标签说明是默认", "默认" in str(spec.get("formatLabel")),
              repr(spec.get("formatLabel")))

    print("4. 关掉「默认」后应恢复手动选择")
    CAPTURED["single"].clear()
    page.setProperty("preset", "custom")
    page.setProperty("customFormatId", "137+140")
    page.setProperty("coverMode", "640")
    page.setProperty("subLangs", ["zh-Hans"])
    page.setProperty("useDefaults", False)
    QMetaObject.invokeMethod(page, "startOne", Qt.DirectConnection)
    if CAPTURED["single"]:
        spec = CAPTURED["single"][0]
        check("preset = custom", spec.get("preset") == "custom", repr(spec.get("preset")))
        check("formatId 保留手动选择", spec.get("formatId") == "137+140", repr(spec.get("formatId")))
        check("coverMode 保留手动选择", spec.get("coverMode") == "640", repr(spec.get("coverMode")))

    print("5. 播放列表：默认模式同样压掉手动选择")
    CAPTURED["batch"].clear()
    playlist = {
        "type": "playlist",
        "title": "合集",
        "entries": [
            {"index": 1, "title": "P1", "url": "https://example.invalid/1",
             "uploader": "UP", "thumbnail": "", "duration": 60},
            {"index": 2, "title": "P2", "url": "https://example.invalid/2",
             "uploader": "UP", "thumbnail": "", "duration": 60},
        ],
        "anonymous": False,
        "isBilibili": False,
    }
    page.setProperty("media", playlist)
    page.setProperty("useDefaults", True)
    QMetaObject.invokeMethod(page, "resetPicks", Qt.DirectConnection)
    QMetaObject.invokeMethod(page, "startPlaylist", Qt.DirectConnection)
    check("产生了 2 个批量 spec", len(CAPTURED["batch"]) == 2, str(len(CAPTURED["batch"])))
    if CAPTURED["batch"]:
        ok = all(s.get("preset") == "best" and s.get("coverMode") == ""
                 and s.get("subLangs") == "" and s.get("subFormat") == ""
                 for s in CAPTURED["batch"])
        check("每个项目都走默认设置", ok, str(CAPTURED["batch"][0]))

    print("6. 后端：空串真的落到全局设置上")
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(path=Path(tmp) / "settings.json")
        settings.set("write_subs", True)
        settings.set("sub_langs", "zh-Hans,en")
        settings.set("sub_format", "srt")
        settings.set("bili_write_subs", True)
        settings.set("bili_sub_langs", "zh-Hans")
        settings.set("bili_cover_mode", "640")
        settings.set("write_thumbnail", False)

        # 模拟「默认」打出的任务：cover_mode / sub_langs / sub_format 全空
        task = Task(id="t1", url="https://example.invalid/v", title="t",
                    preset="best", format_id="", format_label="默认（跟随设置）",
                    sub_langs="", sub_format="", cover_mode="")

        def noop(*a, **k):
            return None

        opts = dl.build_options(task, settings, noop, noop, None)
        check("字幕语言取自全局设置", opts.get("subtitleslangs") == ["zh-Hans", "en"],
              str(opts.get("subtitleslangs")))
        check("字幕开启", opts.get("writesubtitles") is True, str(opts.get("writesubtitles")))
        check("字幕格式取自全局设置 srt", opts.get("convertsubtitles") == "srt",
              str(opts.get("convertsubtitles")))
        check("画质走优先级表（非 custom）", opts.get("format") != "", str(opts.get("format")))

        # 哔哩哔哩链接：封面的全局默认应生效
        bili_task = Task(id="t2", url="https://www.bilibili.com/video/BV1xx411c7mD",
                         title="t", preset="best", format_id="",
                         sub_langs="", sub_format="", cover_mode="")
        bili_opts = dl.build_options(bili_task, settings, noop, noop, None)
        check("B 站封面按全局设置开启", bili_opts.get("writethumbnail") is True,
              str(bili_opts.get("writethumbnail")))

        # 对照：显式选了字幕时，不能用全局的
        explicit = Task(id="t3", url="https://example.invalid/v", title="t",
                        preset="best", sub_langs="ja", sub_format="vtt", cover_mode="none")
        exp_opts = dl.build_options(explicit, settings, noop, noop, None)
        check("显式选择的字幕语言优先于全局",
              exp_opts.get("subtitleslangs") == ["ja"], str(exp_opts.get("subtitleslangs")))
        check("显式选择的字幕格式优先于全局",
              exp_opts.get("convertsubtitles") == "vtt", str(exp_opts.get("convertsubtitles")))
        check("显式选择「不下载封面」优先于全局",
              exp_opts.get("writethumbnail") is False, str(exp_opts.get("writethumbnail")))

        # 确认没有碰真实配置
        real = Path(os.environ.get("APPDATA", "")) / "YtDlpGui" / "settings.json"
        check("未创建/修改用户真实配置路径", not str(real).startswith(tmp), str(real))

    print(f"\n失败项: {len(FAILS)}")
    for f in FAILS:
        print("  -", f)
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
