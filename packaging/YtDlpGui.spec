# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（one-folder）。

设计取舍：
- **不内置 yt-dlp**：它更新频繁，内置等于把版本冻结在打包那一刻。
  程序本来就会把官方 wheel 解压到 %APPDATA%\\YtDlpGui\\lib，
  打包版沿用这条路径（见 app/core/ytdlp.py 的自举逻辑），因此这里显式 exclude。
- **不内置 FFmpeg**：同上，交给「设置 → 组件」下载或让用户指定已有目录。
- one-folder 而非 one-file：省去每次启动解压几百 MB，QtWebEngine 也更稳。
- 保留 QtWebEngine（YouTube 程序内登录用），顺便带上 websockets / qrcode。

体积控制：PySide6 的 hook 会把整个 Qt 塞进来，其中大量东西本程序用不到
（DevTools 资源、调试用 .debug.pak、被排除模块对应的 Qt6*.dll、别的 QML 样式）。
下面的 `_drop()` 过滤把它们摘掉 —— 实测能省约 100 MB。

构建：
    C:\\Python314\\python.exe -m PyInstaller --noconfirm --clean \\
        --distpath packaging\\dist --workpath packaging\\build packaging\\YtDlpGui.spec
产物：
    packaging\\dist\\YtDlpGui\\YtDlpGui.exe
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parent          # noqa: F821 - SPECPATH 由 PyInstaller 注入
APP_DIR = ROOT / "app"

# —— 要剔除的文件（按 *nix 形式的小写相对路径匹配）——
# 1) QtWebEngine 的调试资源：DevTools 面板与 .debug.pak，生产环境完全用不到
#    （qtwebengine_devtools_resources.debug.pak 一个就 72 MB）
#    注意：100p/200p 与 v8_context_snapshot 是**运行时必需**的，不能删
# 2) 被 excludes 排除掉的模块对应的 Qt DLL / QML 插件
# 3) QQuickStyle 只用 "Basic"（main.py 里显式设置），其余控件样式用不到
_DROP_EXACT = {
    "pyside6/resources/qtwebengine_devtools_resources.debug.pak",
    "pyside6/resources/qtwebengine_devtools_resources.pak",
    "pyside6/resources/qtwebengine_resources.debug.pak",
    "pyside6/resources/qtwebengine_resources_100p.debug.pak",
    "pyside6/resources/qtwebengine_resources_200p.debug.pak",
    "pyside6/resources/v8_context_snapshot.debug.bin",
}
_DROP_DIRS = (
    "pyside6/qml/qtwebengine/",         # DevTools 的 QML 前端
    "pyside6/qml/qtquick3d/",
    "pyside6/qml/qt3d/",
    "pyside6/qml/qtgraphs/",
    "pyside6/qml/qtcharts/",
    "pyside6/qml/qtdatavisualization/",
    "pyside6/qml/qtquick/controls/fluentwinui3/",
    "pyside6/qml/qtquick/controls/imagine/",
    "pyside6/qml/qtquick/controls/universal/",
    "pyside6/qml/qtquick/controls/material/",
    "pyside6/qml/qtquick/controls/designer/",
)
_DROP_DLL_PREFIXES = (
    "qt6pdf", "qt6quick3d", "qt6multimedia", "qt6charts", "qt6datavisualization",
    "qt6sql", "qt6test", "qt6designer", "qt6help", "qt6uitools", "qt6scxml",
    "qt6remoteobjects", "qt6texttospeech", "qt6spatialaudio", "qt6serialport",
    "qt6bluetooth", "qt6nfc", "qt6positioning", "qt6sensors", "qt6httpserver",
    "qt6quick3dutils", "qt6quick3dassetimport", "qt6quick3dparticles",
    "qt6spatialaudio", "qt6websockets",
)


def _norm(name: str) -> str:
    return name.replace("\\", "/").lower()


def _drop(name: str) -> bool:
    path = _norm(name)
    if path in _DROP_EXACT:
        return True
    if any(path.startswith(prefix) for prefix in _DROP_DIRS):
        return True
    base = path.rsplit("/", 1)[-1]
    if base.startswith(_DROP_DLL_PREFIXES) and base.endswith((".dll", ".pyd")):
        return True
    if base.startswith("qml") and base.endswith((".dll", ".pyd")) and any(
            tag in base for tag in ("quick3d", "qt3d", "charts", "datavisualization")):
        return True
    return False


# QML 与图标：打包后位于 _MEIPASS 下，helpers.resource_dir() 会优先在那里找
datas = [(str(APP_DIR / "qml"), "qml")]
if (APP_DIR / "assets").is_dir():
    datas.append((str(APP_DIR / "assets"), "assets"))

