import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import QtQuick.Shapes

Window {
    id: win

    width: 1180
    height: 760
    minimumWidth: 960
    minimumHeight: 640
    visible: true
    title: backend.appName
    color: Theme.bg0
    flags: Qt.Window | Qt.FramelessWindowHint

    property var cfg: backend.allSettings()
    property var stats: ({})
    property int page: 0
    /* 正在播放关闭动画：此时不再拦截关闭请求 */
    property bool closing: false
    readonly property bool maximized: visibility === Window.Maximized
    readonly property int sidebarWidth: (win.cfg.sidebar_compact === true) ? 70 : 214
    /* 侧边栏宽度走这个副本，折叠 / 展开时才有平滑过渡；
       动画关闭时时长为 0，等同于立即生效 */
    property int sidebarWidthAnim: sidebarWidth
    Behavior on sidebarWidthAnim {
        NumberAnimation { duration: Theme.durSlow; easing.type: Theme.ease }
    }

    // ── 主题 ────────────────────────────────────────────────
    function applyTheme() {
        var mode = cfg.theme || "dark"
        var isDark = (mode === "light") ? false : (mode === "system" ? backend.systemDark : true)
        Theme.dark = isDark
        Theme.accentKey = cfg.accent || "violet"
        Theme.fontScale = cfg.font_scale || 1.0
        Theme.animationsOn = cfg.animations !== false
        Theme.glassOn = cfg.mica !== false
        try { windowHelper.setDark(isDark) } catch (e) { }
    }

    function restoreGeometry() {
        if (cfg.window_width > 400) win.width = cfg.window_width
        if (cfg.window_height > 400) win.height = cfg.window_height
        if (cfg.window_x >= 0 && cfg.window_y >= 0) {
            win.x = cfg.window_x
            win.y = cfg.window_y
        }
        if (cfg.window_maximized === true) win.visibility = Window.Maximized
    }

    function saveGeometry() {
        if (!maximized) {
            backend.setSetting("window_width", Math.round(win.width))
            backend.setSetting("window_height", Math.round(win.height))
            backend.setSetting("window_x", Math.round(win.x))
            backend.setSetting("window_y", Math.round(win.y))
        }
        backend.setSetting("window_maximized", maximized)
    }

    function refreshStats() { win.stats = backend.stats() }

    /* 窗口级提示气泡：放在根部，避免被列表的 clip 裁掉 */
    function showTip(item, text) { globalTip.show(item, text) }
    function hideTip() { globalTip.hide() }

    Component.onCompleted: {
        applyTheme()
        restoreGeometry()
        refreshStats()
        win.page = backend.startPage
        backend.deps.checkUpdates(false)
        if (!backend.deps.ffmpegReady && backend.deps.ffmpegManaged && !backend.demoMode)
            firstRun.open()
        if (backend.demoOpenLogin) loginDemo.open()
        // 窗口入场：动画关闭时时长为 0，会立刻淡入，不会留下空白窗口
        introAnim.start()
    }

    /* 关闭窗口时先播放退场动画，播完再真正退出。
       动画关闭时时长为 0，等价于原来的立即关闭。 */
    onClosing: function (close) {
        if (win.closing || !Theme.animationsOn) {
            saveGeometry()
            close.accepted = true
            return
        }
        close.accepted = false
        win.closing = true
        saveGeometry()
        closeAnim.start()
    }

    ParallelAnimation {
        id: introAnim
        NumberAnimation { target: stage; property: "opacity"; from: 0; to: 1;
                          duration: Theme.durIntro; easing.type: Easing.OutCubic }
        NumberAnimation { target: stage; property: "scale"; from: 0.985; to: 1;
                          duration: Theme.durIntro; easing.type: Easing.OutCubic }
    }

    SequentialAnimation {
        id: closeAnim
        ParallelAnimation {
            NumberAnimation { target: stage; property: "opacity"; to: 0;
                              duration: Theme.durExit; easing.type: Theme.easeIn }
            NumberAnimation { target: stage; property: "scale"; to: 0.965;
                              duration: Theme.durExit; easing.type: Theme.easeIn }
            NumberAnimation { target: win; property: "opacity"; to: 0;
                              duration: Theme.durExit; easing.type: Theme.easeIn }
        }
        ScriptAction { script: backend.quit() }
    }

    BilibiliLogin { id: loginDemo }

    DepDialog {
        id: firstRun
        kind: "ffmpeg"
        mode: "ask"
        title: "需要安装 FFmpeg"
        message: "未检测到 FFmpeg 组件。合并音视频、转码、嵌入字幕与封面等操作都需要此组件。"
        question: "是否现在从 Internet 下载并安装？（约 40 MB）"
        detail: "选择“取消”后程序仍可正常下载视频，只是无法合并音视频或嵌入字幕。"
                + "<br/>你也可以稍后在 <a href=\"settings\" style=\"color:"
                + Theme.accentText + "\">设置 · 组件</a> 中手动安装。"
        detailClickable: true
        onDetailClicked: {
            firstRun.close()
            win.page = 3
        }
        onAccepted: {
            backend.deps.installFfmpeg()
            title = "正在下载 FFmpeg"
            message = "正在准备 FFmpeg。请不要关闭你的计算机。"
            detail = ""
            mode = "progress"
        }
        onRejected: backend.notify("info", "已跳过安装", "未安装 FFmpeg 时，部分功能将不可用。")
    }

    Connections {
        target: backend.deps
        function onFinished(kind, ok, message) {
            if (kind === "check") {
                if (backend.deps.updateAvailable) {
                    backend.notify("info", "有可用更新",
                                   backend.deps.updateSummary + " 可供更新，请在“设置 - 组件”中操作。")
                }
                return
            }
            firstRun.close()
        }
    }

    Connections {
        target: backend.settings
        function onChanged(key, value) {
            win.cfg = backend.allSettings()
            win.applyTheme()
        }
    }

    Timer {
        interval: 800
        running: true
        repeat: true
        onTriggered: win.refreshStats()
    }

    // 剪贴板监听
    Timer {
        interval: 1600
        running: win.cfg.clipboard_watch === true && win.active
        repeat: true
        onTriggered: {
            var u = backend.detectClipboardUrl(urlFieldUrl)
            if (u !== "") downloadPage.prefill(u)
        }
    }

    /* 启动后按需自动获取访客 Cookie（规避批量下载限流）。
       放在延迟任务里，避免拖慢窗口显示；已存在且未过期时不会真的执行。 */
    Timer {
        interval: 2500
        running: true
        repeat: false
        onTriggered: backend.autoFetchGuestCookie()
    }
    property string urlFieldUrl: ""

    /* ── 舞台 ──────────────────────────────────────────────
       窗口级动画（启动 / 关闭）都作用在这一层。
       缩放手柄、提示气泡等留在舞台外，避免被缩放影响。 */
    Item {
        id: stage
        objectName: "stage"
        anchors.fill: parent
        opacity: 0          // 由入场动画淡入

        // ── 背景 ────────────────────────────────────────────
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: Theme.dark ? "#141A2B" : "#FFFFFF" }
                GradientStop { position: 0.45; color: Theme.bg1 }
                GradientStop { position: 1.0; color: Theme.bg0 }
            }
        }

        /* 内容区中央的柔和环境光，避免出现对角明暗失衡 */
        Shape {
            readonly property real radius: 560
            width: radius * 2
            height: radius * 2
            x: (win.width + win.sidebarWidth) / 2 - radius
            y: win.height * 0.60 - radius
            opacity: Theme.glassOn ? (Theme.dark ? 0.20 : 0.14) : 0
            visible: opacity > 0.01
            Behavior on opacity { NumberAnimation { duration: Theme.durSlow } }

            ShapePath {
                strokeColor: "transparent"
                fillGradient: RadialGradient {
                    centerX: 560
                    centerY: 560
                    centerRadius: 560
                    focalX: 560
                    focalY: 560
                    GradientStop { position: 0.0; color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.40) }
                    GradientStop { position: 0.45; color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.12) }
                    GradientStop { position: 1.0; color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.0) }
                }
                startX: 560
                startY: 0
                PathAngleArc {
                    centerX: 560
                    centerY: 560
                    radiusX: 560
                    radiusY: 560
                    startAngle: 0
                    sweepAngle: 360
                }
            }
        }

        // ── 主体 ────────────────────────────────────────────
        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            TitleBar {
                id: titleBar
                Layout.fillWidth: true
                Layout.preferredHeight: 48
                title: backend.appName
                subtitle: "yt-dlp " + backend.deps.ytdlpVersion
                maximized: win.maximized
                onMinimizeRequested: win.showMinimized()
                onToggleMaximizeRequested: {
                    win.visibility = win.maximized ? Window.Windowed : Window.Maximized
                }
                onCloseRequested: win.close()
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: Theme.borderSoft
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                SideBar {
                    id: sidebar
                    Layout.fillHeight: true
                    Layout.preferredWidth: win.sidebarWidthAnim
                    compact: win.cfg.sidebar_compact === true
                    current: win.page
                    activeCount: win.stats.active || 0
                    pendingCount: win.stats.queued || 0
                    queueCount: win.stats.active || 0
                    speedText: win.stats.speedText || "空闲"
                    onNavigate: function (index) { win.page = index }
                }

                /* 页面切换：新页面轻微上浮淡入，让跳转不显得生硬。
                   动画关闭时不会触发，直接切换。 */
                StackLayout {
                    id: pageStack
                    objectName: "pageStack"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    currentIndex: win.page

                    property bool ready: false
                    transform: Translate { id: pageShift; y: 0 }

                    Component.onCompleted: pageStack.ready = true
                    onCurrentIndexChanged: {
                        if (pageStack.ready && Theme.animationsOn) pageIntro.restart()
                    }

                    DownloadPage {
                        id: downloadPage
                        onRequestQueue: win.page = 1
                    }
                    QueuePage { id: queuePage }
                    HistoryPage { id: historyPage }
                    SettingsPage { id: settingsPage }
                    AboutPage { id: aboutPage }
                }
            }
        }
    }

    ParallelAnimation {
        id: pageIntro
        NumberAnimation { target: pageStack; property: "opacity"; from: 0.25; to: 1;
                          duration: Theme.durBase; easing.type: Theme.ease }
        NumberAnimation { target: pageStack; property: "scale"; from: 0.986; to: 1;
                          duration: Theme.durBase; easing.type: Theme.ease }
        NumberAnimation { target: pageShift; property: "y"; from: 14; to: 0;
                          duration: Theme.durBase; easing.type: Theme.ease }
    }

    // ── 提示 ────────────────────────────────────────────────
    ToolTipBubble { id: globalTip }

    Toast {
        id: toast
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
    }

    Connections {
        target: backend.bilibili
        function onLoginSucceeded(name) {
            backend.notify("success", "哔哩哔哩登录成功", name + "，正在重新解析当前链接…")
            backend.reanalyze()
        }
    }

    Connections {
        target: backend
        function onToast(level, title, message) { toast.push(level, title, message) }
        function onTaskDone(taskId, title, state, reason) {
            if (!win.active || win.page !== 1) {
                if (state === "completed") toast.push("success", "下载完成", title)
                else if (state === "failed") toast.push("error", reason || "下载失败", title)
            }
        }
    }

    // ── 窗口缩放手柄 ────────────────────────────────────────
    MouseArea {
        width: 6; height: parent.height - 2
        anchors.left: parent.left; anchors.top: parent.top; anchors.topMargin: 1
        cursorShape: Qt.SizeHorCursor
        enabled: !win.maximized
        onPressed: win.startSystemResize(Qt.LeftEdge)
    }
    MouseArea {
        width: 6; height: parent.height - 2
        anchors.right: parent.right; anchors.top: parent.top; anchors.topMargin: 1
        cursorShape: Qt.SizeHorCursor
        enabled: !win.maximized
        onPressed: win.startSystemResize(Qt.RightEdge)
    }
    MouseArea {
        height: 5; width: parent.width - 2
        anchors.top: parent.top; anchors.left: parent.left; anchors.leftMargin: 1
        cursorShape: Qt.SizeVerCursor
        enabled: !win.maximized
        onPressed: win.startSystemResize(Qt.TopEdge)
    }
    MouseArea {
        height: 5; width: parent.width - 2
        anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.leftMargin: 1
        cursorShape: Qt.SizeVerCursor
        enabled: !win.maximized
        onPressed: win.startSystemResize(Qt.BottomEdge)
    }
    MouseArea {
        width: 12; height: 12
        anchors.left: parent.left; anchors.top: parent.top
        cursorShape: Qt.SizeFDiagCursor
        enabled: !win.maximized
        onPressed: win.startSystemResize(Qt.LeftEdge | Qt.TopEdge)
    }
    MouseArea {
        width: 12; height: 12
        anchors.right: parent.right; anchors.top: parent.top
        cursorShape: Qt.SizeBDiagCursor
        enabled: !win.maximized
        onPressed: win.startSystemResize(Qt.RightEdge | Qt.TopEdge)
    }
    MouseArea {
        width: 12; height: 12
        anchors.left: parent.left; anchors.bottom: parent.bottom
        cursorShape: Qt.SizeBDiagCursor
        enabled: !win.maximized
        onPressed: win.startSystemResize(Qt.LeftEdge | Qt.BottomEdge)
    }
    MouseArea {
        width: 14; height: 14
        anchors.right: parent.right; anchors.bottom: parent.bottom
        cursorShape: Qt.SizeFDiagCursor
        enabled: !win.maximized
        onPressed: win.startSystemResize(Qt.RightEdge | Qt.BottomEdge)
    }

    // ── 快捷键 ──────────────────────────────────────────────
    Shortcut {
        sequences: ["Ctrl+V"]
        onActivated: {
            var t = backend.pasteFromClipboard()
            if (t !== "") downloadPage.prefill(t)
        }
    }
    Shortcut {
        sequence: "Ctrl+1"
        onActivated: win.page = 0
    }
    Shortcut {
        sequence: "Ctrl+2"
        onActivated: win.page = 1
    }
    Shortcut {
        sequence: "Ctrl+3"
        onActivated: win.page = 2
    }
    Shortcut {
        sequence: "Ctrl+4"
        onActivated: win.page = 3
    }
    Shortcut {
        sequence: "Ctrl+5"
        onActivated: win.page = 4
    }
    Shortcut {
        sequence: "Ctrl+O"
        onActivated: backend.openFolder(win.cfg.output_dir)
    }
    Shortcut {
        sequence: "F5"
        onActivated: backend.reanalyze()
    }
}
