"""把 PNG 转成 ASCII 艺术图，便于在纯文本环境中校验界面。"""
from __future__ import annotations

import argparse
import sys

from PySide6.QtGui import QImage

RAMP = " .:-=+*#%@"


def load(path: str) -> QImage:
    img = QImage(path)
    if img.isNull():
        raise SystemExit(f"无法读取图片: {path}")
    return img.convertToFormat(QImage.Format.Format_RGBA8888)


def ascii_art(img: QImage, cols: int = 120, crop=None, mode: str = "density",
              threshold: int = 90, invert: bool = False, stretch: bool = False) -> str:
    if crop:
        x, y, w, h = crop
        img = img.copy(x, y, w, h)
    W, H = img.width(), img.height()
    if W <= 0 or H <= 0:
        return ""
    cols = max(8, min(cols, W))
    cell_w = W / cols
    cell_h = cell_w * 2.0
    rows = max(1, int(round(H / cell_h)))
    cell_h = H / rows

    # 采样所有单元格的原始亮度
    grid = []
    for r in range(rows):
        y0 = int(r * cell_h)
        y1 = max(y0 + 1, int((r + 1) * cell_h))
        ys = list(range(y0, min(y1, H), max(1, (y1 - y0) // 4)))
        row_vals = []
        for c in range(cols):
            x0 = int(c * cell_w)
            x1 = max(x0 + 1, int((c + 1) * cell_w))
            xs = list(range(x0, min(x1, W), max(1, (x1 - x0) // 4)))
            ink = 0
            tot = 0
            lum_sum = 0
            for y in ys:
                for x in xs:
                    px = img.pixelColor(x, y)
                    lum = (px.red() * 299 + px.green() * 587 + px.blue() * 114) // 1000
                    tot += 1
                    lum_sum += lum
                    if lum >= threshold:
                        ink += 1
            row_vals.append((ink / max(1, tot), lum_sum / max(1, tot) / 255.0))
        grid.append(row_vals)

    lo, hi = 0.0, 1.0
    if stretch and grid:
        vals = [v[0] if mode == "density" else v[1] for row in grid for v in row]
        lo, hi = min(vals), max(vals)
        if hi - lo < 1e-6:
            hi = lo + 1e-6

    out = []
    for row_vals in grid:
        line = []
        for density, luma in row_vals:
            v = density ** 0.55 if mode == "density" else luma
            if stretch:
                v = (v - lo) / (hi - lo)
            if invert:
                v = 1.0 - v
            line.append(RAMP[int(max(0.0, min(1.0, v)) * (len(RAMP) - 1) + 0.5)])
        out.append("".join(line))
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--cols", type=int, default=120)
    ap.add_argument("--crop", type=str, default="")
    ap.add_argument("--threshold", type=int, default=90)
    ap.add_argument("--mode", default="density", choices=["density", "luma"])
    ap.add_argument("--invert", action="store_true")
    ap.add_argument("--stretch", action="store_true")
    args = ap.parse_args()
    crop = tuple(int(v) for v in args.crop.split(",")) if args.crop else None
    img = load(args.path)
    print(f"[{img.width()}x{img.height()}]")
    print(ascii_art(img, args.cols, crop, args.mode, args.threshold,
                    args.invert, args.stretch))
    return 0


if __name__ == "__main__":
    sys.exit(main())
