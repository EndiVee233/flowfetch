"""把多张 PNG 横向或纵向拼接成一张，便于一次性评审。"""
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter

app = QGuiApplication(sys.argv)
args = sys.argv[1:]
out = args[0]
paths = args[1:]
imgs = [QImage(p) for p in paths]
scale = 1.0
if len(imgs) > 1:
    scale = 0.62
w = int(max(i.width() for i in imgs) * scale)
h = int(sum(i.height() for i in imgs) * scale) + 22 * len(imgs)
canvas = QImage(w, h, QImage.Format.Format_RGB32)
canvas.fill(QColor("#202020"))
p = QPainter(canvas)
p.setRenderHint(QPainter.SmoothPixmapTransform, True)
font = QFont("Consolas", 11)
p.setFont(font)
y = 0
for path, img in zip(paths, imgs):
    p.setPen(QColor("#7CFC9A"))
    p.drawText(8, y + 16, path.split(chr(92))[-1])
    y += 22
    tw, th = int(img.width() * scale), int(img.height() * scale)
    p.drawImage(0, y, img.scaled(tw, th, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    y += th
p.end()
canvas.save(out)
print("saved", out, canvas.width(), "x", canvas.height())
