"""yt-dlp 图形用户界面 —— 程序入口。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 允许以 python -m app.main 或直接运行本文件
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app import APP_NAME, APP_ID, APP_TAGLINE, __version__
    from app.core import ytdlp as ytdlp_mod
    from app.core.bridge import Bridge
    from app.core.helpers import resource_dir
    from app.core.winutil import (DWMSBT_MAINWINDOW, DWMSBT_NONE, apply_window_style)
else:
    from . import APP_NAME, APP_ID, APP_TAGLINE, __version__
    from .core import ytdlp as ytdlp_mod
    from .core.bridge import Bridge
    from .core.helpers import resource_dir
    from .core.winutil import (DWMSBT_MAINWINDOW, DWMSBT_NONE, apply_window_style)

from PySide6.QtCore import QObject, Qt, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QGuiApplication, QIcon,
                           QLinearGradient, QPainter, QPainterPath, QPen, QPixmap)
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

# QFileDialog 等部件类对话框必须运行在 QApplication 之下：只创建 QGuiApplication 时，
# 点击“浏览…”会让 Qt 因 “Cannot create a QWidget without QApplication” 直接崩溃。
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

# 打包后 QML / 资源位于 _MEIPASS 下，开发时跟随 app 包，统一交给 resource_dir 解析
QML_DIR = resource_dir("qml")
ASSETS_DIR = resource_dir("assets")

UI_FONTS = ["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI Variable Display",
            "Segoe UI", "Noto Sans SC", "PingFang SC", "Source Han Sans SC"]


def pick_font() -> str:
    families = set(QFontDatabase.families())
    for name in UI_FONTS:
        if name in families:
            return name
    return "Sans Serif"


def pick_icon_font() -> str:
    families = set(QFontDatabase.families())
    for name in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
        if name in families:
            return name
    return pick_font()


def make_icon() -> QIcon:
    """用代码画一个应用图标，避免额外的资源依赖。"""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        s = size / 256.0
        grad = QLinearGradient(0, 0, size, size)
        grad.setColorAt(0.0, QColor("#8B6CFF"))
        grad.setColorAt(0.55, QColor("#6D4BF6"))
        grad.setColorAt(1.0, QColor("#3E2AB8"))
        path = QPainterPath()
        path.addRoundedRect(0, 0, size, size, size * 0.235, size * 0.235)
        p.fillPath(path, grad)
        hl = QLinearGradient(0, 0, 0, size * 0.6)
        hl.setColorAt(0.0, QColor(255, 255, 255, 60))
        hl.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(path, hl)
        cx = size / 2.0
        pen = QPen(QColor(255, 255, 255, 240))
        pen.setWidthF(max(1.4, 22 * s))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        top = size * 0.24
        bottom = size * 0.60
        p.drawLine(int(cx), int(top), int(cx), int(bottom))
        p.drawLine(int(cx), int(bottom), int(cx - size * 0.15), int(bottom - size * 0.15))
        p.drawLine(int(cx), int(bottom), int(cx + size * 0.15), int(bottom - size * 0.15))
        pen2 = QPen(QColor(255, 255, 255, 210))
        pen2.setWidthF(max(1.2, 16 * s))
        pen2.setCapStyle(Qt.RoundCap)
        p.setPen(pen2)
        p.drawLine(int(size * 0.26), int(size * 0.76), int(size * 0.74), int(size * 0.76))
        p.end()
        icon.addPixmap(pm)
    return icon


class WindowHelper(QObject):
    """窗口外观相关的辅助接口。"""

    def __init__(self) -> None:
        super().__init__()
        self._window = None
        self._applied: dict = {}
        self.bridge = None

    def attach(self, window) -> None:
        self._window = window

    @Slot(result="QVariantMap")
    def applyChrome(self) -> dict:
        return self._apply()

    @Slot(bool, result="QVariantMap")
    def setDark(self, dark: bool) -> dict:
        return self._apply(dark=dark)

    @Slot(bool, bool, bool, result="QVariantMap")
    def configure(self, dark: bool, rounded: bool, mica: bool) -> dict:
        return self._apply(dark=dark, rounded=rounded, mica=mica)

    def _apply(self, dark=None, rounded=None, mica=None) -> dict:
        if self._window is None:
            return {}
        # 绝对导入：打包后入口脚本是以 __main__ 运行的顶层模块，相对导入会报
        # 「attempted relative import with no known parent package」（窗口外观会静默失效）
        from app.core import winutil
        if dark is None:
            dark = bool(getattr(self.bridge, "_dark", True))
        if rounded is None:
            rounded = True
        if mica is None:
            mica = False
        backdrop = DWMSBT_MAINWINDOW if mica else DWMSBT_NONE
        try:
            hwnd = int(self._window.winId())
        except Exception:
            return {}
        result = apply_window_style(hwnd, dark=dark, rounded=rounded, backdrop=backdrop)
        result["build"] = winutil._build()
        self._applied = result
        return result


class _YtdlpFetcher(QThread):
    """后台抓取 yt-dlp：首次启动要联网下载，放子线程里界面才不会假死。"""

    done = Signal(bool, str)

    def run(self) -> None:  # noqa: D102
        try:
            ok, reason = ytdlp_mod.ensure()
        except Exception as exc:  # noqa: BLE001
            ok, reason = False, f"获取下载引擎时出错：{exc}"
        self.done.emit(ok, reason)


def _bootstrap_log(message: str) -> None:
    """把首次启动的准备过程写进 logs/bootstrap.log。

    打包分发后没有控制台，用户报「打不开」时这份日志是唯一的线索，
    因此即使一切正常也留一行版本记录。
    """
    try:
        base = Path(os.environ.get("APPDATA") or Path.home()) / "YtDlpGui" / "logs"
        base.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        with open(base / "bootstrap.log", "a", encoding="utf-8") as fh:
            fh.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}\n")
    except Exception:
        pass


def bootstrap_ytdlp() -> bool:
    """确保 yt-dlp 下载引擎可用。

    打包分发时**不内置** yt-dlp（它更新频繁），而是沿用程序既有做法：
    从 PyPI 取官方 wheel 解压到 %APPDATA%\\YtDlpGui\\lib。
    已安装时这里零开销、不联网、不弹窗；缺失时给一个中文进度框，
    失败也不阻塞启动 —— 界面照常打开，设置页可稍后重试安装。
    """
    if ytdlp_mod.available():
        _bootstrap_log(f"引擎已就绪：{ytdlp_mod.installed_version()}（{ytdlp_mod.lib_dir()}）")
        return True

    _bootstrap_log("未找到引擎，开始自动获取…")
    dialog = QProgressDialog("正在获取下载引擎（yt-dlp）…", "", 0, 0)
    dialog.setWindowTitle("首次启动准备")
    dialog.setWindowModality(Qt.ApplicationModal)
    dialog.setCancelButton(None)
    dialog.setMinimumWidth(360)
    dialog.setAutoClose(False)
    dialog.show()
    QApplication.processEvents()

    result: dict = {}
    fetcher = _YtdlpFetcher()
    fetcher.done.connect(lambda ok, reason: result.update(ok=ok, reason=reason))
    fetcher.start()
    # 注意：done 是跨线程信号，投递到主线程要经过事件队列。工作线程可能在
    # isRunning() 变 False 的同一瞬间才 emit，此时队列里的事件还没被处理，
    # 直接读 result 会拿到空值（实测就是这么误报「获取失败」的）。
    # 所以收尾时先等线程结束，再显式把事件队列跑干净，最后才判结果。
    while fetcher.isRunning():
        QApplication.processEvents()
        fetcher.wait(40)
    fetcher.wait(3000)
    for _ in range(5):
        QApplication.processEvents()
    dialog.close()

    if result.get("ok") or ytdlp_mod.available():
        _bootstrap_log(f"获取成功：{ytdlp_mod.installed_version()}")
        return True

    reason = result.get("reason") or ytdlp_mod.ERR_OFFLINE
    # 把「文件都在但 import 不起来」这类真实原因带出来，否则只报一句「未就绪」没法排查
    detail = ytdlp_mod.last_import_error()
    _bootstrap_log(f"获取失败：{reason} | 导入错误：{detail or '无'}")
    box = QMessageBox()
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle("下载引擎未就绪")
    box.setText("未能自动获取 yt-dlp 下载引擎。")
    info = reason + "\n\n程序仍会启动，你可以稍后在「设置 → 组件」中重新安装。"
    if detail:
        info = f"导入引擎时报错：\n{detail}\n\n{info}"
    box.setInformativeText(info)
    retry = box.addButton("重试", QMessageBox.AcceptRole)
    box.addButton("稍后再说", QMessageBox.RejectRole)
    box.exec()
    if box.clickedButton() is retry:
        return bootstrap_ytdlp()
    return False


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME + " — " + APP_TAGLINE)
    app.setOrganizationName(APP_ID)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(make_icon())

    # 打包分发时不含 yt-dlp：首次启动先把它取回来（已装则直接通过，不联网）
    if os.environ.get("LIUGUANG_SKIP_YTDLP_BOOTSTRAP") != "1":
        bootstrap_ytdlp()

    font_family = pick_font()
    icon_family = pick_icon_font()
    base_font = QFont(font_family)
    base_font.setPointSizeF(10.0)
    app.setFont(base_font)

    QQuickStyle.setStyle("Basic")

    bridge = Bridge()
    bridge._dark = True
    bridge._font_family = font_family
    bridge._icon_family = icon_family

    helper = WindowHelper()
    helper.bridge = bridge

    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("backend", bridge)
    ctx.setContextProperty("windowHelper", helper)
    engine.addImportPath(str(QML_DIR))

    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        print("QML 加载失败", file=sys.stderr)
        return 1

    window = engine.rootObjects()[0]
    helper.attach(window)

    if os.environ.get("LIUGUANG_UI_DUMP"):
        def dump(item, depth=0, ox=0.0, oy=0.0, maxdepth=14):
            if depth > maxdepth:
                return
            for child in item.childItems():
                cx, cy = ox + child.x(), oy + child.y()
                name = child.metaObject().className()
                label = ""
                for prop in ("text", "placeholderText"):
                    try:
                        val = child.property(prop)
                    except Exception:
                        continue
                    if isinstance(val, str) and val.strip():
                        label += f" {prop}={val.strip()[:34]!r}"
                        break
                wanted = os.environ.get("LIUGUANG_UI_DUMP_FILTER", "")
                keep = True
                if wanted:
                    keep = any(tok and tok in name for tok in wanted.split(","))
                if child.isVisible() and keep and (label or wanted or name in (
                        "QQuickRectangle", "QQuickTextField", "QQuickFlickable",
                        "QQuickLoader", "QQuickItem", "QQuickWindowQmlImpl")):
                    print(f"{'  ' * depth}{name} @({cx:.0f},{cy:.0f}) "
                          f"{child.width():.0f}x{child.height():.0f}{label}")
                dump(child, depth + 1, cx, cy, maxdepth)

        def run_dump():
            print("=" * 30, "UI DUMP", "=" * 30)
            dump(window.contentItem())
            print("=" * 70)
            sys.stdout.flush()

        QTimer.singleShot(int(os.environ.get("LIUGUANG_UI_DUMP_DELAY", "2500")), run_dump)

    def boot() -> None:
        try:
            helper.configure(bool(bridge.settings.get("theme") != "light"),
                             bool(bridge.settings.get("rounded_window")),
                             bool(bridge.settings.get("mica")))
        except Exception:
            pass
        if os.environ.get("LIUGUANG_DEMO"):
            try:
                bridge.seedDemo()
            except Exception as exc:  # noqa: BLE001
                print("demo seed failed:", exc, file=sys.stderr)
        demo_url = os.environ.get("LIUGUANG_DEMO_URL")
        if demo_url:
            QTimer.singleShot(400, lambda: bridge.analyze(demo_url))

    QTimer.singleShot(80, boot)
    return app.exec()


def _crash_log_path() -> Path:
    """崩溃日志位置：优先写进程序数据目录，失败就退回临时目录。"""
    try:
        base = Path(os.environ.get("APPDATA") or Path.home()) / "YtDlpGui" / "logs"
        base.mkdir(parents=True, exist_ok=True)
        return base / "startup-crash.log"
    except Exception:
        import tempfile
        return Path(tempfile.gettempdir()) / "YtDlpGui-startup-crash.log"


def _report_crash(exc: BaseException) -> None:
    """把启动阶段的异常落盘并弹窗。

    打包成 GUI 程序后没有控制台，异常只会静默消失（用户看到的是「双击没反应」），
    所以这里必须写日志 + 弹窗，并把日志路径告诉用户。
    """
    import traceback

    text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    log = _crash_log_path()
    try:
        log.write_text(
            f"{APP_NAME} {__version__}\nPython {sys.version}\n"
            f"frozen={getattr(sys, 'frozen', False)} exe={sys.executable}\n\n{text}",
            encoding="utf-8")
    except Exception:
        pass

    detail = f"{type(exc).__name__}: {exc}"
    print(text, file=sys.stderr)
    try:
        # 延迟导入：启动失败有可能正是 Qt 起不来，那时弹窗也弹不出来，日志仍然有效
        from PySide6.QtWidgets import QMessageBox as _Box
        box = _Box()
        box.setIcon(_Box.Critical)
        box.setWindowTitle("程序启动失败")
        box.setText(f"{APP_NAME} 启动时出错，无法继续。")
        box.setInformativeText(f"{detail}\n\n详细信息已写入：\n{log}")
        box.exec()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - 兜底：GUI 程序没有控制台可看
        _report_crash(exc)
        sys.exit(1)
