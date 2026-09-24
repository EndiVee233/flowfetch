import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

/* 设置页 */
Item {
    id: root

    function idx(arr, v) {
        for (var i = 0; i < arr.length; i++) if (arr[i] === v) return i
        return 0
    }

    /* 程序内登录（YouTube 等）的当前状态 */
    property var ytLogin: backend.weblogin.siteStatus("youtube")

    /* 自动获取的访客 Cookie 状态（状态变化时由后端信号刷新） */
    property var guestCookie: backend.guestCookieStatus()

    Connections {
        target: backend.weblogin
        function onChanged() { root.ytLogin = backend.weblogin.siteStatus("youtube") }
    }

    Connections {
        target: backend
        function onAnalyzeStateChanged() { root.guestCookie = backend.guestCookieStatus() }
    }

    readonly property var themes: [
        { key: "dark",   label: "深色" },
        { key: "light",  label: "浅色" },
        { key: "system", label: "跟随系统" }
    ]
    readonly property var cookieBrowsers: ["", "edge", "chrome", "firefox", "brave", "opera", "vivaldi", "chromium"]
    readonly property var cookieBrowserNames: ["不使用", "Microsoft Edge", "Google Chrome", "Mozilla Firefox",
                                               "Brave", "Opera", "Vivaldi", "Chromium"]
    readonly property var containers: ["mp4", "mkv", "webm", "原始"]
    readonly property var subFormats: ["原始", "srt", "vtt", "ass", "lrc"]
    readonly property var subFormatNames: ["保持网站格式", "SRT（最通用）", "VTT", "ASS（带样式）", "LRC（歌词）"]
    readonly property var containerNames: ["MP4（兼容性最好）", "MKV（支持多音轨）", "WebM", "保持原始格式"]

    Component.onCompleted: {
        backend.deps.checkUpdates(false)
        if (backend.demoScrollY > 0) flick.contentY = backend.demoScrollY
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.sp6
        spacing: Theme.sp3

        RowLayout {
            Layout.fillWidth: true
            Column {
                spacing: 3
                Text {
                    text: "设置"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsDisplay
                    font.weight: Font.Bold
                }
                Text {
                    text: "所做的更改会立即生效并自动保存。"
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsLabel
                }
            }
            Item { Layout.fillWidth: true }
            AppButton {
                Layout.alignment: Qt.AlignVCenter
                text: "打开配置文件夹"
                iconName: "folder"
                variant: "secondary"
                small: true
                onClicked: backend.openFolder(backend.dataDir)
            }
            AppButton {
                Layout.alignment: Qt.AlignVCenter
                text: "还原默认设置"
                iconName: "refresh"
                variant: "dangerGhost"
                small: true
                onClicked: confirmReset.open()
            }
        }

        Flickable {
            id: flick
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width
            contentHeight: col.implicitHeight + 40
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: AppScrollBar { }

            ColumnLayout {
                id: col
                width: flick.width
                spacing: Theme.sp5

                SectionCard {
                    title: "常规"
                    iconName: "folder"

                    SettingRow {
                        label: "保存位置"
                        hint: win.cfg.output_dir
                        AppButton {
                            text: "更改…"
                            iconName: "folder"
                            variant: "secondary"
                            small: true
                            onClicked: {
                                var p = backend.chooseDirectoryDialog()
                                if (p !== "") backend.setSetting("output_dir", p)
                            }
                        }
                        AppButton {
                            text: "打开"
                            variant: "ghost"
                            small: true
                            onClicked: backend.openFolder(win.cfg.output_dir)
                        }
                    }

                    SettingRow {
                        label: "文件名模板"
                        hint: "可用变量：%(title)s（标题）、%(id)s（标识符）、%(uploader)s（作者）、%(ext)s（扩展名）"
                        AppTextField {
                            Layout.preferredWidth: 300
                            monospace: true
                            text: win.cfg.filename_template
                            onEditingFinished: backend.setSetting("filename_template", text)
                        }
                    }

                    SettingRow {
                        label: "同时下载的任务数"
                        hint: "数值过大可能被站点限制速度"
                        AppSlider {
                            Layout.preferredWidth: 220
                            from: 1
                            to: 8
                            stepSize: 1
                            value: win.cfg.max_concurrent
                            onMoved: backend.setSetting("max_concurrent", value)
                        }
                        Text {
                            Layout.preferredWidth: 72
                            text: win.cfg.max_concurrent + " 个"
                            color: Theme.textDim
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsLabel
                            horizontalAlignment: Text.AlignRight
                        }
                    }

                    SettingRow {
                        label: "每个任务的分片数"
                        hint: "对支持分片下载的站点可提高速度"
                        AppSlider {
                            Layout.preferredWidth: 220
                            from: 1
                            to: 16
                            stepSize: 1
                            value: win.cfg.concurrent_fragments
                            onMoved: backend.setSetting("concurrent_fragments", value)
                        }
                        Text {
                            Layout.preferredWidth: 72
                            text: win.cfg.concurrent_fragments + " 路"
                            color: Theme.textDim
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsLabel
                            horizontalAlignment: Text.AlignRight
                        }
                    }

                    SettingRow {
                        label: "失败后的重试次数"
                        AppSlider {
                            Layout.preferredWidth: 220
                            from: 0
                            to: 20
                            stepSize: 1
                            value: win.cfg.retries
                            onMoved: backend.setSetting("retries", value)
                        }
                        Text {
                            Layout.preferredWidth: 72
                            text: win.cfg.retries + " 次"
                            color: Theme.textDim
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsLabel
                            horizontalAlignment: Text.AlignRight
                        }
                    }

                    SettingRow {
                        label: "下载完成后打开文件夹"
                        AppSwitch {
                            checked: win.cfg.open_folder_when_done === true
                            onToggled: backend.setSetting("open_folder_when_done", value)
                        }
                    }
                }

                SectionCard {
                    title: "外观"
                    iconName: "star"

                    SettingRow {
                        label: "主题"
                        Row {
                            spacing: Theme.sp2
                            Repeater {
                                model: root.themes
                                delegate: Chip {
                                    required property var modelData
                                    text: modelData.label
                                    compact: true
                                    selected: win.cfg.theme === modelData.key
                                    onClicked: backend.setSetting("theme", modelData.key)
                                }
                            }
                        }
                    }

                    SettingRow {
                        label: "强调色"
                        Row {
                            spacing: 8
                            Repeater {
                                model: Theme.accentKeys
                                delegate: Rectangle {
                                    required property string modelData
                                    width: 26
                                    height: 26
                                    radius: 13
                                    color: Theme.accentColor(modelData)
                                    border.width: win.cfg.accent === modelData ? 2 : 0
                                    border.color: Theme.text
                                    scale: swatchMouse.containsMouse ? 1.12 : 1.0
                                    Behavior on scale { NumberAnimation { duration: Theme.durFast } }
                                    AppIcon {
                                        anchors.centerIn: parent
                                        visible: win.cfg.accent === modelData
                                        name: "check"
                                        size: 12
                                        iconColor: "#FFFFFF"
                                    }
                                    MouseArea {
                                        id: swatchMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: backend.setSetting("accent", modelData)
                                    }
                                }
                            }
                        }
                    }

                    SettingRow {
                        label: "界面缩放"
                        AppSlider {
                            Layout.preferredWidth: 220
                            from: 0.85
                            to: 1.30
                            stepSize: 0.05
                            value: win.cfg.font_scale
                            onMoved: backend.setSetting("font_scale", Math.round(value * 100) / 100)
                        }
                        Text {
                            Layout.preferredWidth: 72
                            text: Math.round(win.cfg.font_scale * 100) + "%"
                            color: Theme.textDim
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsLabel
                            horizontalAlignment: Text.AlignRight
                        }
                    }

                    SettingRow {
                        label: "启用界面动画"
                        AppSwitch {
                            checked: win.cfg.animations === true
                            onToggled: backend.setSetting("animations", value)
                        }
                    }

                    SettingRow {
                        label: "启用背景光效"
                        AppSwitch {
                            checked: win.cfg.mica === true
                            onToggled: backend.setSetting("mica", value)
                        }
                    }

                    SettingRow {
                        label: "使用紧凑侧边栏"
                        hint: "仅显示图标"
                        AppSwitch {
                            checked: win.cfg.sidebar_compact === true
                            onToggled: backend.setSetting("sidebar_compact", value)
                        }
                    }
                }

                SectionCard {
                    title: "组件"
                    iconName: "devices"

                    SettingRow {
                        label: "yt-dlp 引擎"
                        hint: backend.deps.ytdlpStatusText + " · 来源：" + backend.deps.ytdlpSourceText
                        AppButton {
                            text: "检查更新"
                            iconName: "search"
                            variant: "secondary"
                            small: true
                            onClicked: {
                                backend.deps.checkUpdates(true)
                                backend.notify("info", "正在检查更新…", "请稍候。")
                            }
                        }
                        AppButton {
                            text: "更新"
                            iconName: "download"
                            small: true
                            visible: backend.deps.ytdlpOutdated
                            onClicked: depDialog.openAsk("ytdlp")
                        }
                    }

                    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borderSoft }

                    SettingRow {
                        label: "FFmpeg 来源"
                        hint: "合并音视频、转码、嵌入字幕与封面都需要 FFmpeg"
                        Row {
                            spacing: Theme.sp2
                            Chip {
                                text: "由本程序下载并管理"
                                compact: true
                                selected: backend.deps.ffmpegManaged
                                onClicked: backend.deps.setMode("managed")
                            }
                            Chip {
                                text: "使用我已安装的"
                                compact: true
                                selected: !backend.deps.ffmpegManaged
                                onClicked: backend.deps.setMode("custom")
                            }
                        }
                    }

                    // —— 模式一：由本程序管理 ——
                    SettingRow {
                        visible: backend.deps.ffmpegManaged
                        label: "FFmpeg 组件"
                        hint: backend.deps.ffmpegReady
                              ? (backend.deps.ffmpegVersion + "（" + backend.deps.ffmpegSource + "）")
                              : "尚未安装。选择“立即下载”后，本程序会负责安装与后续更新。"
                        AppButton {
                            text: backend.deps.ffmpegReady ? "重新下载" : "立即下载"
                            iconName: "download"
                            variant: backend.deps.ffmpegReady ? "secondary" : "primary"
                            small: true
                            onClicked: depDialog.openAsk("ffmpeg")
                        }
                        AppButton {
                            visible: backend.deps.ffmpegReady
                            text: "打开组件文件夹"
                            iconName: "folder"
                            variant: "ghost"
                            small: true
                            onClicked: backend.deps.openBinFolder()
                        }
                    }

                    // —— 模式二：使用用户已安装的 FFmpeg ——
                    SettingRow {
                        visible: !backend.deps.ffmpegManaged
                        label: "FFmpeg 所在目录"
                        hint: "选择包含 ffmpeg.exe 的文件夹；也可以直接填写 ffmpeg.exe 的完整路径"
                        AppTextField {
                            Layout.preferredWidth: 300
                            placeholderText: "例如 C:\\ffmpeg\\bin"
                            text: win.cfg.ffmpeg_dir
                            onEditingFinished: {
                                backend.setSetting("ffmpeg_dir", text)
                                backend.deps.setCustomDir(text)
                            }
                        }
                        AppButton {
                            text: "浏览…"
                            variant: "secondary"
                            small: true
                            onClicked: {
                                var p = backend.pickFile("ffmpeg")
                                if (p !== "") {
                                    backend.setSetting("ffmpeg_dir", p)
                                    backend.deps.setCustomDir(p)
                                }
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        visible: !backend.deps.ffmpegManaged
                        spacing: Theme.sp2
                        AppIcon {
                            name: backend.deps.ffmpegCustomValid ? "completed" : "warning"
                            size: 14
                            iconColor: backend.deps.ffmpegCustomValid ? Theme.success : Theme.danger
                        }
                        Text {
                            Layout.fillWidth: true
                            text: backend.deps.ffmpegCustomStatus
                            color: backend.deps.ffmpegCustomValid ? Theme.success : Theme.danger
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsSmall
                            wrapMode: Text.Wrap
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        visible: backend.deps.ffmpegWarning !== ""
                        spacing: Theme.sp2
                        AppIcon { name: "warning"; size: 14; iconColor: Theme.warning }
                        Text {
                            Layout.fillWidth: true
                            text: backend.deps.ffmpegWarning
                            color: Theme.warning
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsSmall
                            wrapMode: Text.Wrap
                        }
                    }
                }

                SectionCard {
                    title: "哔哩哔哩账号"
                    iconName: "shield"

                    SettingRow {
                        label: backend.bilibili.loggedIn ? "已登录" : "未登录"
                        hint: backend.bilibili.loggedIn
                              ? (backend.bilibili.statusText
                                 + "。下载时会自动携带登录凭据，可解析到更高画质。")
                              : "未登录时只能解析到 1080P 及以下的普通画质。"
                                + "登录后可获取 1080P 高码率、4K、8K、HDR 与 60fps 内容。"
                        AppButton {
                            visible: !backend.bilibili.loggedIn
                            text: "扫码登录"
                            iconName: "shield"
                            small: true
                            onClicked: biliLogin.open()
                        }
                        AppButton {
                            visible: backend.bilibili.loggedIn
                            text: "刷新状态"
                            iconName: "refresh"
                            variant: "secondary"
                            small: true
                            onClicked: backend.bilibili.refresh()
                        }
                        AppButton {
                            visible: backend.bilibili.loggedIn
                            text: "退出登录"
                            variant: "dangerGhost"
                            small: true
                            onClicked: confirmLogout.open()
                        }
                    }
                }

                SectionCard {
                    title: "哔哩哔哩下载"
                    iconName: "download"
                    collapsible: true
                    expanded: false

                    Text {
                        Layout.fillWidth: true
                        text: "以下设置只对哔哩哔哩链接生效，不会影响其它站点。"
                        color: Theme.textMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fsSmall
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.sp2
                        Text {
                            text: "主要内容"
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsBody
                            font.weight: Font.DemiBold
                        }
                        Row {
                            spacing: Theme.sp6
                            AppCheckBox {
                                text: "下载视频"
                                checked: win.cfg.bili_download_video === true
                                onToggled: backend.setSetting("bili_download_video", value)
                            }
                            AppCheckBox {
                                text: "下载音频"
                                checked: win.cfg.bili_download_audio === true
                                onToggled: backend.setSetting("bili_download_audio", value)
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.sp2
                        Text {
                            text: "视频处理"
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsBody
                            font.weight: Font.DemiBold
                        }
                        Row {
                            spacing: Theme.sp6
                            AppCheckBox {
                                text: "自动合并"
                                checked: win.cfg.bili_auto_merge === true
                                onToggled: backend.setSetting("bili_auto_merge", value)
                            }
                            AppCheckBox {
                                text: "标记章节"
                                checked: win.cfg.bili_mark_chapters === true
                                onToggled: backend.setSetting("bili_mark_chapters", value)
                            }
                            AppCheckBox {
                                text: "标记广告"
                                checked: win.cfg.bili_mark_ads === true
                                onToggled: backend.setSetting("bili_mark_ads", value)
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.sp2
                        Text {
                            text: "下载弹幕"
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsBody
                            font.weight: Font.DemiBold
                        }
                        Row {
                            spacing: Theme.sp6
                            AppCheckBox {
                                text: "xml 弹幕"
                                checked: win.cfg.bili_danmaku_xml === true
                                onToggled: backend.setSetting("bili_danmaku_xml", value)
                            }
                            AppCheckBox {
                                text: "ass 弹幕"
                                checked: win.cfg.bili_danmaku_ass === true
                                onToggled: backend.setSetting("bili_danmaku_ass", value)
                            }
                            AppCheckBox {
                                text: "json 弹幕"
                                checked: win.cfg.bili_danmaku_json === true
                                onToggled: backend.setSetting("bili_danmaku_json", value)
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: "yt-dlp 本身不提供弹幕下载，这里由程序直接调用哔哩哔哩接口获取，"
                                  + "与视频文件放在同一目录（文件名形如 视频.danmaku.ass）。"
                            color: Theme.textMuted
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsTiny
                            wrapMode: Text.Wrap
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.sp2
                        Text {
                            text: "其他内容"
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsBody
                            font.weight: Font.DemiBold
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.sp4
                            AppCheckBox {
                                text: "下载字幕"
                                checked: win.cfg.bili_write_subs === true
                                onToggled: backend.setSetting("bili_write_subs", value)
                            }
                            AppTextField {
                                Layout.fillWidth: true
                                placeholderText: "默认字幕语言（逗号分隔，留空=全部），如 zh-Hans,en"
                                text: win.cfg.bili_sub_langs || ""
                                onTextChanged: backend.setSetting("bili_sub_langs", text)
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: Theme.sp2
                            Text {
                                text: "封面分辨率"
                                color: Theme.textMuted
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fsSmall
                            }
                            Flow {
                                Layout.fillWidth: true
                                spacing: Theme.sp2
                                Chip {
                                    text: "不下载"
                                    compact: true
                                    selected: (win.cfg.bili_cover_mode || "") === "none"
                                    onClicked: backend.setSetting("bili_cover_mode", "none")
                                }
                                Chip {
                                    text: "原图"
                                    compact: true
                                    selected: (win.cfg.bili_cover_mode || "") === "original"
                                    onClicked: backend.setSetting("bili_cover_mode", "original")
                                }
                                Chip {
                                    text: "640 宽"
                                    compact: true
                                    selected: (win.cfg.bili_cover_mode || "") === "640"
                                    onClicked: backend.setSetting("bili_cover_mode", "640")
                                }
                                Chip {
                                    text: "320 宽"
                                    compact: true
                                    selected: (win.cfg.bili_cover_mode || "") === "320"
                                    onClicked: backend.setSetting("bili_cover_mode", "320")
                                }
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.sp2
                        Text {
                            text: "元数据"
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsBody
                            font.weight: Font.DemiBold
                        }
                        Row {
                            spacing: Theme.sp6
                            AppCheckBox { text: "nfo 刮削"; enabled: false; checked: false }
                            AppCheckBox {
                                text: "json 刮削"
                                checked: win.cfg.bili_write_json === true
                                onToggled: backend.setSetting("bili_write_json", value)
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: Theme.sp2
                        spacing: Theme.sp5

                        PriorityList {
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignTop
                            title: "画质优先级"
                            hint: "按顺序尝试，使用第一个可用的画质。"
                            table: backend.biliQualityTable()
                            order: win.cfg.bili_quality_order
                            settingsKey: "bili_quality_order"
                            onMove: function (index, delta) {
                                backend.biliMovePriority("bili_quality_order", index, delta)
                            }
                            onReset: backend.biliResetPriority("bili_quality_order")
                        }

                        PriorityList {
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignTop
                            title: "音质优先级"
                            hint: "合并音视频或提取音频时使用。"
                            table: backend.biliAudioTable()
                            order: win.cfg.bili_audio_order
                            settingsKey: "bili_audio_order"
                            onMove: function (index, delta) {
                                backend.biliMovePriority("bili_audio_order", index, delta)
                            }
                            onReset: backend.biliResetPriority("bili_audio_order")
                        }

                        PriorityList {
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignTop
                            title: "编码优先级"
                            hint: "AV1 体积最小，AVC 兼容性最好。"
                            table: backend.biliCodecTable()
                            order: win.cfg.bili_codec_order
                            settingsKey: "bili_codec_order"
                            onMove: function (index, delta) {
                                backend.biliMovePriority("bili_codec_order", index, delta)
                            }
                            onReset: backend.biliResetPriority("bili_codec_order")
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.sp2
                        Text {
                            text: "文件已存在时"
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsBody
                            font.weight: Font.DemiBold
                        }
                        Row {
                            spacing: Theme.sp2
                            Chip {
                                text: "覆盖旧文件"
                                compact: true
                                selected: (win.cfg.bili_existing || "overwrite") === "overwrite"
                                onClicked: backend.setSetting("bili_existing", "overwrite")
                            }
                            Chip {
                                text: "跳过下载"
                                compact: true
                                selected: win.cfg.bili_existing === "skip"
                                onClicked: backend.setSetting("bili_existing", "skip")
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.sp2
                        Text {
                            text: "其他"
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsBody
                            font.weight: Font.DemiBold
                        }
                        AppCheckBox {
                            text: "创建下载任务后自动开始"
                            checked: win.cfg.bili_auto_start === true
                            onToggled: backend.setSetting("bili_auto_start", value)
                        }
                    }
                }

                SectionCard {
                    title: "访客 Cookie"
                    iconName: "bolt"

                    SettingRow {
                        label: root.guestCookie.busy === true ? "正在获取…"
                             : (root.guestCookie.available ? "已获取" : "尚未获取")
                        hint: root.guestCookie.available
                              ? ("已保存 " + root.guestCookie.count + " 项访客凭据。"
                                 + "下载时会自动携带，可降低短时间批量下载被限流的概率（无需登录）。")
                              : "短时间连续下载多个视频时容易被限流。"
                                + "获取一份访客会话即可显著缓解，程序会自动用本机浏览器获取，不含任何登录信息。"
                        AppButton {
                            text: root.guestCookie.busy === true ? "获取中…" : "立即获取"
                            iconName: "refresh"
                            small: true
                            busy: root.guestCookie.busy === true
                            enabled: root.guestCookie.busy !== true
                            onClicked: backend.refreshGuestCookies()
                        }
                    }

                    SettingRow {
                        label: "自动获取访客 Cookie"
                        hint: root.guestCookie.hasBrowser
                              ? "启动时若缺失或超过 7 天会自动重新获取"
                              : "未检测到 Chrome 或 Edge，需手动指定 Cookies 文件"
                        AppSwitch {
                            checked: win.cfg.guest_cookie_enabled !== false
                            onToggled: backend.setSetting("guest_cookie_enabled", value)
                        }
                    }
                }

                SectionCard {
                    title: "YouTube账号"
                    iconName: "shield"

                    SettingRow {
                        label: root.ytLogin.loggedIn === true ? "已登录" : "未登录"
                        hint: root.ytLogin.loggedIn === true
                              ? (root.ytLogin.statusText
                                 + "。下载时会自动携带登录凭据，会员与年龄限制内容也能正常下载。")
                              : "Chrome 与 Edge 新版已对 Cookie 加密，本程序无法从浏览器读取。"
                                + "在此登录一次即可长期有效，无需反复提取。"
                        AppButton {
                            visible: root.ytLogin.loggedIn !== true
                            text: "登录"
                            iconName: "globe"
                            small: true
                            onClicked: backend.weblogin.startLogin("youtube")
                        }
                        AppButton {
                            visible: root.ytLogin.loggedIn === true
                            text: "重新登录"
                            iconName: "refresh"
                            variant: "secondary"
                            small: true
                            onClicked: backend.weblogin.startLogin("youtube")
                        }
                        AppButton {
                            visible: root.ytLogin.loggedIn === true
                            text: "退出登录"
                            variant: "dangerGhost"
                            small: true
                            onClicked: backend.weblogin.logout("youtube")
                        }
                    }

                    SettingRow {
                        label: "使用程序内登录的凭据"
                        hint: "关闭后改用手写的 Cookies 文件或浏览器读取"
                        AppSwitch {
                            checked: win.cfg.weblogin_enabled !== false
                            onToggled: backend.setSetting("weblogin_enabled", value)
                        }
                    }

                    SettingRow {
                        label: "诊断日志"
                        hint: "登录异常时可在该目录查看详细记录"
                        AppButton {
                            text: "打开日志目录"
                            iconName: "folder"
                            variant: "secondary"
                            small: true
                            onClicked: backend.weblogin.openLogFolder()
                        }
                    }
                }

                SectionCard {
                    title: "YouTube 下载"
                    iconName: "download"
                    collapsible: true
                    expanded: false

                    Text {
                        Layout.fillWidth: true
                        text: "画质 / 音质 / 编码优先级只对 YouTube 链接生效；"
                              + "下面的字幕、封面等选项对所有站点通用。"
                        color: Theme.textMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fsSmall
                        wrapMode: Text.Wrap
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Theme.sp2
                        Text {
                            text: "主要设置"
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsBody
                            font.weight: Font.DemiBold
                        }
                        AppCheckBox {
                            text: "按下面的优先级挑选格式"
                            checked: win.cfg.yt_use_custom_quality === true
                            onToggled: backend.setSetting("yt_use_custom_quality", value)
                        }
                        AppCheckBox {
                            text: "优先选择 60 fps"
                            checked: win.cfg.prefer_60fps === true
                            onToggled: backend.setSetting("prefer_60fps", value)
                        }
                        Text {
                            Layout.fillWidth: true
                            text: "关闭优先级后交回 yt-dlp 自动选择最佳画质与音质；"
                                  + "在下载页手动选了具体格式时，始终以你的选择为准。"
                                  + "同一分辨率常有 30 / 60 fps 两种，勾选高帧率后优先取 60 fps。"
                            color: Theme.textMuted
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsTiny
                            wrapMode: Text.Wrap
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: Theme.sp2
                        spacing: Theme.sp5

                        PriorityList {
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignTop
                            title: "画质优先级"
                            hint: "按顺序尝试，使用第一个可用的分辨率。"
                            table: backend.ytQualityTable()
                            order: win.cfg.yt_quality_order
                            settingsKey: "yt_quality_order"
                            onMove: function (index, delta) {
                                backend.ytMovePriority("yt_quality_order", index, delta)
                            }
                            onReset: backend.ytResetPriority("yt_quality_order")
                        }

                        PriorityList {
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignTop
                            title: "音质优先级"
                            hint: "决定合并或提取音频时优先取哪条音轨。"
                            table: backend.ytAudioTable()
                            order: win.cfg.yt_audio_order
                            settingsKey: "yt_audio_order"
                            vipLabel: "会员"
                            onMove: function (index, delta) {
                                backend.ytMovePriority("yt_audio_order", index, delta)
                            }
                            onReset: backend.ytResetPriority("yt_audio_order")
                        }

                        PriorityList {
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignTop
                            title: "编码优先级"
                            hint: "同一分辨率下优先用哪种编码；没有的编码会自动跳到下一项。"
                            table: backend.ytCodecTable()
                            order: win.cfg.yt_codec_order
                            settingsKey: "yt_codec_order"
                            onMove: function (index, delta) {
                                backend.ytMovePriority("yt_codec_order", index, delta)
                            }
                            onReset: backend.ytResetPriority("yt_codec_order")
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: Theme.sp2
                        spacing: Theme.sp2
                        Text {
                            text: "字幕"
                            color: Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsBody
                            font.weight: Font.DemiBold
                        }
                        AppCheckBox {
                            text: "下载字幕"
                            checked: win.cfg.write_subs === true
                            onToggled: backend.setSetting("write_subs", value)
                        }
                        Text {
                            Layout.fillWidth: true
                            text: "人工字幕与自动生成的字幕都会一并接受；"
                                  + "下载页的「字幕」可以按这一条视频单独挑语言。"
                            color: Theme.textMuted
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsTiny
                            wrapMode: Text.Wrap
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.sp4
                            Text {
                                text: "默认字幕语言"
                                color: Theme.text
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fsLabel
                            }
                            AppTextField {
                                Layout.fillWidth: true
                                enabled: win.cfg.write_subs === true
                                placeholderText: "按优先级排列，用逗号分隔，如 zh-Hans,en"
                                monospace: true
                                text: win.cfg.sub_langs
                                onEditingFinished: backend.setSetting("sub_langs", text)
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.sp4
                            Text {
                                text: "字幕输出格式"
                                color: Theme.text
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fsLabel
                            }
                            AppComboBox {
                                Layout.preferredWidth: 300
                                enabled: win.cfg.write_subs === true
                                model: root.subFormatNames
                                currentIndex: root.idx(root.subFormats, win.cfg.sub_format)
                                onActivated: backend.setSetting("sub_format", root.subFormats[currentIndex])
                            }
                        }
                        AppCheckBox {
                            text: "将字幕嵌入视频"
                            checked: win.cfg.embed_subs === true
                            onToggled: backend.setSetting("embed_subs", value)
                        }
                        Text {
                            Layout.fillWidth: true
                            text: "嵌入需要 FFmpeg；MKV 容器支持最好，MP4 只支持部分字幕格式。"
                            color: Theme.textMuted
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsTiny
                            wrapMode: Text.Wrap
                        }
                    }
                }

                SectionCard {
                    title: "网络"
                    iconName: "globe"
                    collapsible: true
                    expanded: false

                    SettingRow {
                        label: "代理服务器"
                        hint: "例如 http://127.0.0.1:7890 或 socks5://127.0.0.1:1080"
                        AppTextField {
                            Layout.preferredWidth: 300
                            placeholderText: "留空表示不使用代理"
                            text: win.cfg.proxy
                            onEditingFinished: backend.setSetting("proxy", text)
                        }
                    }

                    SettingRow {
                        label: "Cookies 文件"
                        hint: "用于下载需要登录才能观看的内容"
                        AppTextField {
                            Layout.preferredWidth: 300
                            placeholderText: "cookies.txt"
                            text: win.cfg.cookie_file
                            onEditingFinished: backend.setSetting("cookie_file", text)
                        }
                        AppButton {
                            text: "浏览…"
                            variant: "secondary"
                            small: true
                            onClicked: {
                                var p = backend.pickFile("cookies")
                                if (p !== "") backend.setSetting("cookie_file", p)
                            }
                        }
                    }

                    SettingRow {
                        label: "从浏览器读取 Cookies"
                        hint: "Chrome / Edge 新版已加密 Cookie，此项大概率读取失败；"
                              + "建议改用上方“YouTube账号”"
                        AppComboBox {
                            Layout.preferredWidth: 300
                            model: root.cookieBrowserNames
                            currentIndex: root.idx(root.cookieBrowsers, win.cfg.cookie_browser)
                            onActivated: backend.setSetting("cookie_browser", root.cookieBrowsers[currentIndex])
                        }
                    }

                    SettingRow {
                        label: "下载限速"
                        hint: "0 表示不限速"
                        AppSlider {
                            Layout.preferredWidth: 220
                            from: 0
                            to: 20480
                            stepSize: 128
                            value: win.cfg.ratelimit_kib
                            onMoved: backend.setSetting("ratelimit_kib", value)
                        }
                        Text {
                            Layout.preferredWidth: 72
                            text: win.cfg.ratelimit_kib > 0
                                  ? (win.cfg.ratelimit_kib >= 1024
                                     ? (Math.round(win.cfg.ratelimit_kib / 1024 * 10) / 10) + " MiB/s"
                                     : win.cfg.ratelimit_kib + " KiB/s")
                                  : "不限速"
                            color: Theme.textDim
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsLabel
                            horizontalAlignment: Text.AlignRight
                        }
                    }

                    SettingRow {
                        label: "网络超时"
                        AppSlider {
                            Layout.preferredWidth: 220
                            from: 5
                            to: 120
                            stepSize: 5
                            value: win.cfg.socket_timeout
                            onMoved: backend.setSetting("socket_timeout", value)
                        }
                        Text {
                            Layout.preferredWidth: 72
                            text: win.cfg.socket_timeout + " 秒"
                            color: Theme.textDim
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsLabel
                            horizontalAlignment: Text.AlignRight
                        }
                    }
                }

                SectionCard {
                    title: "下载内容"
                    iconName: "download"
                    collapsible: true
                    expanded: false

                    SettingRow {
                        label: "视频容器格式"
                        AppComboBox {
                            Layout.preferredWidth: 300
                            model: root.containerNames
                            currentIndex: root.idx(root.containers, win.cfg.container)
                            onActivated: backend.setSetting("container", root.containers[currentIndex])
                        }
                    }

                    SettingRow {
                        label: "不覆盖已存在的文件"
                        AppSwitch {
                            checked: win.cfg.no_overwrites === true
                            onToggled: backend.setSetting("no_overwrites", value)
                        }
                    }

                    SettingRow {
                        label: "嵌入封面"
                        AppSwitch {
                            checked: win.cfg.embed_thumbnail === true
                            onToggled: backend.setSetting("embed_thumbnail", value)
                        }
                    }

                    SettingRow {
                        label: "写入元数据"
                        hint: "将标题、作者、说明写入文件属性"
                        AppSwitch {
                            checked: win.cfg.embed_metadata === true
                            onToggled: backend.setSetting("embed_metadata", value)
                        }
                    }

                    SettingRow {
                        label: "保存 info.json"
                        AppSwitch {
                            checked: win.cfg.write_infojson === true
                            onToggled: backend.setSetting("write_infojson", value)
                        }
                    }

                    SettingRow {
                        label: "保存视频说明"
                        AppSwitch {
                            checked: win.cfg.write_description === true
                            onToggled: backend.setSetting("write_description", value)
                        }
                    }

                    SettingRow {
                        label: "使用 SponsorBlock 标记"
                        hint: "自动获取并标记赞助、片头等片段"
                        AppSwitch {
                            checked: win.cfg.sponsorblock === true
                            onToggled: backend.setSetting("sponsorblock", value)
                        }
                    }

                    SettingRow {
                        label: "移除赞助片段"
                        hint: "需要 FFmpeg，会重新编码相关片段"
                        AppSwitch {
                            enabled: win.cfg.sponsorblock === true
                            checked: win.cfg.sponsorblock_remove === true
                            onToggled: backend.setSetting("sponsorblock_remove", value)
                        }
                    }

                    SettingRow {
                        label: "播放列表最多解析"
                        AppSlider {
                            Layout.preferredWidth: 220
                            from: 10
                            to: 1000
                            stepSize: 10
                            value: win.cfg.playlist_limit
                            onMoved: backend.setSetting("playlist_limit", value)
                        }
                        Text {
                            Layout.preferredWidth: 72
                            text: win.cfg.playlist_limit + " 项"
                            color: Theme.textDim
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsLabel
                            horizontalAlignment: Text.AlignRight
                        }
                    }
                }

                SectionCard {
                    title: "高级"
                    iconName: "keyboard"
                    collapsible: true
                    expanded: false

                    SettingRow {
                        label: "自定义 User-Agent"
                        AppTextField {
                            Layout.preferredWidth: 300
                            placeholderText: "默认使用浏览器标识"
                            text: win.cfg.user_agent
                            onEditingFinished: backend.setSetting("user_agent", text)
                        }
                    }

                    SettingRow {
                        label: "自定义 Referer"
                        AppTextField {
                            Layout.preferredWidth: 300
                            placeholderText: "部分站点需要指定来源页"
                            text: win.cfg.referer
                            onEditingFinished: backend.setSetting("referer", text)
                        }
                    }
                }

                Item { Layout.preferredHeight: Theme.sp6 }
            }
        }
    }

    BilibiliLogin { id: biliLogin }

    Popup {
        id: confirmLogout
        parent: Overlay.overlay
        anchors.centerIn: parent
        modal: true
        width: 360
        padding: Theme.sp5
        Overlay.modal: Rectangle { color: Theme.overlay }
        background: Rectangle {
            radius: Theme.rLg
            color: Theme.popupBg
            border.width: 1
            border.color: Theme.borderStrong
        }
        ColumnLayout {
            anchors.fill: parent
            spacing: Theme.sp4
            Text {
                text: "要退出哔哩哔哩登录吗？"
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsSubtitle
                font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                text: "退出后本机保存的登录凭据会被删除，画质将回到未登录时的水平。"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsLabel
                wrapMode: Text.Wrap
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                AppButton {
                    text: "取消"
                    variant: "secondary"
                    small: true
                    onClicked: confirmLogout.close()
                }
                AppButton {
                    text: "退出"
                    variant: "danger"
                    small: true
                    onClicked: {
                        backend.bilibili.logout()
                        confirmLogout.close()
                        backend.notify("info", "已退出哔哩哔哩", "本机保存的登录凭据已删除。")
                    }
                }
            }
        }
    }

    DepDialog {
        id: depDialog
        property string target: "ffmpeg"

        function openAsk(which) {
            target = which
            root.kind = which
            title = which === "ytdlp" ? "更新 yt-dlp" : "下载 FFmpeg"
            message = which === "ytdlp"
                      ? "即将从 Internet 下载 yt-dlp 组件并安装到程序的组件目录，不会改动你系统里的 Python 环境。"
                      : "此操作将从 Internet 下载 FFmpeg 组件，并安装到程序的组件目录。"
            question = which === "ytdlp"
                       ? "更新完成后需要重新启动程序。是否继续？"
                       : "组件约 40 MB。是否继续？"
            detail = which === "ytdlp" ? backend.deps.ytdlpStatusText : backend.deps.ffmpegStatusText
            mode = "ask"
            open()
        }

        onAccepted: {
            if (target === "ytdlp") {
                backend.deps.updateYtdlp()
                title = "正在更新 yt-dlp"
                message = "正在准备 yt-dlp。请不要关闭你的计算机。"
            } else {
                backend.deps.installFfmpeg()
                title = "正在下载 FFmpeg"
                message = "正在准备 FFmpeg。请不要关闭你的计算机。"
            }
            detail = ""
            mode = "progress"
        }

        onRejected: backend.notify("info", "已取消", "你可以稍后在“设置 - 组件”中重新操作。")
    }

    Connections {
        target: backend.deps
        function onFinished(kind, ok, message) {
            if (kind === "check") return
            depDialog.close()
        }
    }

    Popup {
        id: confirmReset
        parent: Overlay.overlay
        anchors.centerIn: parent
        modal: true
        Overlay.modal: Rectangle { color: Theme.overlay }
        width: 360
        padding: Theme.sp5
        background: Rectangle {
            radius: Theme.rLg
            color: Theme.popupBg
            border.width: 1
            border.color: Theme.borderStrong
        }
        ColumnLayout {
            anchors.fill: parent
            spacing: Theme.sp4
            Text {
                text: "要还原所有设置吗？"
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsSubtitle
                font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                text: "已下载的文件不会受到影响。此操作无法撤销。"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsLabel
                wrapMode: Text.Wrap
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                AppButton {
                    text: "取消"
                    variant: "secondary"
                    small: true
                    onClicked: confirmReset.close()
                }
                AppButton {
                    text: "还原"
                    variant: "danger"
                    small: true
                    onClicked: {
                        backend.resetSettings()
                        confirmReset.close()
                        backend.notify("success", "已还原默认设置", "")
                    }
                }
            }
        }
    }
}
