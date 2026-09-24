# 打包说明（Windows 安装包）

一条命令出安装包：

```powershell
C:\Python314\python.exe packaging\build.py
```

产物：

| 路径 | 说明 | 体积 |
| --- | --- | --- |
| `packaging\dist\YtDlpGui\` | 绿色版发行目录，双击 `YtDlpGui.exe` 即可用 | 约 438 MB |
| `packaging\output\YtDlpGui-1.0.0-setup.exe` | 安装向导（开始菜单/桌面快捷方式/卸载项） | 约 117 MB |

## 打包内容的取舍

- **版本号只有一个来源**：`app/__init__.py` 的 `__version__`。
  `build.py` 读出后通过 ISCC 的 `/DMyAppVersion=` 传给 `installer.iss`
  （`.iss` 里有兜底默认值，方便单独手编）。
  不要在 `.iss` 里试图解析 Python 源码：ISPP 只有 `GetStringFileInfo`
  （读 PE 版本资源），**没有读文本文件的函数**，`GetVersionNumbersString`
  也读不了 `.py`（实测取到空值，会把安装包名变成 `YtDlpGui--setup.exe`）。

- **不内置 yt-dlp**：它更新频繁，内置等于把版本冻结在打包那一刻。
  程序本来就支持把官方 wheel 解压到 `%APPDATA%\YtDlpGui\lib`，
  打包版沿用这条路 —— 首次启动自动联网获取（约 3 MB，几秒钟），
  之后可在「设置 → 组件」里随时更新。自举逻辑见 `app/core/ytdlp.py`。
- **不内置 FFmpeg**：同上，交给「设置 → 组件」下载，或让用户指定已有目录。
- **保留 QtWebEngine**：YouTube 的「程序内登录」需要它（约 195 MB，是体积大头）。
- **one-folder 而非 one-file**：省去每次启动解压几百 MB，QtWebEngine 也更稳定。

## 关键坑（改打包配置前先读）

1. **不要随便往 `excludes` 里加 Qt 模块**。排掉一个模块，PyInstaller 就不再收集
   它对应的 `Qt6Xxx.dll`，而**别的保留组件可能依赖那个 DLL**。踩过一次：
   排掉 `QtSql` 后启动即报
   `libshiboken: could not import module 'PySide6.QtQuick'`
   —— 真因是 QML 引擎的 LocalStorage 插件依赖 `Qt6Sql.dll`。
   加任何 exclude 之前，先用 `dumpbin /DEPENDENTS` 核对依赖闭合。
2. **yt-dlp 用到的标准库要显式列进 `hiddenimports`**。因为 yt-dlp 本身被排除，
   PyInstaller 只按我们自己的代码收集依赖，而 yt-dlp 运行时会用到一堆我们从不
   import 的模块（首次实测卡在 `No module named 'getpass'`）。
3. **不要把 `QT_QPA_PLATFORM` 设成空字符串**做「真窗口」测试：Qt 会把 `""`
   当成非法平台名，窗口根本不会创建（排查时被这个假象误导过）。
4. **入口脚本里不能用相对导入**（`from .core import x`）。冻结后入口是以
   `__main__` 运行的顶层模块，会报 `attempted relative import with no known
   parent package`，而且**错误被吞掉后表现为「窗口外观失效」**这种软故障。
5. **跨线程信号投递要等事件队列**。首次启动自举用了 `QThread` + `done` 信号，
   工作线程在 `isRunning()` 变 False 的同一瞬间才 emit，主线程直接读结果会拿到
   空值 —— 实测误报「获取失败」而其实已经装好了。收尾时必须
   `fetcher.wait()` 之后再 `processEvents()` 数次。

## 打包后的自检

`packaging\probe-timeline.ps1` 会启动发行版并逐秒记录窗口出现与进程存活，
同时打印 `bootstrap.log` / `startup-crash.log`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\probe-timeline.ps1 -Fresh -Seconds 25
```

期望结果：第 1–4 秒是「首次启动准备」进度框（下载引擎），第 5 秒起出现主窗口
`yt-dlp 图形用户界面 - …`，之后一直存活；`bootstrap.log` 里是
「未找到引擎 → 已下载 → 安装完成 → 获取成功」。

> 注意：脚本以 ASCII 写就。Windows PowerShell 5.1 在文件没有 UTF-8 BOM 时按
> ANSI 读取 `.ps1`，中文会被拆成语法错误。

## 运行时诊断日志（给用户排障用）

| 文件 | 内容 |
| --- | --- |
| `%APPDATA%\YtDlpGui\logs\bootstrap.log` | 首次启动获取 yt-dlp 的全过程 |
| `%APPDATA%\YtDlpGui\logs\startup-crash.log` | 启动期异常完整堆栈；设 `LIUGUANG_DEBUG_IMPORT=1` 还会记录 yt_dlp 导入失败详情 |
| `%APPDATA%\YtDlpGui\logs\weblogin.log` | 程序内登录 / 访客 Cookie |

设备环境变量：`LIUGUANG_SKIP_YTDLP_BOOTSTRAP=1` 可跳过首次启动的引擎获取。

## 已知限制

- 安装包**未做代码签名**，SmartScreen 首次运行可能提示「未知发布者」。
- 尚未在**全新 Windows 环境**上验证过安装流程（开发机上直接编译 + 跑发行版通过）；
  安装向导本身（Inno Setup 7.1.0，中文）已成功编译，但未做静默安装实测。
- `packaging\dist\` 里的发行目录只有 `.exe` 与 `_internal\`，
  直接拷走整个 `YtDlpGui` 文件夹即为绿色版。
