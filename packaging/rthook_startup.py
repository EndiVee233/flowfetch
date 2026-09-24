"""PyInstaller 运行时钩子：在入口脚本之前安装启动异常兜底记录。

为什么不在 `app/main.py` 里做：入口脚本**自身的顶层 import** 失败时
（例如打包漏了某个 Qt 模块），`if __name__ == "__main__"` 那段根本不会执行，
异常只会写进 stderr —— 而 GUI 程序没有控制台，用户看到的就是「双击没反应」。

运行时钩子在入口脚本之前执行，因此能覆盖这一段。日志写到
`%APPDATA%\\YtDlpGui\\logs\\startup-crash.log`，失败则退回临时目录。
"""
import os
import sys
import tempfile
import traceback


def _log_path():
    try:
        base = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"),
                            "YtDlpGui", "logs")
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, "startup-crash.log")
    except Exception:
        return os.path.join(tempfile.gettempdir(), "YtDlpGui-startup-crash.log")


def _write(text):
    try:
        with open(_log_path(), "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
            fh.flush()
    except Exception:
        pass
    try:
        sys.stderr.write(text + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def _excepthook(exc_type, exc, tb):
    """记录未捕获异常；导入期失败也能留下完整堆栈。"""
    _write("".join(traceback.format_exception(exc_type, exc, tb)))
    sys.__excepthook__(exc_type, exc, tb)


def _thread_hook(args):
    _write("".join(traceback.format_exception(args.exc_type, args.exc_value,
                                              args.exc_traceback)))


sys.excepthook = _excepthook
try:
    import threading
    threading.excepthook = _thread_hook
except Exception:
    pass

_write(f"[runtime-hook] {sys.executable} | frozen={getattr(sys, 'frozen', False)}")


# 诊断开关：打包版里「下载引擎的文件都在却 import 不起来」时最难查，
# 设 LIUGUANG_DEBUG_IMPORT=1 就能把 yt_dlp 导入失败的完整堆栈写进日志。
if os.environ.get("LIUGUANG_DEBUG_IMPORT") == "1":
    import builtins

    _real_import = builtins.__import__
    _trace_left = [6]      # 只在登录最前面的几次失败，避免刷屏

    def _traced_import(name, *args, **kwargs):
        try:
            return _real_import(name, *args, **kwargs)
        except BaseException:
            if (name == "yt_dlp" or name.startswith("yt_dlp.")) and _trace_left[0] > 0:
                _trace_left[0] -= 1
                _write("[import-trace] 导入 " + name + " 失败：\n"
                       + traceback.format_exc())
            raise

    builtins.__import__ = _traced_import
    _write("[import-trace] 已开启 yt_dlp 导入追踪")
