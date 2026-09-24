"""哔哩哔哩扫码登录。

登录流程与 BBDown / bilidown 等工具一致：

1. 请求 passport 的 qrcode/generate 接口拿到二维码内容与 qrcode_key；
2. 用户用手机客户端扫码；
3. 轮询 qrcode/poll，成功后从响应头取得 SESSDATA 等 Cookie；
4. 把 Cookie 写成 Netscape 格式的 cookies.txt 供 yt-dlp 使用。

登录后即可解析 1080P 高码率、4K、8K、HDR 与 60fps 等需要大会员的内容。
"""
from __future__ import annotations

import json
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtCore import Qt

from .helpers import app_data_dir

QR_GENERATE = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
QR_POLL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
NAV_API = "https://api.bilibili.com/x/web-interface/nav"

COOKIE_FILE = app_data_dir() / "bilibili_cookies.txt"
QR_IMAGE = app_data_dir() / "cache" / "bilibili_qr.png"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# poll 返回的 code
POLL_WAITING = 86101      # 未扫码
POLL_SCANNED = 86090      # 已扫码待确认
POLL_EXPIRED = 86038      # 二维码已过期
POLL_OK = 0               # 登录成功

STATUS_TEXT = {
    POLL_WAITING: "请使用哔哩哔哩手机客户端扫描二维码",
    POLL_SCANNED: "已扫码，请在手机上确认登录",
    POLL_EXPIRED: "二维码已过期，请点击刷新",
    POLL_OK: "登录成功",
}


def is_bilibili_url(url: str) -> bool:
    return "bilibili.com" in (url or "").lower() or "b23.tv" in (url or "").lower()


def _ssl() -> ssl.SSLContext:
    try:
        return ssl.create_default_context()
    except Exception:
        return ssl._create_unverified_context()  # type: ignore[attr-defined]


def _get(url: str, cookies: Optional[Dict[str, str]] = None,
         timeout: int = 20) -> Tuple[int, Any, str]:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    req.add_header("Referer", "https://www.bilibili.com/")
    if cookies:
        req.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()))
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl()) as resp:
        body = resp.read().decode("utf-8", "replace")
        return resp.status, resp.headers, body


def parse_set_cookie(headers: Any) -> Dict[str, str]:
    """从响应头里取出所有 Cookie 键值。"""
    out: Dict[str, str] = {}
    try:
        raw = headers.get_all("Set-Cookie") or []
    except Exception:
        raw = []
    for item in raw:
        first = item.split(";", 1)[0]
        if "=" not in first:
            continue
        name, value = first.split("=", 1)
        name, value = name.strip(), value.strip()
        if name:
            out[name] = value
    return out


