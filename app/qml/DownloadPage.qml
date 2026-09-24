import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

/* 下载页 */
Item {
    id: root

    property var media: null
    property string mediaThumb: ""
    property string errorText: ""
    property string errorTitle: ""
    property string errorRaw: ""
    property bool showRaw: false
    property bool audioOnly: false
    property string preset: "best"
    property string customFormatId: ""
    property string customFormatLabel: ""
    property bool customAutoMerge: true
    property string customVideoId: ""
    property string customAudioId: ""
    property string customVideoLabel: ""
    property string customAudioLabel: ""
    property var picked: ({})
    property bool allPicked: true

    /* 封面："" 跟随全局设置；"none" 不下载；"original" 原图；"640"/"320" 缩放宽度 */
    property string coverMode: ""
    /* 字幕：选中的语言代码列表 + 输出格式（"" 跟随全局设置） */
    property var subLangs: []
    property string subFormat: ""
    /* 「默认」：把画质、字幕、封面全部交回设置里的默认值。
       它是个可点掉的开关：再点一次就取消勾选、回到自定义；
       点右边任意一项也会自动切到自定义。为 true 时打包 spec 会显式传空串，
       让后端走「跟随全局设置」这条既有降级路径。 */
    property bool useDefaults: true
    /* 当前解析结果里可用的字幕语言（来自 media.subtitles） */
    readonly property var subtitleSource: (media && media.subtitles) ? media.subtitles : []

    signal requestQueue()

    readonly property bool hasMedia: media !== null
    readonly property bool isPlaylist: hasMedia && media.type === "playlist"
    readonly property int pickedCount: countPicked()

    readonly property var heightNames: ({ 2160: "4K", 1440: "2K", 1080: "1080P",
                                           720: "720P", 480: "480P", 360: "360P",
                                           240: "240P", 144: "144P" })

    /* 只列出解析结果里真实存在的画质档位，避免选了 4K 却只能下到 1080P；
       哔哩哔哩未登录时，把需要登录才能解锁的档位以灰化形式一并列出。 */
    readonly property var presets: {
        // 播放列表（分P/合集）拿不到统一的高度列表，用常见档位兜底
        var hs = (media && media.heights && media.heights.length > 0)
                 ? media.heights.slice()
                 : (isPlaylist ? [1080, 720, 480, 360] : [2160, 1440, 1080, 720, 480, 360])
        var lockedSet = {}
        if (needsBilibiliLogin()) {
            var extra = [2160, 1440]
            for (var j = 0; j < extra.length; j++) {
                if (hs.indexOf(extra[j]) < 0) {
                    hs.push(extra[j])
                    lockedSet[extra[j]] = true
                }
            }
        }
        hs.sort(function (a, b) { return b - a })
        var out = [{ key: "best", label: "最佳画质", locked: false }]
        for (var i = 0; i < hs.length; i++) {
            var h = hs[i]
            if (h > 0)
                out.push({ key: String(h), label: heightNames[h] || (h + "P"),
                           locked: lockedSet[h] === true })
        }
        out.push({ key: "worst", label: "最小体积", locked: false })
        return out
    }

    function qualityHint() {
        if (!media) return ""
        if (isPlaylist) {
            var tip = "播放列表会按每个项目自身可用的最高画质下载"
            if (media.isBilibili && !backend.bilibili.loggedIn)
                tip += "；未登录哔哩哔哩时最高只有 1080P"
            return tip
        }
        var h = media.maxHeight || 0
        var f = media.maxFps || 0
        var text = h > 0
                 ? ("当前最高可解析到 " + h + "P" + (f >= 50 ? " " + Math.round(f) + "fps" : ""))
                 : "未能解析到可用的视频画质"
        if (media.isBilibili && !backend.bilibili.loggedIn)
            text += "。带锁图标的 4K / 2K 档位需要登录哔哩哔哩后才能解锁"
        return text
    }

    function needsBilibiliLogin() {
        return media !== null && media.isBilibili === true && !backend.bilibili.loggedIn
    }

    /* 程序内登录的当前状态（YouTube 等）。放在属性里，避免在绑定中反复读文件。 */
    property var ytLogin: backend.weblogin.siteStatus("youtube")

    /* YouTube 未登录：会员专享、年龄限制等内容会解析失败或只能拿到低画质 */
    function needsYouTubeLogin() {
        if (media === null) return false
        if (String(media.extractor || "").indexOf("YouTube") < 0) return false
        return root.ytLogin.loggedIn !== true
    }

    /* 已登录、但 YouTube 拒绝了带登录态的请求，程序自动改用匿名模式解析 */
    readonly property bool anonymousFallback: media !== null
        && media.anonymous === true && root.ytLogin.loggedIn === true

    /* 解析失败的原因是“需要登录”，且链接属于支持程序内登录的站点 */
    readonly property bool loginFailure: {
        if (String(errorTitle).indexOf("登录") < 0) return false
        var u = String(backend.lastAnalyzeUrl || "").toLowerCase()
        return u.indexOf("youtube.com") >= 0 || u.indexOf("youtu.be") >= 0
    }

    readonly property bool isBili: media !== null && media.isBilibili === true

    function biliQualityAvailable(qn) {
        if (!media || !media.qualities || media.qualities.length === 0) return true
        return media.qualities.indexOf(qn) >= 0
    }

    function countPicked() {
        if (!isPlaylist) return 0
        var n = 0
        for (var k in picked) if (picked[k]) n++
        return n
    }

    function resetPicks() {
        var m = {}
        if (media && media.type === "playlist")
            for (var i = 0; i < media.entries.length; i++) m[i] = true
        picked = m
        allPicked = true
    }

    function resetResult() {
        media = null
        mediaThumb = ""
        errorText = ""
        errorTitle = ""
        errorRaw = ""
        showRaw = false
        picked = ({})
        allPicked = true
        customFormatId = ""
        customFormatLabel = ""
        customAutoMerge = true
        customVideoId = ""
        customAudioId = ""
        customVideoLabel = ""
        customAudioLabel = ""
        coverMode = ""
        subLangs = []
        subFormat = ""
        useDefaults = true
    }

    function togglePick(i) {
        var m = {}
        for (var k in picked) m[k] = picked[k]
        m[i] = !m[i]
        picked = m
        allPicked = countPicked() === (media ? media.entries.length : 0)
    }

    function setAll(v) {
        var m = {}
        if (isPlaylist) for (var i = 0; i < media.entries.length; i++) m[i] = v
        picked = m
        allPicked = v
    }

    function hasFormatChoice() {
        if (customFormatId !== "") return true
        if (preset === "best" || preset === "worst") return true
        return String(preset).indexOf("bili:") === 0
    }

    /* 弹窗里没单独选过格式时，用设置里的默认值 */
    function effectiveSubFormat() {
        return subFormat !== "" ? subFormat : (win.cfg.sub_format || "原始")
    }

    /* 「默认」选中时，把设置里实际会生效的选项拼成一句话，让用户知道会发生什么 */
    function defaultsSummary() {
        var cfg = win.cfg
        var bits = []
        bits.push(cfg.yt_use_custom_quality === true || isBili
                  ? "画质按优先级表自动选择" : "由 yt-dlp 自动选最佳画质")
        if (cfg.write_subs === true) {
            var langs = String(cfg.sub_langs || "").split(",").filter(
                        function (s) { return s.trim() !== "" })
            bits.push("字幕 " + (langs.length > 0 ? langs.length + " 种语言" : "全部语言"))
        } else {
            bits.push("不下载字幕")
        }
        var cover = String(cfg.bili_cover_mode || "")
        var coverText = { "none": "不下载封面", "original": "封面原图",
                          "640": "封面 640 宽", "320": "封面 320 宽" }[cover]
        bits.push(coverText !== undefined ? coverText
                                          : (cfg.embed_thumbnail === true
                                             ? "封面嵌入视频" : "不下载封面"))
        return bits.join("　·　")
    }

    function presetLabel() {
        /* 手动选过格式（含只选音频）时以具体格式为准 */
        if (customFormatId !== "") return customFormatLabel
        if (audioOnly) return "仅音频"
        if (preset === "best") return "最高品质（自动）"
        if (preset === "worst") return "最低品质（自动）"
        for (var i = 0; i < presets.length; i++)
            if (presets[i].key === preset) return presets[i].label
        return "最佳画质"
    }

    function doAnalyze() {
        var t = urlField.text.trim()
        if (t === "") return
        win.urlFieldUrl = t
        root.resetResult()
        backend.analyze(t)
    }

    function prefill(text) {
        urlField.text = text
        win.urlFieldUrl = text
        root.resetResult()
    }

    function startOne() {
        if (!hasMedia || isPlaylist) return

        /* 选中「默认」时：画质交回全局优先级表，字幕与封面传空串表示跟随设置 */
        if (useDefaults) {
            backend.startDownload({
                "url": media.webpage_url || media.url,
                "title": media.title,
                "uploader": media.uploader,
                "thumbnail": media.thumbnail,
                "duration": media.duration,
                "audioOnly": false,
                "preset": "best",
                "formatId": "",
                "formatLabel": "默认（跟随设置）",
                "outputDir": win.cfg.output_dir,
                "anonymous": media.anonymous === true,
                "coverMode": "",
                "subLangs": "",
                "subFormat": "",
                "kind": "complete"
            })
            backend.notify("success", "已添加到下载队列", media.title)
            root.requestQueue()
            return
        }

        /* 用户选择“不合并”时，把画面与声音拆成两个任务分别保存 */
        if (customFormatId.indexOf("+") >= 0 && !customAutoMerge
                && customVideoId !== "" && customAudioId !== "") {
            var common = {
                "url": media.webpage_url || media.url,
                "title": media.title,
                "uploader": media.uploader,
                "thumbnail": media.thumbnail,
                "duration": media.duration,
                "outputDir": win.cfg.output_dir,
                "preset": "custom",
                "audioOnly": false,
                "anonymous": media.anonymous === true
            }
            var videoSpec = Object.assign({}, common)
            videoSpec.formatId = customVideoId
            videoSpec.formatLabel = customVideoLabel + "（仅画面）"
            videoSpec.kind = "video_only"
            videoSpec.coverMode = root.coverMode
            videoSpec.subLangs = root.subLangs.join(",")
            videoSpec.subFormat = root.subFormat
            backend.startDownload(videoSpec)

            var audioSpec = Object.assign({}, common)
            audioSpec.formatId = customAudioId
            audioSpec.formatLabel = customAudioLabel + "（仅声音）"
            audioSpec.kind = "audio_only"
            audioSpec.subLangs = root.subLangs.join(",")
            audioSpec.subFormat = root.subFormat
            backend.startDownload(audioSpec)

            backend.notify("success", "已添加到下载队列", "画面与声音将分别保存为两个文件。")
            root.requestQueue()
            return
        }
        backend.startDownload({
            "url": media.webpage_url || media.url,
            "title": media.title,
            "uploader": media.uploader,
            "thumbnail": media.thumbnail,
            "duration": media.duration,
            "audioOnly": audioOnly,
            /* 手动选过格式（含只选音频）时一律按 custom 走，避免被“仅音频”的兜底选择顶掉 */
            "preset": customFormatId !== "" ? "custom" : (audioOnly ? "audio" : preset),
            "formatId": customFormatId,
            "formatLabel": presetLabel(),
            "outputDir": win.cfg.output_dir,
            "anonymous": media.anonymous === true,
            "coverMode": root.coverMode,
            "subLangs": root.subLangs.join(","),
            "subFormat": root.subFormat,
            "kind": audioOnly ? "audio_only" : "complete"
        })
        backend.notify("success", "已添加到下载队列", media.title)
        root.requestQueue()
    }

    function startPlaylist() {
        if (!isPlaylist) return
        var specs = []
        for (var i = 0; i < media.entries.length; i++) {
            if (!picked[i]) continue
            var e = media.entries[i]
            specs.push({
                "url": e.url,
                "title": e.title,
                "uploader": e.uploader,
                "thumbnail": e.thumbnail,
                "duration": e.duration,
                "audioOnly": useDefaults ? false : audioOnly,
                "preset": useDefaults ? "best" : (audioOnly ? "audio" : preset),
                "formatLabel": useDefaults ? "默认（跟随设置）" : presetLabel(),
                "playlistIndex": i + 1,
                "playlistCount": media.entries.length,
                "outputDir": win.cfg.output_dir,
                "anonymous": media.anonymous === true,
                "coverMode": useDefaults ? "" : root.coverMode,
                "subLangs": useDefaults ? "" : root.subLangs.join(","),
                "subFormat": useDefaults ? "" : root.subFormat,
                "kind": (useDefaults || !audioOnly) ? "complete" : "audio_only"
            })
        }
        if (specs.length === 0) {
            backend.notify("warning", "请至少选择一项", "请选择要下载的项目，然后重试。")
            return
        }
        var n = backend.startBatch(specs)
        backend.notify("success", "已添加到下载队列", "共添加 " + n + " 个项目。")
        root.requestQueue()
    }

    Connections {
        target: backend
        function onMediaReady(data) {
            root.media = data
            root.mediaThumb = data.thumbnailLocal || data.thumbnail || ""
            root.errorText = ""
            if (urlField.text.trim() === "" && data.sourceUrl) {
                urlField.text = data.sourceUrl
                win.urlFieldUrl = data.sourceUrl
            }
            root.resetPicks()
            if (backend.demoOpenFormat) formatDialog.open()
            if (backend.demoOpenBiliQuality) biliQualityDialog.open()
            if (backend.demoOpenSubtitles) subtitleDialog.open()
        }
        function onMediaFailed(title, hint, raw) {
            root.media = null
            root.mediaThumb = ""
            root.errorTitle = title !== "" ? title : "解析失败"
            /* hint 为空时界面会显示成一片空白、看着像“什么都没发生”，
               这里用兜底文案顶住，保证错误一定可见 */
            root.errorText = hint !== "" ? hint
                                         : "未能完成解析。可展开下方“原始信息”查看详细原因。"
            root.errorRaw = raw
            root.showRaw = false
        }
        function onMediaThumbReady(original, local) {
            if (root.media && root.media.thumbnail === original)
                root.mediaThumb = local
        }
    }

    Connections {
        target: backend.weblogin
        function onChanged() { root.ytLogin = backend.weblogin.siteStatus("youtube") }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.sp6
        spacing: Theme.sp4

        // ── 标题 ──────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Column {
                Layout.fillWidth: true
                spacing: 3
                Text {
                    text: "下载"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsDisplay
                    font.weight: Font.Bold
                }
                Text {
                    text: "在下方输入框中粘贴链接，然后选择“解析”。"
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsLabel
                }
            }
            AppButton {
                Layout.alignment: Qt.AlignVCenter
                visible: root.hasMedia || root.errorText !== ""
                text: "清空"
                iconName: "trash"
                variant: "ghost"
                small: true
                onClicked: {
                    urlField.text = ""
                    root.resetResult()
                }
            }
        }

        // ── 链接输入 ──────────────────────────────────────────
        AppCard {
            Layout.fillWidth: true
            padding: Theme.sp3
            highlighted: urlField.activeFocus

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.sp2

                AppTextField {
                    id: urlField
                    Layout.fillWidth: true
                    iconName: "link"
                    placeholderText: "请在此粘贴视频或播放列表的链接"
                    onAccepted: root.doAnalyze()
                    Keys.onEscapePressed: root.resetResult()
                }

                AppButton {
                    text: "粘贴"
                    iconName: "paste"
                    variant: "secondary"
                    onClicked: {
                        var t = backend.pasteFromClipboard()
                        if (t.trim() === "") {
                            backend.notify("warning", "剪贴板中没有文本", "请先复制链接，然后重试。")
                            return
                        }
                        urlField.text = t
                        root.resetResult()
                    }
                }

                AppButton {
                    text: "解析"
                    iconName: "search"
                    busy: backend.analyzing
                    enabled: urlField.text.trim() !== ""
                    onClicked: root.doAnalyze()
                }
            }
        }

        // ── 结果区 ────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            // 空状态
            Column {
                anchors.centerIn: parent
                spacing: Theme.sp3
                visible: !root.hasMedia && root.errorText === "" && !backend.analyzing

                Rectangle {
                    width: 80
                    height: 80
                    radius: 24
                    anchors.horizontalCenter: parent.horizontalCenter
                    color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.12)
                    border.width: 1
                    border.color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.38)

                    AppIcon {
                        anchors.centerIn: parent
                        name: "cloud"
                        size: 34
                        iconColor: Theme.accentText
                    }
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "尚未添加任何链接"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSubtitle
                    font.weight: Font.DemiBold
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 440
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                    text: "此程序支持 YouTube、Bilibili 等 1800 多个站点。\n"
                          + "你也可以直接粘贴播放列表链接，以便批量下载。"
                    color: Theme.textDim
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsLabel
                    lineHeight: 1.5
                }
                AppButton {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "从剪贴板粘贴"
                    iconName: "paste"
                    variant: "secondary"
                    small: true
                    onClicked: {
                        var t = backend.pasteFromClipboard()
                        if (t.trim() === "") {
                            backend.notify("warning", "剪贴板中没有文本", "请先复制链接，然后重试。")
                            return
                        }
                        root.prefill(t)
                    }
                }
            }

            // 解析中
            Column {
                anchors.centerIn: parent
                spacing: Theme.sp3
                visible: backend.analyzing
                AppIcon {
                    anchors.horizontalCenter: parent.horizontalCenter
                    name: "sync"
                    size: 32
                    iconColor: Theme.accentText
                    spin: true
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "正在获取媒体信息，请不要关闭此窗口…"
                    color: Theme.textDim
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsBody
                }
            }

            // 解析失败
            Column {
                anchors.centerIn: parent
                spacing: Theme.sp3
                width: Math.min(520, parent.width)
                visible: root.errorText !== "" && !backend.analyzing

                Rectangle {
                    width: 68
                    height: 68
                    radius: 22
                    anchors.horizontalCenter: parent.horizontalCenter
                    color: Qt.rgba(Theme.danger.r, Theme.danger.g, Theme.danger.b, 0.12)
                    AppIcon {
                        anchors.centerIn: parent
                        name: "warning"
                        size: 28
                        iconColor: Theme.danger
                    }
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: root.errorTitle !== "" ? root.errorTitle : "无法解析此链接"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSubtitle
                    font.weight: Font.DemiBold
                }
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                    text: root.errorText
                    color: Theme.textDim
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsLabel
                    maximumLineCount: 4
                    elide: Text.ElideRight
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    visible: root.errorRaw !== ""
                    text: root.showRaw ? "收起原始信息" : "查看原始信息"
                    color: Theme.accentText
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSmall
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.showRaw = !root.showRaw
                    }
                }
                Text {
                    width: parent.width
                    visible: root.showRaw && root.errorRaw !== ""
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                    text: root.errorRaw
                    color: Theme.textMuted
                    font.family: "Cascadia Mono"
                    font.pixelSize: Theme.fsTiny
                    maximumLineCount: 6
                    elide: Text.ElideRight
                }
                Row {
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: Theme.sp2

                    AppButton {
                        text: "重试"
                        iconName: "refresh"
                        variant: "secondary"
                        small: true
                        onClicked: backend.reanalyze()
                    }
                    /* 登录类失败时直接给出去登录的入口 */
                    AppButton {
                        visible: root.loginFailure
                        text: "去登录"
                        iconName: "globe"
                        small: true
                        onClicked: backend.weblogin.startLogin("youtube")
                    }
                }
            }

            // 解析结果
            Flickable {
                id: resultFlick
                anchors.fill: parent
                visible: root.hasMedia && !backend.analyzing
                contentWidth: width
                contentHeight: Math.max(resultFlick.height, resultColumn.implicitHeight)
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: AppScrollBar { }

                ColumnLayout {
                    id: resultColumn
                    width: resultFlick.width - 10
                    spacing: Theme.sp4

                    AppCard {
                        Layout.fillWidth: true
                        padding: Theme.sp4

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.sp4

                            Rectangle {
                                Layout.preferredWidth: 196
                                Layout.preferredHeight: 110
                                radius: Theme.rMd
                                color: Theme.surfaceAlt
                                clip: true

                                Image {
                                    id: thumb
                                    anchors.fill: parent
                                    source: root.mediaThumb
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                    cache: true
                                    visible: status === Image.Ready
                                }

                                AppIcon {
                                    anchors.centerIn: parent
                                    visible: thumb.status !== Image.Ready
                                    name: root.isPlaylist ? "library" : "video"
                                    size: 28
                                    iconColor: Theme.textMuted
                                }

                                Rectangle {
                                    visible: root.media && root.media.durationText !== ""
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    anchors.margins: 6
                                    width: durText.implicitWidth + 12
                                    height: 20
                                    radius: 6
                                    color: "#B3000000"
                                    Text {
                                        id: durText
                                        anchors.centerIn: parent
                                        text: (root.media && root.media.durationText)
                                              ? root.media.durationText : ""
                                        color: "#FFFFFF"
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fsSmall
                                        font.weight: Font.DemiBold
                                    }
                                }

                                Rectangle {
                                    visible: root.media !== null && root.media.isLive === true
                                    anchors.left: parent.left
                                    anchors.top: parent.top
                                    anchors.margins: 6
                                    width: liveText.implicitWidth + 14
                                    height: 20
                                    radius: 6
                                    color: Theme.danger
                                    Text {
                                        id: liveText
                                        anchors.centerIn: parent
                                        text: "直播"
                                        color: "#FFFFFF"
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fsSmall
                                        font.weight: Font.DemiBold
                                    }
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: Theme.sp2

                                Text {
                                    Layout.fillWidth: true
                                    text: root.media ? root.media.title : ""
                                    color: Theme.text
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fsSubtitle
                                    font.weight: Font.DemiBold
                                    wrapMode: Text.Wrap
                                    maximumLineCount: 2
                                    elide: Text.ElideRight
                                    lineHeight: 1.25
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: {
                                        if (!root.media) return ""
                                        var bits = []
                                        if (root.media.uploader) bits.push(root.media.uploader)
                                        if (root.media.extractor) bits.push(root.media.extractor)
                                        if (root.isPlaylist) bits.push("共 " + root.media.entryCount + " 个项目")
                                        else if (root.media.formatCount > 0)
                                            bits.push(root.media.formatCount + " 种可用格式")
                                        return bits.join("  ·  ")
                                    }
                                    color: Theme.textDim
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fsLabel
                                    elide: Text.ElideRight
                                }

                                /* YouTube 未登录时的提示：会员专享 / 年龄限制内容会拿不到 */
                                Rectangle {
                                    Layout.fillWidth: true
                                    visible: root.needsYouTubeLogin()
                                    implicitHeight: ytNotice.implicitHeight + Theme.sp4
                                    radius: Theme.rSm
                                    color: Qt.rgba(Theme.warning.r, Theme.warning.g,
                                                   Theme.warning.b, 0.10)
                                    border.width: 1
                                    border.color: Qt.rgba(Theme.warning.r, Theme.warning.g,
                                                          Theme.warning.b, 0.30)

                                    RowLayout {
                                        id: ytNotice
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.leftMargin: Theme.sp3
                                        anchors.rightMargin: Theme.sp3
                                        spacing: Theme.sp2

                                        AppIcon {
                                            name: "warning"
                                            size: 14
                                            iconColor: Theme.warning
                                            Layout.alignment: Qt.AlignVCenter
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            Layout.alignment: Qt.AlignVCenter
                                            text: "YouTube 未登录。会员专享、年龄限制等内容将无法下载。"
                                            color: Theme.textDim
                                            font.family: Theme.fontFamily
                                            font.pixelSize: Theme.fsSmall
                                            wrapMode: Text.Wrap
                                            lineHeight: 1.4
                                        }
                                        AppButton {
                                            text: "去登录"
                                            small: true
                                            Layout.alignment: Qt.AlignVCenter
                                            onClicked: backend.weblogin.startLogin("youtube")
                                        }
                                    }
                                }

                                /* 已登录却被 YouTube 拒绝时的说明，避免用户以为登录没生效 */
                                Rectangle {
                                    Layout.fillWidth: true
                                    visible: root.anonymousFallback
                                    implicitHeight: anonNotice.implicitHeight + Theme.sp4
                                    radius: Theme.rSm
                                    color: Qt.rgba(Theme.info.r, Theme.info.g,
                                                   Theme.info.b, 0.10)
                                    border.width: 1
                                    border.color: Qt.rgba(Theme.info.r, Theme.info.g,
                                                          Theme.info.b, 0.30)

                                    RowLayout {
                                        id: anonNotice
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.leftMargin: Theme.sp3
                                        anchors.rightMargin: Theme.sp3
                                        spacing: Theme.sp2

                                        AppIcon {
                                            name: "info"
                                            size: 14
                                            iconColor: Theme.info
                                            Layout.alignment: Qt.AlignVCenter
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            Layout.alignment: Qt.AlignVCenter
                                            text: "YouTube 未接受本次登录凭据，已自动改用匿名模式。"
                                                  + "普通视频不受影响，会员专享内容可能无法下载。"
                                            color: Theme.textDim
                                            font.family: Theme.fontFamily
                                            font.pixelSize: Theme.fsSmall
                                            wrapMode: Text.Wrap
                                            lineHeight: 1.4
                                        }
                                    }
                                }

                                Item { Layout.fillHeight: true }

                                Flow {
                                    Layout.fillWidth: true
                                    spacing: Theme.sp2

                                    /* 说明这排胶囊是「本次下载」的覆盖项：
                                       「默认」= 全部跟随设置，点它可切换；点右边任意一项即改为自定义 */
                                    Text {
                                        text: "本次下载"
                                        color: Theme.textMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fsSmall
                                        height: 26
                                        verticalAlignment: Text.AlignVCenter
                                    }

                                    /* 默认项：画质、字幕、封面全部交回设置里的默认值。
                                       再点一次即可取消勾选；点右边任意一项也会自动切到自定义。
                                       三项不再置灰 —— 置灰又点不掉会把用户锁死在默认态。 */
                                    Chip {
                                        objectName: "defaultsChip"
                                        text: "默认"
                                        iconName: "star"
                                        compact: true
                                        checkWhenSelected: true
                                        selected: root.useDefaults
                                        onClicked: root.useDefaults = !root.useDefaults
                                    }

                                    /* 画质选择统一进“格式选择”弹窗（含自动挡），不再单独摆快捷档 */
                                    Chip {
                                        text: root.isBili ? "画质选择" : "格式选择"
                                        compact: true
                                        selected: !root.useDefaults && root.hasFormatChoice()
                                        onClicked: {
                                            root.useDefaults = false
                                            if (root.isBili) {
                                                biliQualityDialog.open()
                                            } else {
                                                formatDialog.autoMode =
                                                    (root.preset === "best" ? "best"
                                                     : root.preset === "worst" ? "worst" : "")
                                                formatDialog.open()
                                            }
                                        }
                                    }

                                    Chip {
                                        text: root.coverMode === "" ? "封面"
                                                  : (root.coverMode === "none" ? "封面 · 不下载"
                                                     : "封面 · " + root.coverMode)
                                        compact: true
                                        selected: !root.useDefaults && root.coverMode !== ""
                                        onClicked: {
                                            root.useDefaults = false
                                            coverDialog.open()
                                        }
                                    }

                                    Chip {
                                        text: {
                                            if (root.subLangs.length === 0) return "字幕"
                                            var fmt = root.effectiveSubFormat()
                                            var tag = (fmt !== "" && fmt !== "原始")
                                                      ? " · " + fmt.toUpperCase() : ""
                                            return "字幕 · " + root.subLangs.length + " 种" + tag
                                        }
                                        compact: true
                                        selected: !root.useDefaults && root.subLangs.length > 0
                                        onClicked: {
                                            root.useDefaults = false
                                            subtitleDialog.open()
                                        }
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.topMargin: 2
                                    visible: root.qualityHint() !== ""
                                    spacing: Theme.sp2

                                    AppIcon {
                                        name: root.needsBilibiliLogin() ? "warning" : "info"
                                        size: 13
                                        iconColor: root.needsBilibiliLogin() ? Theme.warning : Theme.textMuted
                                        Layout.alignment: Qt.AlignVCenter
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: root.qualityHint()
                                        color: root.needsBilibiliLogin() ? Theme.warning : Theme.textMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fsSmall
                                        elide: Text.ElideRight
                                    }
                                    AppButton {
                                        Layout.alignment: Qt.AlignVCenter
                                        visible: root.needsBilibiliLogin()
                                        text: "登录哔哩哔哩"
                                        small: true
                                        onClicked: biliLogin.open()
                                    }
                                }

                                /* 「默认」生效时，把设置里实际会采用的字幕/封面说出来，
                                   并把入口指向设置页，省得用户来回找 */
                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.topMargin: 1
                                    visible: root.useDefaults
                                    spacing: Theme.sp2

                                    AppIcon {
                                        name: "star"
                                        size: 13
                                        iconColor: Theme.accentText
                                        Layout.alignment: Qt.AlignVCenter
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: root.defaultsSummary()
                                        color: Theme.textMuted
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fsSmall
                                        elide: Text.ElideRight
                                    }
                                    AppButton {
                                        Layout.alignment: Qt.AlignVCenter
                                        text: "去设置"
                                        variant: "ghost"
                                        small: true
                                        onClicked: win.page = 3
                                    }
                                }
                            }
                        }
                    }

                    AppCard {
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.isPlaylist
                                              ? Math.min(340, 80 + root.media.entries.length * 44)
                                              : 0
                        visible: root.isPlaylist
                        padding: Theme.sp4

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: Theme.sp2

                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: "选择要下载的项目"
                                    color: Theme.text
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fsBody
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    text: "已选择 " + root.pickedCount + " / "
                                          + (root.isPlaylist ? root.media.entries.length : 0) + " 项"
                                    color: Theme.textMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fsLabel
                                }
                                Item { Layout.fillWidth: true }
                                AppButton {
                                    text: root.allPicked ? "取消全选" : "全选"
                                    variant: "ghost"
                                    small: true
                                    onClicked: root.setAll(!root.allPicked)
                                }
                            }

                            ListView {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                clip: true
                                model: root.isPlaylist ? root.media.entries : []
                                spacing: 2
                                boundsBehavior: Flickable.StopAtBounds
                                ScrollBar.vertical: AppScrollBar { }

                                delegate: Rectangle {
                                    required property var modelData
                                    required property int index
                                    width: ListView.view.width
                                    height: 42
                                    radius: Theme.rSm
                                    color: rowMouse.containsMouse ? Theme.surfaceHover : "transparent"

                                    MouseArea {
                                        id: rowMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.togglePick(index)
                                    }

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 6
                                        anchors.rightMargin: 10
                                        spacing: Theme.sp3

                                        AppCheckBox {
                                            checked: root.picked[index] === true
                                            onToggled: root.togglePick(index)
                                        }
                                        Text {
                                            Layout.preferredWidth: 34
                                            text: modelData.index
                                            color: Theme.textMuted
                                            font.family: Theme.fontFamily
                                            font.pixelSize: Theme.fsSmall
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: modelData.title
                                            color: Theme.text
                                            font.family: Theme.fontFamily
                                            font.pixelSize: Theme.fsLabel
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            text: modelData.durationText
                                            color: Theme.textMuted
                                            font.family: Theme.fontFamily
                                            font.pixelSize: Theme.fsSmall
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.topMargin: Theme.sp1
                        Layout.preferredHeight: actionRow.implicitHeight + Theme.sp3 * 2
                        radius: Theme.rLg
                        color: Theme.surface
                        border.width: 1
                        border.color: Theme.border

                        RowLayout {
                        id: actionRow
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.leftMargin: Theme.sp3
                        anchors.rightMargin: Theme.sp3
                        spacing: Theme.sp3

                        AppButton {
                            Layout.alignment: Qt.AlignVCenter
                            text: "保存到"
                            iconName: "folder"
                            variant: "ghost"
                            onClicked: {
                                var p = backend.chooseDirectoryDialog()
                                if (p !== "") backend.setSetting("output_dir", p)
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: (win.cfg.output_dir || "")
                            color: Theme.textDim
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsLabel
                            elide: Text.ElideMiddle
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    backend.copyText(win.cfg.output_dir)
                                    backend.notify("info", "已复制保存位置", win.cfg.output_dir)
                                }
                            }
                        }

                        AppButton {
                            Layout.alignment: Qt.AlignVCenter
                            visible: root.isPlaylist
                            text: "下载选中的 " + root.pickedCount + " 项"
                            iconName: "download"
                            enabled: root.pickedCount > 0
                            onClicked: root.startPlaylist()
                        }

                        AppButton {
                            Layout.alignment: Qt.AlignVCenter
                            visible: !root.isPlaylist
                            text: root.useDefaults ? "下载（跟随设置）" : "下载"
                            iconName: "download"
                            onClicked: root.startOne()
                        }
                        }
                    }
                }
            }
        }
    }

    BilibiliLogin { id: biliLogin }

    BiliQualityDialog {
        id: biliQualityDialog
        available: root.media && root.media.qualities ? root.media.qualities : []
        unavailable: root.media && root.media.unavailableQualities
                     ? root.media.unavailableQualities : []
        currentQn: String(root.preset).indexOf("bili:") === 0
                   ? parseInt(String(root.preset).slice(5))
                   : (root.preset === "best" ? biliQualityDialog.qnBest
                      : root.preset === "worst" ? biliQualityDialog.qnWorst : 0)
        onPicked: function (qn) {
            root.audioOnly = false
            root.customFormatId = ""
            root.customFormatLabel = ""
            /* -1 / -2 是自动挡，等价于通用的最高 / 最低品质预设 */
            if (qn === biliQualityDialog.qnBest) root.preset = "best"
            else if (qn === biliQualityDialog.qnWorst) root.preset = "worst"
            else root.preset = "bili:" + qn
        }
    }

    FormatDialog {
        id: formatDialog
        formats: root.media && root.media.formats ? root.media.formats : []
        onPicked: function (f) {
            root.audioOnly = f.audioOnly === true
            if (f.autoTier) {
                root.customFormatId = ""
                root.customFormatLabel = ""
                root.preset = f.autoTier
                return
            }
            root.customFormatId = f.formatId
            root.customFormatLabel = f.label
            root.customAutoMerge = f.autoMerge !== false
            root.customVideoId = f.videoId || ""
            root.customAudioId = f.audioId || ""
            root.customVideoLabel = f.videoLabel || ""
            root.customAudioLabel = f.audioLabel || ""
            root.preset = "custom"
        }
    }

    CoverDialog {
        id: coverDialog
        onAccepted: function (mode) {
            root.coverMode = mode
        }
    }

    SubtitleDialog {
        id: subtitleDialog
        available: root.subtitleSource
        selected: root.subLangs
        format: root.subFormat
        onAccepted: function (langs, fmt) {
            root.subLangs = langs
            root.subFormat = fmt
        }
    }

    DropArea {
        anchors.fill: parent
        onDropped: function (drop) {
            if (drop.hasText) {
                urlField.text = drop.text
                root.doAnalyze()
            }
        }
    }
}
