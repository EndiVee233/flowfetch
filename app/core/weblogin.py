"""程序内账号登录：在应用自带的浏览器里登录一次，之后长期有效。

为什么不让用户从浏览器读取 Cookies
------------------------------------
Chrome / Edge 从 v127 起默认启用 App-Bound Encryption（ABE），
Cookie 的解密密钥被绑定到浏览器自身进程，第三方程序无法解密，
yt-dlp 读取时会报 “Failed to decrypt with DPAPI”。

因此这里改为：让用户在程序自带的浏览器里登录一次，Cookies 由本程序自己
持有并持久化，再导出成 Netscape 格式供 yt-dlp 使用。
只要用户不主动退出，登录态可以保持很久，无需反复提取。

关于 Google 拒绝嵌入式浏览器
----------------------------
Google 会拦截嵌入式浏览器的登录（提示 “This browser or app may not be secure”）。
经验做法（qutebrowser 等长期使用）是把 User-Agent 伪装成 Firefox 即可通过，
本模块对 accounts.google.com 单独下发 Firefox UA。
"""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal, Slot

from .helpers import app_data_dir

COOKIE_DIR = app_data_dir() / "cookies"
PROFILE_DIR = app_data_dir() / "webprofile"

# 伪装成 Firefox，绕过 Google 对嵌入式浏览器的拦截
FIREFOX_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) "
              "Gecko/20100101 Firefox/131.0")

# 需要特殊 UA 的主机
_UA_HOSTS = ("accounts.google.com", "accounts.youtube.com", "myaccount.google.com")


def _site_config() -> Dict[str, Dict[str, Any]]:
    """各站点的登录入口与判定规则。"""
    return {
        "youtube": {
            "label": "YouTube",
            # service=youtube 登录成功后会跳回 youtube.com
            "startUrl": ("https://accounts.google.com/v3/signin/identifier"
                         "?service=youtube&continue=https%3A%2F%2Fwww.youtube.com%2F"
                         "&hl=zh-CN&flowName=GlifWebSignIn"),
            "cookieDomains": (
                "youtube.com", "google.com", "googleusercontent.com",
                "googlevideo.com", "ytimg.com", "ggpht.com",
                "googleapis.com", "gstatic.com",
            ),
            # 出现其中任意一个即认为已登录
            "loginCookies": ("SID", "__Secure-1PSID", "__Secure-3PSID", "LOGIN_INFO"),
        },
    }


def snapshot_for_url(url: str) -> str:
    """按 URL 找到程序内登录导出的凭据文件；没有则返回空串。

    供下载与解析时选用，不依赖 WebLoginManager 实例，避免模块互相引用。
    """
    if not url:
        return ""
    try:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return ""
    if not host:
        return ""
    for key, cfg in _site_config().items():
        if any(host == d or host.endswith("." + d) for d in cfg["cookieDomains"]):
            path = COOKIE_DIR / f"{key}_cookies.txt"
            if path.is_file():
                return str(path)
    return ""


LOG_DIR = app_data_dir() / "logs"


def log(message: str) -> None:
    """写诊断日志。

    登录涉及 QtWebEngine 与 Google 的多步交互，出问题时很难复现，
    因此把关键节点落盘，便于用户反馈时定位。
    """
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_DIR / "weblogin.log", "a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] {message}\n")
    except Exception:  # noqa: BLE001
        pass


class _YdlLogger:
    """yt-dlp 解密器需要的 logger 接口。

    签名必须容忍额外参数：yt-dlp 会以 warning(msg, only_once=True) 的形式调用，
    只接受 msg 会抛 TypeError 并导致解密整体失败。
    """

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        log(f"  yt-dlp: {msg}")

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        log(f"  yt-dlp 错误: {msg}")


def _cookie_db_path() -> Optional[Path]:
    """QtWebEngine 的 Cookies 数据库位置（新版本在 Network 子目录下）。"""
    for cand in (PROFILE_DIR / "Cookies", PROFILE_DIR / "Network" / "Cookies"):
        try:
            if cand.is_file() and cand.stat().st_size > 0:
                return cand
        except OSError:
            continue
    return None