# Qt 自带的资源（plugins / translations / qml 模块）由 PyInstaller 的 PySide6 hook 负责，
# 这里只补那些「函数内部延迟导入」的模块 —— 静态分析看不到它们。
hiddenimports = [
    # 程序内登录窗口（weblogin.py 里在构造时才 import）
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebChannel",
    "PySide6.QtNetwork",
    "PySide6.QtPrintSupport",
    # 访客 Cookie（guestcookie.py 里延迟导入）
    "websockets",
    # B 站扫码登录兜底安装的二维码库（bilibili.py）
    "qrcode",
]
hiddenimports += collect_submodules("websockets")
hiddenimports += collect_submodules("qrcode")

# 关键（踩过的坑）：yt-dlp 不打包，于是 PyInstaller 只按**我们自己的**代码
# 收集依赖 —— 而 yt-dlp 运行时会用到一批我们从不 import 的标准库/可选库
# （首次实测就卡在 ModuleNotFoundError: No module named 'getpass'）。
# 这里把它们显式列进来；不存在的会被 PyInstaller 忽略（仅提示），不会失败。
hiddenimports += [
    # —— yt-dlp 用到的标准库 ——
    "getpass", "netrc", "sqlite3", "ssl", "ctypes", "ctypes.util", "zlib",
    "bz2", "lzma", "mimetypes", "email", "email.message", "html", "html.parser",
    "xml", "xml.etree.ElementTree", "urllib", "urllib.request", "urllib.parse",
    "http", "http.cookiejar", "http.client", "http.server", "wsgiref",
    "concurrent", "concurrent.futures", "multiprocessing", "socket",
    "subprocess", "tempfile", "secrets", "unicodedata", "base64", "binascii",
    "hashlib", "hmac", "json", "locale", "logging", "platform", "shutil",
    "struct", "textwrap", "tokenize", "uuid", "warnings", "optparse",
    "fileinput", "quopri", "bisect", "heapq", "glob", "inspect", "pkgutil",
    "sysconfig", "asyncio", "contextvars", "dataclasses", "traceback",
    # —— yt-dlp 的可选第三方依赖（本机已装，装上就能少一次运行期失败）——
    "brotli", "certifi", "mutagen", "requests", "urllib3",
    "Cryptodome", "websockets",
]

# 注意（踩过的坑）：excludes 里排掉一个模块，PyInstaller 就不再收集它对应的
# Qt6Xxx.dll，而别的**保留**组件可能仍依赖那个 DLL —— 于是启动时报
# 「libshiboken: could not import module 'PySide6.QtQuick'」这种看不出因果的错。
# 例如 QtSql：QML 引擎的 LocalStorage 插件依赖 Qt6Sql.dll，因此不能排。
# 下面的清单是逐个用 dumpbin 核对过依赖闭合后才保留的。
excludes = [
    "yt_dlp",                    # 由程序运行时自行获取（见文件头说明）
    "tkinter", "unittest", "pydoc", "doctest", "test",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtQuick3D", "PySide6.QtQuick3DUtils",
    "PySide6.QtSerialPort", "PySide6.QtTest",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning",
    "PySide6.QtSensors", "PySide6.QtSensorsQuick", "PySide6.QtWebSockets",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtSpatialAudio",
    "PySide6.QtTextToSpeech", "PySide6.QtHttpServer", "PySide6.QtPdf",
    "PySide6.QtPdfWidgets", "PySide6.QtDesigner", "PySide6.QtHelp",
    "PySide6.QtUiTools",
]

a = Analysis(  # noqa: F821
    [str(APP_DIR / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / "packaging" / "rthook_startup.py")],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

# —— 剔除死重 ——
_before = len(a.binaries) + len(a.datas)
a.binaries = TOC(entry for entry in a.binaries if not _drop(entry[0]))  # noqa: F821
a.datas = TOC(entry for entry in a.datas if not _drop(entry[0]))        # noqa: F821
print(f"[spec] 剔除 {_before - len(a.binaries) - len(a.datas)} 项未使用的 Qt 资源")

# 自检：QML 与图标必须真的进来了，否则打出来的包一启动就白屏
_names = {_norm(entry[0]) for entry in a.datas}
for required in ("qml/main.qml", "qml/theme.qml", "assets/app.ico"):
    if required not in _names:
        raise SystemExit(f"[spec] 打包内容缺少 {required}，请检查 datas 配置")
print("[spec] QML 与图标已就位")

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="YtDlpGui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,              # UPX 压 Qt 的 DLL 容易出问题，宁可大一点
    console=False,          # GUI 程序，不弹控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(APP_DIR / "assets" / "app.ico") if (APP_DIR / "assets" / "app.ico").is_file() else None,
    version=str(ROOT / "packaging" / "version_info.txt"),
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="YtDlpGui",
)