def write_cookies(cookies: Dict[str, str], path: Path = COOKIE_FILE) -> None:
    """写成 yt-dlp 能识别的 Netscape cookies.txt。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    expire = int(time.time()) + 180 * 24 * 3600
    lines = ["# Netscape HTTP Cookie File", "# 由 yt-dlp 图形用户界面生成", ""]
    for name, value in cookies.items():
        lines.append("\t".join([".bilibili.com", "TRUE", "/", "FALSE", str(expire), name, value]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_cookies(path: Path = COOKIE_FILE) -> Dict[str, str]:
    out: Dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                out[parts[5]] = parts[6]
    except Exception:
        pass
    return out


def render_qr(data: str, path: Path = QR_IMAGE) -> str:
    """把二维码内容渲染成 PNG，返回文件路径。"""
    try:
        import qrcode  # type: ignore
    except ImportError:
        from .deps import ensure_package
        if not ensure_package("qrcode"):
            raise RuntimeError("缺少二维码组件，无法生成二维码")
        import qrcode  # type: ignore

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    matrix: List[List[bool]] = qr.get_matrix()
    n = len(matrix)
    scale = max(4, min(10, 460 // max(n, 1)))
    img = QImage(n * scale, n * scale, QImage.Format.Format_RGB32)
    img.fill(QColor("#FFFFFF"))
    painter = QPainter(img)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#0B0E15"))
    for y, row in enumerate(matrix):
        for x, cell in enumerate(row):
            if cell:
                painter.drawRect(x * scale, y * scale, scale, scale)
    painter.end()
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), "PNG")
    return str(path)


# ----------------------------------------------------------------------
class BilibiliAuth(QObject):
    """哔哩哔哩扫码登录与登录状态。"""

    changed = Signal()
    qrReady = Signal(str)          # 二维码图片路径
    statusChanged = Signal(str)    # 当前状态文案
    failed = Signal(str)
    loginSucceeded = Signal(str)   # 登录成功（参数为账号名）

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._key = ""
        self._qr_path = ""
        self._status = "尚未登录"
        self._polling = False
        self._stop = threading.Event()
        self._user: Dict[str, Any] = {}
        self._check_existing()

    # ------------------------------------------------------------------
    def _check_existing(self) -> None:
        if not COOKIE_FILE.exists():
            return
        cookies = read_cookies()
        if not cookies.get("SESSDATA"):
            self._status = "尚未登录"
            return
        threading.Thread(target=self._fetch_user, args=(cookies,), daemon=True,
                         name="bili-nav").start()

    def _fetch_user(self, cookies: Dict[str, str]) -> None:
        try:
            _status, _h, body = _get(NAV_API, cookies)
            data = json.loads(body)
            info = data.get("data") or {}
            if data.get("code") == 0 and info.get("isLogin"):
                first_time = not self._user
                self._user = info
                self._status = self._build_status(info)
                if first_time:
                    self.loginSucceeded.emit(str(info.get("uname") or ""))
            else:
                self._user = {}
                self._status = "登录状态已失效，请重新扫码"
        except Exception:
            self._user = {}
            self._status = "无法验证登录状态"
        self.changed.emit()

    @staticmethod
    def _build_status(info: Dict[str, Any]) -> str:
        name = str(info.get("uname") or "已登录")
        vip = int(info.get("vipStatus") or 0)
        vip_type = int(info.get("vipType") or 0)
        if vip and vip_type == 2:
            return f"{name}（年度大会员）"
        if vip:
            return f"{name}（大会员）"
        return f"{name}（普通用户）"

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------
    @Property(bool, notify=changed)
    def loggedIn(self) -> bool:
        return bool(self._user.get("isLogin"))

    @Property(str, notify=changed)
    def statusText(self) -> str:
        return self._status

    @Property(str, notify=changed)
    def userName(self) -> str:
        return str(self._user.get("uname") or "")

    @Property(str, notify=changed)
    def userFace(self) -> str:
        return str(self._user.get("face") or "")

    @Property(bool, notify=changed)
    def isVip(self) -> bool:
        return bool(int(self._user.get("vipStatus") or 0))

    @Property(str, notify=changed)
    def vipText(self) -> str:
        return "大会员" if self.isVip else "普通用户"

    @Property(str, notify=changed)
    def qrPath(self) -> str:
        if not self._qr_path:
            return ""
        try:
            stamp = int(Path(self._qr_path).stat().st_mtime)
        except OSError:
            stamp = 0
        return "file:///" + self._qr_path.replace("\\", "/") + f"?v={stamp}"

    @Property(bool, notify=changed)
    def polling(self) -> bool:
        return self._polling

    @Property(str, constant=True)
    def cookiePath(self) -> str:
        return str(COOKIE_FILE)

    # ------------------------------------------------------------------
    # 登录
    # ------------------------------------------------------------------
    @Slot()
    def startLogin(self) -> None:
        if self._polling:
            return
        self._stop.clear()
        threading.Thread(target=self._login_worker, daemon=True,
                         name="bili-login").start()

    def _login_worker(self) -> None:
        self._polling = True
        self._status = "正在获取二维码…"
        self.changed.emit()

        try:
            _status, _h, body = _get(QR_GENERATE)
            data = json.loads(body)
            payload = data.get("data") or {}
            url = str(payload.get("url") or "")
            self._key = str(payload.get("qrcode_key") or "")
            if data.get("code") != 0 or not url or not self._key:
                raise RuntimeError(str(data.get("message") or "无法获取二维码"))
            self._qr_path = render_qr(url)
            self.qrReady.emit(self.qrPath)
            self._status = STATUS_TEXT[POLL_WAITING]
            self.changed.emit()
        except Exception as exc:  # noqa: BLE001
            self._polling = False
            self._status = "获取二维码失败"
            self.changed.emit()
            self.failed.emit(f"无法获取登录二维码：{exc}")
            return

        deadline = time.time() + 180
        while not self._stop.is_set() and time.time() < deadline:
            time.sleep(2.0)
            if self._stop.is_set():
                break
            try:
                _status, headers, body = _get(f"{QR_POLL}?qrcode_key={self._key}")
                data = json.loads(body)
                info = data.get("data") or {}
                code = int(info.get("code") or 0)
                if code == POLL_OK:
                    cookies = parse_set_cookie(headers)
                    if not cookies.get("SESSDATA"):
                        cookies.update(self._cookies_from_url(str(info.get("url") or "")))
                    if not cookies.get("SESSDATA"):
                        raise RuntimeError("登录成功但未能取得 Cookie")
                    write_cookies(cookies)
                    self._polling = False
                    self._status = "登录成功，正在读取账号信息…"
                    self.changed.emit()
                    self._fetch_user(cookies)
                    return
                if code in (POLL_WAITING, POLL_SCANNED):
                    text = STATUS_TEXT[code]
                    if text != self._status:
                        self._status = text
                        self.changed.emit()
                    continue
                if code == POLL_EXPIRED:
                    self._polling = False
                    self._status = STATUS_TEXT[POLL_EXPIRED]
                    self.changed.emit()
                    return
            except Exception:
                continue

        self._polling = False
        if not self.loggedIn:
            self._status = "登录超时，请重新获取二维码"
        self.changed.emit()

    @staticmethod
    def _cookies_from_url(url: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for key in ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5", "sid"):
            match = re.search(rf"[?&]{key}=([^&]+)", url or "")
            if match:
                out[key] = urllib.parse.unquote(match.group(1))
        return out

    @Slot()
    def cancelLogin(self) -> None:
        self._stop.set()
        self._polling = False
        if not self.loggedIn:
            self._status = "尚未登录"
        self.changed.emit()

    @Slot()
    def logout(self) -> None:
        self._stop.set()
        self._polling = False
        self._user = {}
        self._status = "尚未登录"
        try:
            COOKIE_FILE.unlink()
        except OSError:
            pass
        self.changed.emit()

    @Slot()
    def refresh(self) -> None:
        if COOKIE_FILE.exists():
            threading.Thread(target=self._fetch_user, args=(read_cookies(),),
                             daemon=True, name="bili-nav").start()

    @Slot()
    def openCookieFolder(self) -> None:
        from .helpers import open_in_explorer
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        open_in_explorer(str(COOKIE_FILE.parent))