def _decrypt_dpapi(blob: bytes) -> str:
    """直接用 Windows DPAPI 解密。

    QtWebEngine 自带的 Chromium 未必带 Local State 密钥文件，
    这种情况下 Cookie 是以 DPAPI 直接加密的（同样带 v10 前缀），
    yt-dlp 的解密器会因为「no key found」失败，必须自己兜底。
    """
    if not blob:
        return ""
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:  # noqa: BLE001
        return ""

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(blob, len(blob))
    src = _Blob(len(blob), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    dst = _Blob()
    try:
        ok = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(src), None, None, None, None, 0, ctypes.byref(dst))
    except Exception as exc:  # noqa: BLE001
        log(f"  DPAPI 调用异常: {exc}")
        return ""
    if not ok:
        return ""
    try:
        data = ctypes.string_at(dst.pbData, dst.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(dst.pbData)
    return data.decode("utf-8", "replace")


def _decrypt_value(encrypted: bytes) -> str:
    """尝试解密 Cookie 的 encrypted_value，按可能性依次回退。"""
    if not encrypted:
        return ""
    # 1) 交给 yt-dlp：处理「Local State 密钥 + AES-GCM」的现代格式
    try:
        from yt_dlp.cookies import WindowsChromeCookieDecryptor
        decryptor = WindowsChromeCookieDecryptor(str(PROFILE_DIR), _YdlLogger())
        value = decryptor.decrypt(encrypted) or ""
        if value:
            return value
    except Exception as exc:  # noqa: BLE001
        log(f"  yt-dlp 解密失败: {type(exc).__name__}: {exc}")

    # 2) 回退：去掉 v10/v11/v20 前缀后直接 DPAPI 解密
    prefix = bytes(encrypted[:3])
    payload = encrypted[3:] if prefix in (b"v10", b"v11", b"v20") else encrypted
    value = _decrypt_dpapi(payload)
    if value:
        log("  已通过 DPAPI 回退解密")
    return value


def _chrome_time(value: Any) -> int:
    """Chromium 的过期时间是「1601 年起的微秒数」，换成 Unix 秒。"""
    try:
        stamp = int(value)
    except (TypeError, ValueError):
        return 0
    if stamp <= 0:
        return 0
    return int(stamp / 1_000_000 - 11644473600)


def read_profile_cookies() -> List[Dict[str, Any]]:
    """直接从 QtWebEngine 的 profile 目录读取 Cookies。

    为什么不只依赖 QWebEngineCookieStore 的信号：在部分环境
    （无头模式、Cookie 后端未就绪）下 cookieAdded / cookieFilter
    完全不触发，会导致「明明登录成功却检测不到」。这里作为兜底，
    直接读磁盘上的数据库，更可靠且不依赖 Qt 的回调时序。
    """
    db = _cookie_db_path()
    if db is None:
        log("磁盘读取：未找到 Cookies 数据库")
        return []
    tmp_dir = Path(tempfile.mkdtemp(prefix="ytdlp_ck_"))
    tmp_db = tmp_dir / "Cookies"
    try:
        shutil.copy2(db, tmp_db)      # 复制一份，避免与浏览器进程抢锁
    except OSError as exc:
        log(f"磁盘读取：复制数据库失败 {exc}")
        return []

    out: List[Dict[str, Any]] = []
    try:
        con = sqlite3.connect(str(tmp_db))
        cur = con.cursor()
        # Chromium 各版本的 cookies 表列名不完全一致，先探测再查询
        cols = {row[1] for row in cur.execute("PRAGMA table_info(cookies)")}
        if not cols:
            log("磁盘读取：cookies 表不存在")
            con.close()
            return []
        http_col = "is_httponly" if "is_httponly" in cols else "0"
        secure_col = "is_secure" if "is_secure" in cols else "0"
        cur.execute(f"SELECT host_key, name, value, encrypted_value, path, "
                    f"expires_utc, {secure_col}, {http_col} FROM cookies")
        rows = cur.fetchall()
        con.close()
        log(f"磁盘读取：表结构 {sorted(cols)[:6]}…")
    except Exception as exc:  # noqa: BLE001
        log(f"磁盘读取：查询失败 {type(exc).__name__}: {exc}")
        return []

    for host, name, value, enc, path, expires, secure, httponly in rows:
        plain = str(value or "")
        if not plain and enc:
            plain = _decrypt_value(bytes(enc))
        if not plain:
            continue
        out.append({
            "domain": str(host or ""),
            "name": str(name or ""),
            "value": plain,
            "path": str(path or "/"),
            "expires": _chrome_time(expires),
            "secure": bool(secure),
            "httpOnly": bool(httponly),
        })
    log(f"磁盘读取：共 {len(out)} 项（数据库 {len(rows)} 行）")
    return out


def _is_data_line(line: str) -> bool:
    """判断 cookies.txt 的一行是不是数据行。

    注意 Netscape 格式里 HttpOnly 的 Cookie 行以 “#HttpOnly_.” 开头，
    不能当成注释跳过 —— Google 的 SID 等关键凭据都是 HttpOnly。
    """
    if not line:
        return False
    if line.startswith("#HttpOnly_"):
        return True
    return not line.startswith("#")


class WebLoginManager(QObject):
    """管理程序内登录得到的 Cookies。"""

    changed = Signal()
    statusChanged = Signal(str)
    loginSucceeded = Signal(str, str)    # 站点 key, 站点名称
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._sites = _site_config()
        self._windows: Dict[str, Any] = {}
        self._profile: Any = None
        COOKIE_DIR.mkdir(parents=True, exist_ok=True)

    def profile(self):
        """懒加载并复用同一个 WebEngine profile。

        必须复用：profile 的 storageName 相同，重复创建会与已有实例冲突；
        而且页面与 cookieStore 必须绑定在同一个 profile 上，否则
        监听 cookieAdded 的 store 与页面实际写入的 store 不是同一个，
        会出现“登录成功却永远收不到 Cookie”。
        """
        if self._profile is None:
            from PySide6.QtWebEngineCore import QWebEngineProfile
            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            profile = QWebEngineProfile("ytlogin", self)
            profile.setPersistentStoragePath(str(PROFILE_DIR))
            profile.setPersistentCookiesPolicy(
                QWebEngineProfile.ForcePersistentCookies)
            profile.setHttpUserAgent(FIREFOX_UA)
            self._profile = profile
            log(f"创建 WebEngine profile: {profile.persistentStoragePath()}")
        return self._profile

    # ------------------------------------------------------------------
    # 路径与基础信息
    # ------------------------------------------------------------------
    @staticmethod
    def cookieDir() -> str:
        return str(COOKIE_DIR)

    def snapshot_path(self, site: str) -> Path:
        return COOKIE_DIR / f"{site}_cookies.txt"

    def siteLabel(self, site: str) -> str:
        cfg = self._sites.get(site)
        return str(cfg["label"]) if cfg else site

    @Slot(result="QVariantList")
    def siteList(self) -> List[Dict[str, Any]]:
        out = []
        for key, cfg in self._sites.items():
            out.append({
                "key": key,
                "label": cfg["label"],
                "loggedIn": self.isLoggedIn(key),
                "statusText": self.statusText(key),
            })
        return out

    # ------------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------------
    def _snapshot_info(self, site: str) -> Tuple[int, float]:
        """返回 (cookie 条数, 最早的过期时间戳)。没有快照时返回 (0, 0)。"""
        path = self.snapshot_path(site)
        if not path.is_file():
            return 0, 0.0
        count = 0
        earliest = 0.0
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not _is_data_line(line):
                    continue
                parts = line.split("\t")
                if len(parts) < 7:
                    continue
                count += 1
                try:
                    exp = float(parts[4])
                except ValueError:
                    continue
                if exp > 0 and (earliest == 0 or exp < earliest):
                    earliest = exp
        except OSError:
            return 0, 0.0
        return count, earliest

    def isLoggedIn(self, site: str) -> bool:
        """快照存在、未过期且包含登录 Cookie 才算已登录。"""
        cfg = self._sites.get(site)
        if not cfg:
            return False
        path = self.snapshot_path(site)
        if not path.is_file():
            return False
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        now = time.time()
        for name in cfg["loginCookies"]:
            marker = "\t" + name + "\t"
            for line in text.splitlines():
                line = line.strip()
                if not _is_data_line(line):
                    continue
                if marker not in line:
                    continue
                parts = line.split("\t")
                if len(parts) < 7:
                    continue
                try:
                    exp = float(parts[4])
                except ValueError:
                    return True      # 会话 Cookie，视为有效
                if exp <= 0 or exp > now:
                    return True
        return False

    def statusText(self, site: str) -> str:
        cfg = self._sites.get(site)
        if not cfg:
            return ""
        count, earliest = self._snapshot_info(site)
        if count == 0:
            return "尚未登录"
        if not self.isLoggedIn(site):
            return "未检测到有效的登录凭据，请重新登录"
        if earliest <= 0:
            return f"已登录（{count} 项凭据）"
        days = int((earliest - time.time()) / 86400)
        if days <= 0:
            return "凭据即将过期，建议重新登录"
        if days > 365:
            return f"已登录，凭据约 {days // 365} 年后到期"
        return f"已登录，凭据约 {days} 天后到期"

    @Slot(str, result="QVariantMap")
    def siteStatus(self, site: str) -> Dict[str, Any]:
        count, earliest = self._snapshot_info(site)
        return {
            "key": site,
            "label": self.siteLabel(site),
            "loggedIn": self.isLoggedIn(site),
            "statusText": self.statusText(site),
            "cookieCount": count,
            "expiresAt": earliest,
        }

    # ------------------------------------------------------------------
    # 登录 / 退出
    # ------------------------------------------------------------------
    @Slot(str)
    def startLogin(self, site: str) -> None:
        """打开登录窗口。"""
        cfg = self._sites.get(site)
        if not cfg:
            self.failed.emit("未知的登录目标")
            return
        existing = self._windows.get(site)
        if existing is not None:
            try:
                existing.raise_()
                existing.activateWindow()
                return
            except RuntimeError:
                self._windows.pop(site, None)
        try:
            window = _LoginWindow(site, cfg, self)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"无法打开登录窗口：{exc}")
            return
        self._windows[site] = window
        self.statusChanged.emit("正在打开登录窗口…")
        window.show()

    def _forget_window(self, site: str) -> None:
        self._windows.pop(site, None)

    @Slot()
    def openLogFolder(self) -> None:
        """打开诊断日志目录，便于反馈登录问题时排查。"""
        from .helpers import open_in_explorer
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        open_in_explorer(str(LOG_DIR))

    @Slot(str)
    def logout(self, site: str) -> None:
        """删除导出的凭据与浏览器内的会话。"""
        path = self.snapshot_path(site)
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass
        window = self._windows.get(site)
        if window is not None:
            try:
                window.clearCookies()
            except Exception:  # noqa: BLE001
                pass
        self.changed.emit()

    def onLoginFinished(self, site: str, exported: int) -> None:
        """登录窗口检测到登录成功后回调。"""
        if exported > 0:
            self.loginSucceeded.emit(site, self.siteLabel(site))
        self.changed.emit()


