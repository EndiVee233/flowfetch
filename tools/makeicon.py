"""生成打包用的 app.ico（真正的多尺寸图标）。

程序图标是 `app/main.py` 里用 QPainter 画出来的（避免额外资源依赖），
打包时 PyInstaller / Inno Setup 需要一个真正的 .ico 文件，所以这里把同样的
绘制结果导出到 `app/assets/app.ico`。

注意：Qt 的 ICO 写入器只会存一张位图（任务栏/资源管理器的小尺寸会糊），
所以这里自己拼 ICO 容器：ICONDIR + 每个尺寸一条 ICONDIRENTRY + PNG 数据
（Vista 起 ICO 支持内嵌 PNG，Windows 10/11 完全支持）。

用法（offscreen 即可，不需要真窗口）：
    C:\\Python314\\python.exe tools\\makeicon.py
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from app.main import make_icon  # noqa: E402

# Windows 会按这些尺寸挑最合适的一张；256 是最大档
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
OUT = ROOT / "app" / "assets" / "app.ico"


def png_bytes(icon, size: int) -> bytes:
    """把某个尺寸渲染成 PNG 字节。

    用 QByteArray + QBuffer 直接编码；QBuffer 必须显式释放 ——
    它的析构写在 C++ 侧，交给 Python 垃圾回收容易在解释器退出阶段踩空指针。
    """
    pm = icon.pixmap(size, size)
    if pm.isNull():
        raise RuntimeError(f"{size}x{size} 渲染失败")
    store = QByteArray()
    buf = QBuffer(store)
    buf.open(QIODevice.WriteOnly)
    if not pm.save(buf, "PNG"):
        buf.close()
        raise RuntimeError(f"{size}x{size} 编码 PNG 失败")
    buf.close()
    data = bytes(store)
    del buf
    return data


def build_ico(images: list[tuple[int, bytes]]) -> bytes:
    """按 ICO 容器格式拼装。"""
    header = struct.pack("<HHH", 0, 1, len(images))          # reserved, type=icon, count
    offset = len(header) + 16 * len(images)
    entries, blobs = [], []
    for size, data in images:
        dim = 0 if size >= 256 else size                      # 256 在目录里写 0
        entries.append(struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32,
                                   len(data), offset))
        blobs.append(data)
        offset += len(data)
    return header + b"".join(entries) + b"".join(blobs)


def main() -> int:
    QGuiApplication(sys.argv)
    icon = make_icon()
    images = [(size, png_bytes(icon, size)) for size in SIZES]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(build_ico(images))

    with open(OUT, "rb") as fh:
        head = fh.read(6)
    count = int.from_bytes(head[4:6], "little")
    print(f"已生成 {OUT}")
    print(f"  尺寸: {', '.join(str(s) for s in SIZES)}")
    print(f"  内含 {count} 张位图，共 {OUT.stat().st_size} 字节")
    ok = count == len(SIZES) and OUT.stat().st_size > 5000
    if not ok:
        print("校验未通过")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
