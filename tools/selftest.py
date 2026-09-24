"""端到端自检：解析 -> 下载 -> 校验产物。

用法：
    C:\\Python314\\python.exe tools\\selftest.py

环境变量：`TEST_URL` 换测试链接；`LIUGUANG_HISTORY=1` 让自检写进真实历史记录
（默认只写 `tools/_history.json`，免得自检产物混进用户的历史列表）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from app.core.bridge import Bridge  # noqa: E402

URL = os.environ.get("TEST_URL", "https://www.youtube.com/watch?v=BaW_jenozKc")
OUT = ROOT / "tools" / "_out"
# 自检的下载记录不该混进用户真实的「历史记录」里（以前会），默认写到 _out 旁边的临时文件；
# 需要看界面效果时用 LIUGUANG_HISTORY=1 让自检故意写进真实历史。
HISTORY = (Path(os.environ["LIUGUANG_HISTORY"])
           if os.environ.get("LIUGUANG_HISTORY", "") not in ("", "0", "1")
           else (None if os.environ.get("LIUGUANG_HISTORY") == "1"
                 else ROOT / "tools" / "_history.json"))

app = QGuiApplication(sys.argv)
bridge = Bridge()
if HISTORY is not None:
    bridge.history.redirect(HISTORY)
bridge.settings.set("output_dir", str(OUT))
bridge.settings.set("max_concurrent", 2)
bridge.settings.set("embed_metadata", True)
bridge.settings.set("embed_thumbnail", False)
OUT.mkdir(parents=True, exist_ok=True)

state = {"phase": "analyze", "task": None, "code": 1}


def on_media(data):
    print("[解析成功]", data["type"], "|", data.get("title"), "|",
          data.get("durationText"), "| 格式数:", data.get("formatCount"),
          "| 播放列表项:", data.get("entryCount", 0))
    if data["type"] == "playlist":
        print("[播放列表前 3 项]", [e["title"][:24] for e in data["entries"][:3]])
        state["code"] = 0
        app.quit()
        return
    state["phase"] = "download"
    state["task"] = bridge.startDownload({
        "url": data["webpage_url"],
        "title": data["title"],
        "uploader": data.get("uploader", ""),
        "duration": data.get("duration", 0),
        "preset": "worst",
        "formatLabel": "最小体积（自检）",
    })
    print("[开始下载] 任务", state["task"])


def on_failed(msg):
    print("[失败]", msg)
    state["code"] = 1
    app.quit()


def on_done(task_id, title, status):
    if task_id != state["task"]:
        return
    task = bridge.tasks.get(task_id)
    print("[下载结束]", status, "|", title)
    if task is not None:
        print("  文件:", task.filepath)
        print("  大小:", task.size_text(), "| 格式:", task.format_label)
        if task.error:
            print("  错误:", task.error)
    files = list(OUT.glob("*"))
    print("  产物:", [(f.name, f.stat().st_size) for f in files])
    state["code"] = 0 if status == "completed" and files else 1
    QTimer.singleShot(200, app.quit)


bridge.mediaReady.connect(on_media)
bridge.mediaFailed.connect(on_failed)
bridge.taskDone.connect(on_done)

QTimer.singleShot(300, lambda: bridge.analyze(URL))
QTimer.singleShot(150000, lambda: (print("[超时]"), app.quit()))

app.exec()
print("[退出码]", state["code"])
sys.exit(state["code"])