# ----------------------------------------------------------------------
# 登录窗口
# ----------------------------------------------------------------------
def _qcookie_to_dict(cookie) -> Dict[str, Any]:
    """把 QNetworkCookie 规范成统一结构，便于与磁盘读取的结果合并。"""
    try:
        expiry = cookie.expirationDate()
        stamp = int(expiry.toSecsSinceEpoch()) if expiry and expiry.isValid() else 0
    except Exception:  # noqa: BLE001
        stamp = 0
    return {
        "domain": str(cookie.domain() or ""),
        "name": bytes(cookie.name()).decode("utf-8", "replace"),
        "value": bytes(cookie.value()).decode("utf-8", "replace"),
        "path": str(cookie.path() or "/"),
        "expires": stamp,
        "secure": bool(cookie.isSecure()),
        "httpOnly": bool(cookie.isHttpOnly()),
    }


def _netscape_line(item: Dict[str, Any]) -> str:
    """把一条 Cookie 转成 Netscape cookies.txt 的一行。"""
    domain = str(item.get("domain") or "")
    # 以点开头表示同时匹配子域
    include_sub = "TRUE" if domain.startswith(".") else "FALSE"
    if item.get("httpOnly"):
        domain = "#HttpOnly_" + domain
    return "\t".join([
        domain,
        include_sub,
        str(item.get("path") or "/"),
        "TRUE" if item.get("secure") else "FALSE",
        str(int(item.get("expires") or 0)),
        str(item.get("name") or ""),
        str(item.get("value") or ""),
    ])


