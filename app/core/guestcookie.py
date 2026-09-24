"""自动获取访客 Cookie（通过 CDP 连接本机浏览器）。

用途
----
短时间内连续下载多个 YouTube 视频时，YouTube 会因为缺少有效的访客会话
而限流（429 / “Sign in to confirm you're not a bot”）。常见的解决办法是
传入一份 Cookie，但这**并不一定需要登录** —— YouTube 的访客标识
（VISITOR_INFO1_LIVE、VISITOR_PRIVACY_METADATA 等）本身就足以缓解限流。

为什么用 CDP 而不是直接读浏览器的 Cookie 文件
----------------------------------------------
Chrome / Edge 新版启用了 App-Bound Encryption，磁盘上的 Cookie 由浏览器
进程身份保护，外部程序无法解密（yt-dlp 的 --cookies-from-browser 会报
“Failed to decrypt with DPAPI”）。但浏览器自己显然能解密 —— 通过
DevTools 协议（CDP）让浏览器把 Cookie 以明文返回，即可绕开这一限制，
而且拿到的是**真实浏览器**签发的会话，不会被判定为嵌入式浏览器。

实现上使用 Python 自带的 ``websockets`` 库（本机已验证可用）通过 CDP
抓取明文 Cookie，而不是 QtWebSockets + 嵌套事件循环——后者在子线程里
与 Qt 事件循环互相打架，回调永远收不到。
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QThread, Signal, Slot

from .helpers import app_data_dir

GUEST_DIR = app_data_dir() / "cookies"
GUEST_FILE = GUEST_DIR / "guest_cookies.txt"
PROFILE_DIR = app_data_dir() / "guestprofile"

TARGET_URL = "https://www.youtube.com/"
PAGE_WAIT_MS = 9000        # 等待页面建立会话
GRAB_DELAY_MS = 2500       # 发出取 Cookie 命令后的等待
OVERALL_TIMEOUT_MS = 45000


def _log(message: str) -> None:
    """写诊断日志，与登录模块共用同一个文件。"""
    try:
        log_dir = app_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_dir / "weblogin.log", "a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] [访客Cookie] {message}\n")
    except Exception:  # noqa: BLE001
        pass


def find_browser() -> str:
    """在本机常见位置找一个可用的 Chromium 系浏览器。"""
    local = os.environ.get("LOCALAPPDATA", "")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    cands = [
        Path(pf) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(pf86) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(pf86) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(pf) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(local) / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]
    for path in cands:
        try:
            if path.is_file():
                return str(path)
        except OSError:
            continue
    return ""


def guest_cookie_path() -> Optional[Path]:
    """已缓存的访客 Cookie 文件；不存在则返回 None。"""
    try:
        if GUEST_FILE.is_file() and GUEST_FILE.stat().st_size > 0:
            return GUEST_FILE
    except OSError:
        pass
    return None


def write_guest_cookies(cookies: List[Dict[str, Any]]) -> int:
    """把 CDP 返回的 Cookie 写成 Netscape 文件，返回条数。"""
    lines = ["# Netscape HTTP Cookie File",
             "# 由 yt-dlp 图形用户界面自动获取（访客会话，不含登录凭据）", ""]
    count = 0
    for c in cookies:
        domain = str(c.get("domain") or "").strip()
        name = str(c.get("name") or "").strip()
        if not domain or not name:
            continue
        # CDP 用 -1 表示会话 Cookie，Netscape 格式里用 0
        try:
            expires = float(c.get("expires") or -1)
        except (TypeError, ValueError):
            expires = -1
        stamp = str(int(expires)) if expires > 0 else "0"
        prefix = "#HttpOnly_" if c.get("httpOnly") else ""
        lines.append("\t".join([
            prefix + domain,
            "TRUE" if domain.startswith(".") else "FALSE",
            str(c.get("path") or "/"),
            "TRUE" if c.get("secure") else "FALSE",
            stamp,
            name,
            str(c.get("value") or ""),
        ]))
        count += 1
    GUEST_DIR.mkdir(parents=True, exist_ok=True)
    tmp = GUEST_FILE.with_suffix(".txt.tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(GUEST_FILE)
    return count


class GuestCookieWorker(QThread):
    """在后台线程里通过 CDP 抓取访客 Cookie。

    会临时启动一个无头浏览器（使用独立的用户数据目录，不影响用户
    正在使用的浏览器），拿到 Cookie 后立即关闭。

    通信使用 Python 的 ``websockets`` 库（已在本机验证可用），而不是
    QWebSocket + 嵌套事件循环——后者在子线程里与 Qt 事件循环互相打架，
    导致连接永远收不到回调。

    直接继承 QThread 并在 run() 里干活，避开 moveToThread + started
    信号在跨线程槽调用时的怪异行为。
    """

    finished = Signal(int, str)      # 条数, 错误信息（空串表示成功）

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._proc: Any = None

    # ------------------------------------------------------------------
    def run(self) -> None:
        _log("run() 开始执行")
        try:
            import websockets  # 延迟导入，避免缺包时拖垮整个 bridge
        except Exception as exc:  # noqa: BLE001
            self._finish(0, f"缺少 websockets 库：{exc}")
            return

        browser = find_browser()
        if not browser:
            self._finish(0, "未在本机找到 Chrome 或 Edge")
            return
        _log(f"使用浏览器: {browser}")

        port = self._pick_port()
        try:
            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            self._proc = subprocess.Popen(
                [browser, "--headless=new", f"--remote-debugging-port={port}",
                 f"--user-data-dir={PROFILE_DIR}", "--no-first-run",
                 "--no-default-browser-check", "--disable-gpu",
                 "--no-sandbox", "--mute-audio", "about:blank"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:  # noqa: BLE001
            self._finish(0, f"无法启动浏览器：{exc}")
            return

        ws_url = self._wait_for_target(port)
        if not ws_url:
            _log(f"调试端口 {port} 在限定时间内未就绪")
            self._finish(0, "浏览器调试端口未就绪")
            self._cleanup()
            return
        _log(f"浏览器已启动，调试地址 {ws_url}")

        try:
            count = asyncio.run(self._grab(websockets, ws_url))
        except Exception as exc:  # noqa: BLE001
            self._finish(0, f"获取 Cookie 失败：{exc}")
            self._cleanup()
            return

        if count <= 0:
            self._finish(0, "浏览器未返回任何 Cookie（可能未联网）")
            self._cleanup()
            return
        self._finish(count, "")

    # ------------------------------------------------------------------
    @staticmethod
    def _pick_port() -> int:
        """挑一个空闲端口，避免与用户自己的调试实例冲突。"""
        for port in range(9333, 9400):
            with socket.socket() as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        return 9333

    @staticmethod
    def _wait_for_target(port: int, timeout: float = 25.0) -> str:
        """轮询 /json/list 直到出现 page target，返回其 WebSocket 地址。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/json/list", timeout=2) as resp:
                    targets = json.loads(resp.read().decode("utf-8", "replace"))
                for item in targets:
                    if item.get("type") == "page" and item.get("webSocketDebuggerUrl"):
                        return str(item["webSocketDebuggerUrl"])
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.5)
        return ""

    # ------------------------------------------------------------------
    async def _grab(self, websockets, ws_url: str) -> int:
        """连接 CDP，导航到 YouTube，取回访客 Cookie 并写盘。"""
        async with websockets.connect(ws_url, max_size=None) as conn:
            mid = 0

            async def call(method: str, params: Dict[str, Any] | None = None):
                nonlocal mid
                mid += 1
                await conn.send(json.dumps(
                    {"id": mid, "method": method, "params": params or {}}))
                while True:
                    msg = json.loads(await conn.recv())
                    if msg.get("id") == mid:
                        return msg.get("result", {})

            await call("Page.enable")
            await call("Network.enable")
            await call("Page.navigate", {"url": TARGET_URL})
            # 等页面真正建立会话（YouTube 会在此下发 VISITOR_INFO1_LIVE 等）
            await asyncio.sleep(PAGE_WAIT_MS / 1000.0)
            result = await call("Network.getCookies")
            cookies = list(result.get("cookies") or [])
            _log(f"收到 {len(cookies)} 个 Cookie")

        count = write_guest_cookies(cookies)
        _log(f"已写入 {count} 条到 {GUEST_FILE}")
        return count

    # ------------------------------------------------------------------
    def _finish(self, count: int, error: str) -> None:
        self._cleanup()
        self.finished.emit(count, error)

    def _cleanup(self) -> None:
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                try:
                    self._proc.kill()
                except Exception:  # noqa: BLE001
                    pass
        self._proc = None
