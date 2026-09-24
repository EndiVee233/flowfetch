"""离线加载 Main.qml 并捕获真实 QML 警告/错误。

与之前失败的测试不同：本脚本会按 main.py 的方式设置 backend / windowHelper
两个上下文属性，并安装 qInstallMessageHandler 收集 warning，从而区分
“真正的 QML 错误”与“缺少上下文对象的伪警告”。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QCoreApplication, QMessageLogContext, QUrl, QtMsgType, qInstallMessageHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from app.core.bridge import Bridge
from app.main import WindowHelper  # noqa: E402

WARNINGS = []
ERRORS = []


def _handler(msg_type, context, message):
    text = f"{message}"
    if msg_type in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
        if msg_type == QtMsgType.QtWarningMsg:
            WARNINGS.append(text)
        else:
            ERRORS.append(f"[{msg_type.name}] {text}")


def main() -> int:
    qInstallMessageHandler(_handler)
    app = QApplication(sys.argv)
    QQuickStyle.setStyle("Basic")

    bridge = Bridge()
    bridge._dark = True
    helper = WindowHelper()
    helper.bridge = bridge

    qml_dir = ROOT / "app" / "qml"
    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("backend", bridge)
    ctx.setContextProperty("windowHelper", helper)
    engine.addImportPath(str(qml_dir))

    engine.load(QUrl.fromLocalFile(str(qml_dir / "Main.qml")))

    if not engine.rootObjects():
        print("QML 加载失败：没有 rootObjects")
        print(f"warnings: {len(WARNINGS)}  errors: {len(ERRORS)}")
        for w in WARNINGS[:60]:
            print("  WARN:", w)
        for e in ERRORS:
            print("  ERR :", e)
        return 1

    # 给一下事件循环时间，触发 Component.onCompleted / 绑定求值
    app.processEvents()
    QCoreApplication.sendPostedEvents()

    # 额外验证：注入演示数据并切到历史页，强制 ListView 创建 delegate，
    # 真正触发 HistoryPage 中 `required property string kind` 的绑定求值。
    win = engine.rootObjects()[0]
    try:
        bridge.seedDemo()
    except Exception as exc:  # noqa: BLE001
        print("seedDemo 失败:", exc, file=sys.stderr)
    try:
        win.setProperty("page", 2)
    except Exception:
        pass
    for _ in range(6):
        app.processEvents()
        QCoreApplication.sendPostedEvents()

    print(f"rootObjects: {len(engine.rootObjects())}")
    print(f"warnings: {len(WARNINGS)}")
    print(f"errors: {len(ERRORS)}")
    # 只打印前 40 条 warning，避免刷屏
    for w in WARNINGS[:40]:
        print("  WARN:", w)
    for e in ERRORS:
        print("  ERR :", e)

    # 关注点：kind 字段相关、AlsoFile 删除按钮、FormatDialog 引用
    interesting = [w for w in WARNINGS if any(k in w for k in ("kind", "KindRole", "alsoFile", "pendingFile", "FormatDialog", "Type", "undefined"))]
    print(f"\n关键相关警告: {len(interesting)}")
    for w in interesting:
        print("  KEY:", w)

    return 0 if not ERRORS else 1


if __name__ == "__main__":
    sys.exit(main())