class _LoginWindow(QObject):
    """用内嵌浏览器完成登录的独立窗口。

    之所以用 QWidget 而不是 QML：QtWebEngine 会接管 OpenGL 上下文，
    放进主 QML 窗口容易影响无边框圆角等自绘效果；登录窗口是临时流程，
    独立窗口更稳妥。
    """

    def __init__(self, site: str, cfg: Dict[str, Any], manager: WebLoginManager) -> None:
        from PySide6.QtWidgets import (QHBoxLayout, QLabel, QProgressBar,
                                       QPushButton, QVBoxLayout, QWidget)
        from PySide6.QtWebEngineCore import QWebEnginePage
        from PySide6.QtWebEngineWidgets import QWebEngineView

        super().__init__(manager)
        self._site = site
        self._cfg = cfg
        self._manager = manager
        self._cookies: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        self._done = False
        self._pending = False
        self._last_disk_check = 0.0   # 磁盘兜底读取的限流时间戳
        self._seen = 0                # 收到的 cookie 总数，仅用于日志

        self.profile = manager.profile()
        self.store = self.profile.cookieStore()
        self.store.cookieAdded.connect(self._on_cookie_added)

        self.window = QWidget()
        self.window.setWindowTitle(f"登录 {cfg['label']}")
        self.window.resize(900, 680)
        self.window.setStyleSheet("background:#141A2B; color:#EEF1F8;")
        self.window.destroyed.connect(lambda *_a: manager._forget_window(site))

        self.title = QLabel(f"登录 {cfg['label']}")
        self.title.setStyleSheet("font-size:15px; font-weight:600; padding:2px;")
        self.status = QLabel("正在打开登录页面…")
        self.status.setStyleSheet("color:#BCC4D4; font-size:12px;")
        self.progress = QProgressBar()
        self.progress.setMaximum(0)
        self.progress.setFixedHeight(3)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(
            "QProgressBar{background:#1E2534;border:0;}"
            "QProgressBar::chunk{background:#7C5CFF;}")

        self.btnDone = QPushButton("完成")
        self.btnDone.setCursor(Qt.PointingHandCursor)
        self.btnDone.setStyleSheet(
            "QPushButton{background:#7C5CFF;color:#fff;border:0;border-radius:6px;"
            "padding:6px 18px;font-size:13px;}"
            "QPushButton:hover{background:#8E72FF;}")
        self.btnDone.clicked.connect(self._finish)

        self.btnCancel = QPushButton("取消")
        self.btnCancel.setCursor(Qt.PointingHandCursor)
        self.btnCancel.setStyleSheet(
            "QPushButton{background:transparent;color:#9AA5BA;border:0;border-radius:6px;"
            "padding:6px 12px;font-size:13px;}"
            "QPushButton:hover{background:#262F41;color:#EEF1F8;}")
        self.btnCancel.clicked.connect(self._cancel)

        self.btnRetry = QPushButton("重新加载")
        self.btnRetry.setCursor(Qt.PointingHandCursor)
        self.btnRetry.setStyleSheet(
            "QPushButton{background:#262F41;color:#EEF1F8;border:0;border-radius:6px;"
            "padding:6px 14px;font-size:13px;}"
            "QPushButton:hover{background:#2E3749;}")
        self.btnRetry.clicked.connect(lambda: self.view.reload())

        top = QHBoxLayout()
        top.setContentsMargins(16, 12, 16, 8)
        top.addWidget(self.title)
        top.addStretch(1)
        top.addWidget(self.status)
        top.addSpacing(12)
        top.addWidget(self.btnRetry)
        top.addWidget(self.btnCancel)
        top.addWidget(self.btnDone)

        # QWebEngineView 默认跑在 defaultProfile 上，必须显式换 page，
        # 否则页面写入的 Cookie 与下面监听的 store 不属于同一个 profile。
        self.page = QWebEnginePage(self.profile, self.window)
        self.view = QWebEngineView()
        self.view.setPage(self.page)
        self.view.setStyleSheet("background:#FFFFFF;")
        self.view.urlChanged.connect(self._on_url_changed)
        self.view.loadFinished.connect(self._on_load_finished)

        root = QVBoxLayout(self.window)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addLayout(top)
        root.addWidget(self.progress)
        root.addWidget(self.view, 1)

        log(f"打开登录窗口 site={site} profile={PROFILE_DIR}")
        log(f"Cookies 数据库: {_cookie_db_path() or '（尚未生成）'}")
        self.view.setUrl(QUrl(str(cfg["startUrl"])))
        # 载入已保存的 Cookie，重新打开窗口时也能识别既有登录态
        QTimer.singleShot(400, self.store.loadAllCookies)

    # ------------------------------------------------------------------
    def show(self) -> None:
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def clearCookies(self) -> None:
        try:
            self.store.deleteAllCookies()
        except Exception:  # noqa: BLE001
            pass

    def _on_cookie_added(self, cookie) -> None:
        item = _qcookie_to_dict(cookie)
        self._seen += 1
        domain = item["domain"].lstrip(".")
        if not any(domain == d or domain.endswith("." + d)
                   for d in self._cfg["cookieDomains"]):
            return
        self._cookies[(domain, item["path"], item["name"])] = item
        log(f"收到 Cookie: {item['domain']} {item['name']}")
        if not self._done:
            self._check_login()

    def _on_url_changed(self, url: QUrl) -> None:
        host = (url.host() or "").lower()
        if host in _UA_HOSTS or not host:
            return
        self.status.setText("已打开 " + host)
        # 离开 Google 账号页说明登录流程走完，稍后确认登录态
        if any(h in host for h in self._cfg["cookieDomains"]):
            log(f"已跳转到 {host}，准备确认登录态")
            QTimer.singleShot(1200, self.store.loadAllCookies)
            QTimer.singleShot(1800, self._check_login)

    def _on_load_finished(self, ok: bool) -> None:
        self.progress.setMaximum(1)
        self.progress.setValue(1)
        if not ok:
            self.status.setText("页面加载失败，可尝试重新加载")
            log("页面加载失败")
            return
        # 页面加载完再确认一次，避免漏掉跳转过程中写入的 Cookie
        QTimer.singleShot(600, self.store.loadAllCookies)
        QTimer.singleShot(900, self._check_login)

    def _check_login(self) -> None:
        """检测到登录凭据后不立刻导出。

        登录过程中 Cookie 是陆续写入的（SID、HSID、SSID、APISID…），
        拿到第一个就存会漏掉其余部分，导致 yt-dlp 仍然拿不到完整登录态。
        """
        if self._done or self._pending:
            return
        if not self._has_login_cookie():
            return
        self._pending = True
        self.status.setText("已检测到登录，正在收集凭据…")
        log("检测到登录凭据")
        QTimer.singleShot(1500, self._collect_and_export)

    def _has_login_cookie(self) -> bool:
        """是否已拿到登录凭据：先查内存，再兜底查磁盘。

        cookieAdded 在部分环境（无头模式、Cookie 后端未就绪）下完全不触发，
        只靠它会出现「明明登录成功却一直显示未登录」，所以必须带磁盘兜底。
        """
        want = self._cfg["loginCookies"]
        if any(i["name"] in want for i in self._cookies.values()):
            return True
        now = time.monotonic()
        if now - self._last_disk_check < 4.0:      # 限流，避免频繁读库
            return False
        self._last_disk_check = now
        try:
            names = {i["name"] for i in read_profile_cookies()}
        except Exception as exc:  # noqa: BLE001
            log(f"磁盘兜底异常: {type(exc).__name__}: {exc}")
            return False
        hit = any(n in names for n in want)
        log(f"磁盘兜底：{len(names)} 个 Cookie，登录凭据{'命中' if hit else '未命中'}")
        return hit

    def _collect_and_export(self) -> None:
        if self._done:
            return
        try:
            self.store.loadAllCookies()      # 补齐跳转过程中最后写入的 Cookie
        except Exception:  # noqa: BLE001
            pass
        QTimer.singleShot(500, self._export_and_finish)

    def _export_and_finish(self) -> None:
        if self._done:
            return
        self.status.setText("正在保存凭据…")
        try:
            count = self._export()
        except Exception as exc:  # noqa: BLE001
            self.status.setText(f"保存凭据失败：{exc}")
            log(f"保存凭据失败: {type(exc).__name__}: {exc}")
            self._manager.failed.emit(f"保存凭据失败：{exc}")
            return
        if count == 0:
            # 一条都没抓到：先不关窗口，让用户确认是否真的登录成功了
            self._pending = False
            self._last_disk_check = 0.0
            self.status.setText("未获取到登录凭据，请确认已登录后再点“完成”")
            log("导出 0 项，暂不保存")
            return
        self._done = True
        self.status.setText(f"登录成功，已保存 {count} 项凭据")
        log(f"保存成功，共 {count} 项")
        self._manager.onLoginFinished(self._site, count)
        QTimer.singleShot(1500, self._finish)

    def _collect_cookies(self) -> List[Dict[str, Any]]:
        """合并「信号收到的」与「磁盘读到的」凭据，按域过滤后去重。"""
        allowed = self._cfg["cookieDomains"]
        merged: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

        # 信号收到的更实时，优先采用
        for item in self._cookies.values():
            merged[(item["domain"].lstrip("."), item["path"], item["name"])] = item

        # 再用磁盘结果补齐：cookieAdded 未触发时这是唯一的来源
        try:
            for item in read_profile_cookies():
                domain = item["domain"].lstrip(".")
                if not any(domain == d or domain.endswith("." + d) for d in allowed):
                    continue
                merged.setdefault((domain, item["path"], item["name"]), item)
        except Exception as exc:  # noqa: BLE001
            log(f"导出时磁盘读取异常: {type(exc).__name__}: {exc}")

        return sorted(merged.values(),
                      key=lambda i: (i["domain"].lstrip("."), i["name"]))

    def _export(self) -> int:
        """把相关 Cookie 导出成 Netscape 文件，返回条数。"""
        cookies = self._collect_cookies()
        lines = ["# Netscape HTTP Cookie File",
                 "# 由 yt-dlp 图形用户界面生成（程序内登录）", ""]
        for item in cookies:
            lines.append(_netscape_line(item))
        target = self._manager.snapshot_path(self._site)
        COOKIE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".txt.tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        tmp.replace(target)
        log(f"已导出 {len(cookies)} 项凭据到 {target.name}")
        return len(cookies)

    def _finish(self) -> None:
        """点“完成”：无论是否自动检测到，都强制收集并保存一次。"""
        if not self._done:
            self._export_and_finish()
            return
        self._close()

    def _cancel(self) -> None:
        """放弃本次登录：不写出凭据，直接关闭。"""
        self._close()

    def _close(self) -> None:
        try:
            self.store.cookieAdded.disconnect(self._on_cookie_added)
        except Exception:  # noqa: BLE001
            pass
        self._manager._forget_window(self._site)
        self.window.close()
        self.window.deleteLater()
