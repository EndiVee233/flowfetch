"""一键打包：生成图标 → PyInstaller 出 one-folder 发行版 → Inno Setup 出安装包。

用法（在项目根目录执行）：
    C:\\Python314\\python.exe packaging\\build.py

产物：
    packaging\\dist\\YtDlpGui\\            可直接运行的发行目录（绿色版）
    packaging\\output\\YtDlpGui-1.0.0-setup.exe   安装包

依赖：
    - PyInstaller（已随开发环境安装）
    - Inno Setup 7（默认装在 C:\\Program Files\\Inno Setup 7\\ISCC.exe，
      可用环境变量 ISCC 指定其它路径）
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "packaging"
PY = sys.executable


def run(cmd: list[str], title: str) -> None:
    print(f"\n=== {title} ===")
    print("$", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        raise SystemExit(f"[失败] {title}（退出码 {result.returncode}）")


def find_iscc() -> str:
    env = os.environ.get("ISCC")
    if env and Path(env).is_file():
        return env
    for cand in (
        Path(r"C:\Program Files\Inno Setup 7\ISCC.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 7\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    ):
        if cand.is_file():
            return str(cand)
    raise SystemExit(
        "找不到 Inno Setup 的 ISCC.exe。请安装 Inno Setup 7，"
        "或用环境变量 ISCC 指向它。")


def read_version() -> str:
    """从 app/__init__.py 读出 __version__（安装包脚本要用它）。"""
    import re
    text = (ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.M)
    if not match:
        raise SystemExit("读不到 app/__init__.py 里的 __version__")
    return match.group(1)


def main() -> int:
    version = read_version()
    print(f"应用版本：{version}")

    # 1) 图标（多尺寸 .ico，PyInstaller 与 Inno Setup 都用它）
    run([PY, str(ROOT / "tools" / "makeicon.py")], "生成应用图标")

    # 2) 先把正在运行的旧版本关掉，否则覆盖文件会 PermissionError
    subprocess.run(["taskkill", "/IM", "YtDlpGui.exe", "/F"],
                   capture_output=True, text=True)

    # 3) PyInstaller（--clean 保证不残留上一次的文件）
    run([PY, "-m", "PyInstaller", "--noconfirm", "--clean",
         "--distpath", str(PKG / "dist"), "--workpath", str(PKG / "build"),
         str(PKG / "YtDlpGui.spec")], "PyInstaller 打包")

    exe = PKG / "dist" / "YtDlpGui" / "YtDlpGui.exe"
    if not exe.is_file():
        raise SystemExit(f"[失败] 没找到 {exe}")

    # 4) Inno Setup（版本号通过 /D 传进去，避免 .iss 与 app/__init__.py 两处不一致）
    run([find_iscc(), f"/DMyAppVersion={version}", str(PKG / "installer.iss")],
        "编译安装包")

    setup = next((PKG / "output").glob("*-setup.exe"), None)
    if setup is None:
        raise SystemExit("[失败] 没有生成 setup.exe")

    dist_mb = sum(f.stat().st_size for f in (PKG / "dist" / "YtDlpGui").rglob("*")
                  if f.is_file()) / 1024 / 1024
    print("\n=== 打包完成 ===")
    print(f"  发行目录：{PKG / 'dist' / 'YtDlpGui'}（{dist_mb:.1f} MB）")
    print(f"  安装包  ：{setup}（{setup.stat().st_size / 1024 / 1024:.1f} MB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
