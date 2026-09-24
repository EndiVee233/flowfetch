"""暂停 / 继续 功能的离线回归测试。

用一个假的 YoutubeDL 顶替真实下载器：它按 0.1s 的节奏调用进度回调，
于是无需联网就能复现「下载 → 暂停 → 继续 → 取消」的完整状态机。
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import app.core.downloader as dl  # noqa: E402
from app.core import taskmodel as TM  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.taskmodel import Task, TaskModel  # noqa: E402

TOTAL = 20_000_000
STEP = 1_000_000

# 下载步数：默认 20 步 × 0.1s = 2 秒；测「暂停撞上下载完成」时会调小
FAST_STEPS = 20

FAILS = []


class FakeYDL:
    """模拟一份需要 2 秒才能下完的媒体。"""

    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def prepare_filename(self, info):
        return ""

    def extract_info(self, url, download=True):
        hooks = self.opts.get("progress_hooks") or []
        hook = hooks[0] if hooks else None
        for i in range(1, FAST_STEPS + 1):
            time.sleep(0.1)
            if hook:
                hook({
                    "status": "downloading",
                    "downloaded_bytes": i * STEP,
                    "total_bytes": TOTAL,
                    "speed": float(STEP),
                    "eta": 20 - i,
                    "info_dict": {"title": "测试视频", "id": "fake"},
                })
        if hook:
            hook({"status": "finished", "filename": "", "info_dict": {}})
        return {"title": "测试视频", "id": "fake"}


def check(name: str, cond: bool, extra: str = "") -> None:
    print(("  [ok]   " if cond else "  [FAIL] ") + name + ("" if cond else f"  ->  {extra}"))
    if not cond:
        FAILS.append(name)


def spin(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main() -> int:
    app = QApplication(sys.argv)  # noqa: F841
    dl.yt_dlp.YoutubeDL = FakeYDL  # 注入假下载器

    settings = Settings()
    model = TaskModel()
    engine = dl.DownloadEngine(settings, model)

    task = engine.new_task("https://example.com/video")
    engine.enqueue(task)

    print("1. 正常下载")
    spin(700)
    check("状态 = 下载中", task.status == TM.DOWNLOADING, task.status)
    check("进度 > 0", task.progress > 0, str(task.progress))
    got = task.downloaded
    check("已记录已下载字节", got > 0, str(got))

    print("2. 暂停")
    engine.pause(task.id)
    check("状态 = 已暂停", task.status == TM.PAUSED, task.status)
    check("文案 = 已暂停", task.detail == "已暂停", task.detail)

    # 暂停瞬间，取消前发出的进度信号可能还在事件队列里，必须被丢弃
    engine._on_progress(task.id, {"status": TM.DOWNLOADING,
                                  "downloaded": 9_000_000, "total": TOTAL})
    check("旧进度信号不会把状态改回下载中", task.status == TM.PAUSED, task.status)

    spin(700)
    check("线程退出后保持已暂停（不被当成已取消）", task.status == TM.PAUSED, task.status)
    check("断点进度保留", task.downloaded >= got, f"{task.downloaded} < {got}")

    print("3. 继续")
    engine.resume(task.id)
    spin(600)
    check("重新开始下载", task.status in (TM.ANALYZING, TM.DOWNLOADING), task.status)
    spin(400)
    check("继续后进度重新增长",
          task.status == TM.DOWNLOADING and task.progress > 0,
          f"{task.status} {task.progress}")

    print("4. 暂停中直接取消")
    engine.pause(task.id)
    spin(500)
    check("暂停生效", task.status == TM.PAUSED, task.status)
    engine.cancel(task.id)
    check("状态 = 已取消", task.status == TM.CANCELED, task.status)

    print("5. 排队中的任务")
    queued = Task(id="q1", url="https://example.com/q", status=TM.QUEUED, title="排队任务")
    model.add(queued)
    engine.pause("q1")
    check("排队任务可暂停", queued.status == TM.PAUSED, queued.status)
    check("暂停的排队任务不会被调度",
          all(t.id != "q1" for t in model.queued()))
    engine.resume("q1")
    check("继续后重新进入队列",
          queued.status in (TM.QUEUED, TM.ANALYZING, TM.DOWNLOADING), queued.status)
    spin(400)

    engine.cancelAll()
    spin(500)

    print("6. 暂停后立刻继续（旧线程还没退出）")
    race = engine.new_task("https://example.com/race")
    engine.enqueue(race)
    spin(500)
    check("下载进行中", race.status == TM.DOWNLOADING, race.status)
    engine.pause(race.id)
    engine.resume(race.id)
    check("立刻继续后回到队列", race.status == TM.QUEUED, race.status)
    spin(1600)
    # 立刻继续时下载线程往往还没来得及响应暂停，于是会顺势下完；
    # 无论哪种结果都行，唯独不能卡在「排队中 / 已暂停」。
    check("不会卡死在排队中（继续下载或直接完成）",
          race.status in (TM.ANALYZING, TM.DOWNLOADING, TM.COMPLETED), race.status)
    engine.cancelAll()
    spin(300)

    print("7. 暂停撞上下载完成（迟到的完成事件必须丢掉）")
    late = engine.new_task("https://example.com/late")
    model.add(late)
    late.status = TM.DOWNLOADING
    late.downloaded = 8_000_000
    late.total = TOTAL
    late.progress = 0.4
    # 真实场景：下载线程走完、发出 finished，紧接着用户点了暂停，于是这条完成事件
    # 排在暂停之后才被主线程处理（真实下载里后处理很慢，这个窗口很常见）。
    # 注意：同线程 emit 是直连、会当场执行，必须用 singleShot 才真正排进事件队列。
    QTimer.singleShot(0, lambda: engine.signals.finished.emit(
        late.id, {"path": "", "info": {"title": "测试视频"}}))
    engine.pause(late.id)
    check("点暂停后立刻是已暂停", late.status == TM.PAUSED, late.status)
    spin(200)                    # 处理队列里那个迟到的完成事件
    check("迟到的完成事件不会把状态改成已完成", late.status == TM.PAUSED, late.status)
    check("文案仍然是已暂停", late.detail == "已暂停", late.detail)
    check("断点进度没有被清零", late.downloaded == 8_000_000, str(late.downloaded))
    engine.resume(late.id)
    spin(300)
    check("继续之后仍能重新跑起来",
          late.status in (TM.ANALYZING, TM.DOWNLOADING, TM.COMPLETED), late.status)
    engine.cancelAll()
    spin(400)

    print("8. 历史记录的路径隔离（自检不许写进用户历史）")
    import json
    import tempfile

    from app.core.history import HistoryModel, HISTORY_PATH

    real = HISTORY_PATH
    real_stat = real.stat() if real.exists() else None
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "history.json"
        hist = HistoryModel(path=target)
        check("构造时就用指定路径（不碰真实文件）", hist._path == target, str(hist._path))
        hist.add({"url": "https://example.com/a", "title": "第一条", "filepath": str(ROOT / "tools" / "_out" / "x.mkv"), "format_label": "自检"})
        hist.add({"url": "https://example.com/b", "title": "第二条", "filepath": "C:/Users/x/Downloads/y.mkv", "format_label": "最高品质（自动）"})
        check("记录写进了临时文件", target.exists() and hist.count == 2, str(hist.count))
        now_stat = real.stat() if real.exists() else None
        check("真实历史文件分毫未动",
              (real_stat is None and now_stat is None)
              or (real_stat is not None and now_stat is not None
                  and real_stat.st_mtime == now_stat.st_mtime
                  and real_stat.st_size == now_stat.st_size),
              f"{real_stat} -> {now_stat}")
        removed = hist.removeMatching("_out")
        check("按关键字清理自检记录", removed == 1 and hist.count == 1, f"{removed} / {hist.count}")
        check("清理结果已落盘",
              len(json.loads(target.read_text(encoding="utf-8"))) == 1,
              target.read_text(encoding="utf-8")[:60])
        # redirect 是给开发工具用的：换文件并重新载入
        other = Path(tmp) / "other.json"
        other.write_text(json.dumps([{"title": "另一份"}]), encoding="utf-8")
        hist.redirect(other)
        check("redirect 能换文件并重新载入",
              hist.count == 1 and hist.allItems()[0]["title"] == "另一份",
              str(hist.allItems()))

    print()
    if FAILS:
        print(f"失败 {len(FAILS)} 项：" + "、".join(FAILS))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
