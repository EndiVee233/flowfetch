"""组件管理自检：检查更新 + 下载 FFmpeg。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.deps import DependencyManager  # noqa: E402

app = QGuiApplication(sys.argv)
settings = Settings()
deps = DependencyManager(settings)

print("组件目录:", deps.binDir)
print("FFmpeg 就绪:", deps.ffmpegReady, "|", deps.ffmpegStatusText)
print("系统 PATH 中的 FFmpeg（不会自动使用）:", deps.systemFfmpeg or "无")

deps.progress.connect(lambda k, p, m: print(f"  [{k}] {p}% {m}"))

state = {"code": 1}
ACTION = sys.argv[1] if len(sys.argv) > 1 else "download"


def on_finished(kind, ok, message):
    if kind == "check":
        print("检查更新完成：")
        print("  yt-dlp 已安装", deps.ytdlpVersion, "最新", deps.ytdlpLatest or "未知",
              "需要更新:", deps.ytdlpOutdated)
        print("  FFmpeg 需要更新:", deps.ffmpegOutdated)
        if ACTION == "check":
            state["code"] = 0
            app.quit()
        else:
            print("开始下载 FFmpeg…")
            deps.installFfmpeg()
        return
    print(f"[{kind}] 成功={ok} {message}")
    print("FFmpeg 就绪:", deps.ffmpegReady, "|", deps.ffmpegStatusText)
    print("路径:", deps.ffmpegPath)
    state["code"] = 0 if ok else 1
    app.quit()


deps.finished.connect(on_finished)
QTimer.singleShot(200, lambda: deps.checkUpdates(True))
QTimer.singleShot(600000, app.quit)
app.exec()
print("退出码", state["code"])
sys.exit(state["code"])
