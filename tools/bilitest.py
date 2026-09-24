"""检查哔哩哔哩解析出的实际可用画质。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from app.core.bilibili import COOKIE_FILE  # noqa: E402
from app.core.bridge import Bridge  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.bilibili.com/video/BV1G88G6KEhn/"
app = QGuiApplication(sys.argv)
bridge = Bridge()
print("哔哩哔哩登录状态:", bridge.bilibili.statusText, "| Cookies 文件存在:", COOKIE_FILE.exists())


def on_media(data):
    print("标题:", data.get("title"))
    print("站点:", data.get("extractor"), "| isBilibili:", data.get("isBilibili"))
    print("可用高度:", data.get("heights"))
    print("最高:", data.get("maxHeight"), "P |", data.get("maxFps"), "fps")
    print("格式数:", data.get("formatCount"))
    print("--- 前 12 个视频格式 ---")
    shown = 0
    for f in data.get("formats", []):
        if not f["hasVideo"] or not f["height"]:
            continue
        print(f"  id={f['formatId']:<8} {f['height']}P {int(f['fps'] or 0):>3}fps "
              f"{f['vcodec'][:12]:<12} {f['extractor'] if 'extractor' in f else ''} "
              f"{f['filesizeText']}")
        shown += 1
        if shown >= 12:
            break
    app.quit()


def on_fail(msg):
    print("解析失败:", msg)
    app.quit()


bridge.mediaReady.connect(on_media)
bridge.mediaFailed.connect(on_fail)
QTimer.singleShot(200, lambda: bridge.analyze(URL))
QTimer.singleShot(120000, app.quit)
app.exec()
