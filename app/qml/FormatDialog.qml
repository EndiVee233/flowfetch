import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

/* 格式选择：视频与音频分栏单选，可自由组合 */
Popup {
    id: root

    property var formats: []
    property string keyword: ""

    /* 两级选择：先选档位（视频=分辨率+帧率，音频=码率档），
       再在右边那栏选这个档位下可用的编码 */
    property string videoKey: ""
    property string videoCodec: ""
    property string audioKey: ""
    property string audioCodec: ""

    property bool autoMerge: true

    /* 自动挡："" / "best" / "worst"。选中后视频与音频由程序自动选最优并合并，
       此时两栏的手动选择被禁用，避免“视频选最高、音频选最低”的错配。 */
    property string autoMode: ""

    signal picked(var result)

    function matches(f) {
        if (keyword.trim() === "") return true
        var k = keyword.trim().toLowerCase()
        return (String(f.label) + " " + f.ext + " " + f.formatId + " " + f.vcodec
                + " " + f.acodec + " " + f.resolution + " " + f.note)
               .toLowerCase().indexOf(k) >= 0
    }

    /* 视频栏：所有带画面的格式（含音视频合一的） */
    readonly property var videoList: {
        var out = []
        for (var i = 0; i < formats.length; i++) {
            var f = formats[i]
            if (f.hasVideo && matches(f)) out.push(f)
        }
        out.sort(function (a, b) {
            if (b.height !== a.height) return b.height - a.height
            if (b.fps !== a.fps) return b.fps - a.fps
            return b.tbr - a.tbr
        })
        return out
    }

    /* 音频栏：纯音频格式 */
    readonly property var audioList: {
        var out = []
        for (var i = 0; i < formats.length; i++) {
            var f = formats[i]
            if (!f.hasVideo && f.hasAudio && matches(f)) out.push(f)
        }
        out.sort(function (a, b) { return b.tbr - a.tbr })
        return out
    }

    // ── 档位分组 ────────────────────────────────────────────────────
    function fpsOf(f) { return f.fps > 0 ? Math.round(f.fps) : 0 }
    function resOf(f) {
        if (f.width && f.height) return f.width + "x" + f.height
        if (f.height) return f.height + "p"
        return "未知分辨率"
    }
    function videoKeyOf(f) { return resOf(f) + "@" + fpsOf(f) }
    function videoLabelOf(f) {
        var fps = fpsOf(f)
        return fps > 0 ? (resOf(f) + " · " + fps + "FPS") : resOf(f)
    }
    function kbpsOf(f) { return Math.round(f.abr > 0 ? f.abr : (f.tbr || 0)) }
    /* 码率档按 16k 取整，这样「AAC 129K」和「Opus 128K」会归到同一档，
       用户才能在同一档里比较两种编码 */
    function audioKeyOf(f) {
        var kbps = kbpsOf(f)
        if (kbps <= 0) return "未知码率"
        return String(Math.max(1, Math.round(kbps / 16)) * 16)
    }
    function audioLabelOf(list) {
        var best = 0
        for (var i = 0; i < list.length; i++) best = Math.max(best, kbpsOf(list[i]))
        return best > 0 ? (best + "kbps") : "未知码率"
    }
    function codecKeyOf(f) { return String(f.codecKey || f.codec || "default") }
    function codecLabelOf(f) { return String(f.codec || "") !== "" ? f.codec : "默认" }

    function sizeRange(list) {
        var lo = 0
        for (var i = 0; i < list.length; i++) {
            var s = list[i].filesize || 0
            if (s > 0 && (lo === 0 || s < lo)) lo = s
        }
        return lo > 0 ? (human(lo) + " 起") : "体积未知"
    }

    /* 编码排序沿用设置里的「编码优先级」，认不出的排在最后 */
    readonly property var videoCodecRank: {
        var t = backend.ytCodecTable()
        var m = ({})
        for (var i = 0; i < t.length; i++) m[String(t[i].value)] = i
        return m
    }
    readonly property var audioCodecRank: {
        var t = backend.ytAudioTable()
        var m = ({})
        for (var i = 0; i < t.length; i++) m[String(t[i].value)] = i
        return m
    }
    function codecRank(f) {
        var itag = audioCodecRank[String(f.formatId || "")]
        if (!f.hasVideo && itag !== undefined) return itag
        var key = String(f.codecKey || "").toLowerCase()
        if (key === "vp09") key = "vp9"
        if (key === "hvc1" || key === "hev1") key = "hevc"
        var r = videoCodecRank[key]
        return r === undefined ? 99 : r
    }

    /* 同一编码同一档位可能有 DRC 之类的变体：优先普通版本，其次高码率 */
    function betterFormat(f, cur, isVideo) {
        var fd = String(f.formatId || "").indexOf("-drc") >= 0
        var cd = String(cur.formatId || "").indexOf("-drc") >= 0
        if (fd !== cd) return !fd
        var fa = isVideo ? (f.tbr || 0) : kbpsOf(f)
        var ca = isVideo ? (cur.tbr || 0) : kbpsOf(cur)
        return fa > ca
    }

    function buildCodecs(list, isVideo) {
        var picked = ({})
        for (var i = 0; i < list.length; i++) {
            var f = list[i]
            var ck = codecKeyOf(f)
            if (picked[ck] === undefined || betterFormat(f, picked[ck], isVideo))
                picked[ck] = f
        }
        var arr = []
        for (var k in picked) arr.push(picked[k])
        arr.sort(function (a, b) {
            var ra = codecRank(a)
            var rb = codecRank(b)
            if (ra !== rb) return ra - rb
            return (b.tbr || 0) - (a.tbr || 0)
        })
        return arr
    }

    function buildGroups(list, isVideo) {
        var map = ({})
        var order = []
        for (var i = 0; i < list.length; i++) {
            var f = list[i]
            var key = isVideo ? videoKeyOf(f) : audioKeyOf(f)
            if (map[key] === undefined) {
                map[key] = { key: key, formats: [] }
                order.push(key)
            }
            map[key].formats.push(f)
        }
        var out = []
        for (var j = 0; j < order.length; j++) {
            var g = map[order[j]]
            g.label = isVideo ? videoLabelOf(g.formats[0]) : audioLabelOf(g.formats)
            g.codecs = buildCodecs(g.formats, isVideo)
            g.sub = g.codecs.length + " 种编码 · " + sizeRange(g.formats)
            out.push(g)
        }
        return out
    }

    function groupByKey(groups, key) {
        for (var i = 0; i < groups.length; i++)
            if (String(groups[i].key) === String(key)) return groups[i]
        return null
    }
    function groupRows(groups) {
        var out = []
        for (var i = 0; i < groups.length; i++)
            out.push({ key: groups[i].key, label: groups[i].label, sub: groups[i].sub })
        return out
    }
    function codecRows(group) {
        var out = []
        if (group === null) return out
        for (var i = 0; i < group.codecs.length; i++) {
            var f = group.codecs[i]
            out.push({ key: codecKeyOf(f), label: codecLabelOf(f), sub: codecSub(f) })
        }
        return out
    }
    function codecSub(f) {
        var bits = ["ID " + f.formatId]
        if (f.ext) bits.push(String(f.ext).toUpperCase())
        if (f.abr > 0) bits.push(Math.round(f.abr) + "kbps")
        if (f.filesizeText && f.filesizeText !== "未知") bits.push(f.filesizeText)
        if (f.hasVideo && f.hasAudio) bits.push("含声音")
        return bits.join(" · ")
    }

    readonly property var videoGroups: buildGroups(videoList, true)
    readonly property var audioGroups: buildGroups(audioList, false)
    readonly property var videoGroup: groupByKey(videoGroups, videoKey)
    readonly property var audioGroup: groupByKey(audioGroups, audioKey)
    readonly property var videoGroupRows: groupRows(videoGroups)
    readonly property var audioGroupRows: groupRows(audioGroups)
    readonly property var videoCodecRows: codecRows(videoGroup)
    readonly property var audioCodecRows: codecRows(audioGroup)

    function pickVideoGroup(key) {
        videoKey = key
        var g = groupByKey(videoGroups, key)
        videoCodec = (g !== null && g.codecs.length > 0) ? codecKeyOf(g.codecs[0]) : ""
    }
    function pickAudioGroup(key) {
        audioKey = key
        var g = groupByKey(audioGroups, key)
        audioCodec = (g !== null && g.codecs.length > 0) ? codecKeyOf(g.codecs[0]) : ""
    }

    readonly property var pickedVideo: {
        var g = videoGroup
        if (g === null || g.codecs.length === 0) return null
        for (var i = 0; i < g.codecs.length; i++)
            if (codecKeyOf(g.codecs[i]) === videoCodec) return g.codecs[i]
        return g.codecs[0]
    }
    readonly property var pickedAudio: {
        var g = audioGroup
        if (g === null || g.codecs.length === 0) return null
        for (var i = 0; i < g.codecs.length; i++)
            if (codecKeyOf(g.codecs[i]) === audioCodec) return g.codecs[i]
        return g.codecs[0]
    }

    readonly property bool videoHasAudio: pickedVideo !== null && pickedVideo.hasAudio === true
    readonly property bool needsBoth: pickedVideo !== null && pickedAudio !== null && !videoHasAudio
    readonly property string resultId: {
        if (needsBoth) return pickedVideo.formatId + "+" + pickedAudio.formatId
        if (pickedVideo !== null) return pickedVideo.formatId
        if (pickedAudio !== null) return pickedAudio.formatId
        return ""
    }
    function brief(f) {
        if (f === null) return ""
        var base = (f.shortLabel && f.shortLabel !== "") ? f.shortLabel : f.label
        // 精简标签里已经不放编码了，这里补回来，"将下载" 才能看清是哪种编码
        return f.codec ? (base + " · " + f.codec) : base
    }
    function sizeOf(f) {
        if (f === null || !f.filesizeText || f.filesizeText === "未知") return ""
        return "（" + f.filesizeText + "）"
    }
    function bytesOf(f) {
        return (f === null || !f.filesize) ? 0 : f.filesize
    }
    function human(bytes) {
        if (bytes <= 0) return ""
        var units = ["B", "KB", "MB", "GB", "TB"]
        var i = 0, v = bytes
        while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
        return (i === 0 ? v.toFixed(0) : v.toFixed(2)) + " " + units[i]
    }

    // 用 real：4K 素材动辄超过 32 位 int 的上限
    readonly property real totalBytes: bytesOf(pickedVideo)
                                       + (videoHasAudio ? 0 : bytesOf(pickedAudio))

    readonly property string resultLabel: {
        if (autoMode !== "") return autoLabel
        if (needsBoth)
            return brief(pickedVideo) + sizeOf(pickedVideo)
                   + "　＋　" + brief(pickedAudio) + sizeOf(pickedAudio)
        if (pickedVideo !== null) return brief(pickedVideo) + sizeOf(pickedVideo)
        if (pickedAudio !== null) return brief(pickedAudio) + sizeOf(pickedAudio)
        return ""
    }

    readonly property string autoLabel: {
        if (autoMode === "best") return "最高品质（自动）"
        if (autoMode === "worst") return "最低品质（自动）"
        return ""
    }

    function pickAuto(key) {
        if (autoMode === key) {
            autoMode = ""
            return
        }
        autoMode = key
        /* 切到自动挡时清空手动选择，整段由程序接管 */
        videoKey = ""
        videoCodec = ""
        audioKey = ""
        audioCodec = ""
    }

    onOpened: {
        autoMode = ""
        pickVideoGroup(videoGroups.length > 0 ? videoGroups[0].key : "")
        pickAudioGroup(audioGroups.length > 0 ? audioGroups[0].key : "")
        autoMerge = true
    }

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(1080, (parent ? parent.width : 960) - 48)
    height: Math.min(620, (parent ? parent.height : 700) - 50)
    modal: true
    focus: true
    padding: 0
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    Overlay.modal: Rectangle { color: Theme.overlay }

    background: Rectangle {
        radius: Theme.rXl
        color: Theme.popupBg
        border.width: 1
        border.color: Theme.borderStrong
    }

    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.durFast }
        NumberAnimation { property: "scale"; from: 0.96; to: 1; duration: Theme.durBase; easing.type: Easing.OutCubic }
    }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.durFast } }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 60

            Column {
                anchors.left: parent.left
                anchors.leftMargin: Theme.sp5
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                Text {
                    text: "选择下载格式"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSubtitle
                    font.weight: Font.DemiBold
                }
                Text {
                    text: "先选档位，再在右边挑这个档位下的编码；只选一边也可以，选“不使用”即可留空。"
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSmall
                }
            }

            IconButton {
                anchors.right: parent.right
                anchors.rightMargin: Theme.sp3
                anchors.verticalCenter: parent.verticalCenter
                iconName: "close"
                onClicked: root.close()
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borderSoft }

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            AppTextField {
                anchors.fill: parent
                anchors.margins: Theme.sp3
                iconName: "search"
                placeholderText: "搜索格式：1080、mp4、avc1、audio…"
                onTextChanged: root.keyword = text
            }
        }

        /* 自动挡：一键交给程序选最优画质并合并，选了它就不能再手动挑另一栏 */
        ColumnLayout {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.sp4
            Layout.rightMargin: Theme.sp4
            Layout.topMargin: Theme.sp3
            Layout.bottomMargin: Theme.sp2
            spacing: Theme.sp1

            Text {
                text: "快速选择"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsSmall
            }
            Flow {
                Layout.fillWidth: true
                spacing: Theme.sp2
                Chip {
                    text: "最高品质（自动）"
                    compact: true
                    selected: root.autoMode === "best"
                    onClicked: root.pickAuto("best")
                }
                Chip {
                    text: "最低品质（自动）"
                    compact: true
                    selected: root.autoMode === "worst"
                    onClicked: root.pickAuto("worst")
                }
            }
            Text {
                visible: root.autoMode !== ""
                text: "已选择自动挡，点击下方按钮可取消并手动选择。"
                color: Theme.textDim
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsTiny
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borderSoft }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            FormatColumn {
                Layout.fillWidth: true
                Layout.fillHeight: true
                enabled: root.autoMode === ""
                opacity: root.autoMode === "" ? 1.0 : 0.45
                title: "视频"
                subtitle: root.videoGroups.length + " 个档位"
                items: root.videoGroupRows
                selectionKey: root.videoKey
                onPicked: function (key) { root.pickVideoGroup(key) }
            }

            Rectangle { Layout.preferredWidth: 1; Layout.fillHeight: true; color: Theme.borderSoft }

            FormatColumn {
                Layout.fillWidth: true
                Layout.fillHeight: true
                enabled: root.autoMode === ""
                opacity: root.autoMode === "" ? 1.0 : 0.45
                title: "视频编码"
                subtitle: root.videoGroup ? root.videoGroup.label : "先选左侧档位"
                items: root.videoCodecRows
                selectionKey: root.videoCodec
                allowNone: false
                emptyText: "先选左侧档位"
                onPicked: function (key) { root.videoCodec = key }
            }

            Rectangle { Layout.preferredWidth: 1; Layout.fillHeight: true; color: Theme.borderSoft }

            FormatColumn {
                Layout.fillWidth: true
                Layout.fillHeight: true
                enabled: root.autoMode === ""
                opacity: root.autoMode === "" ? 1.0 : 0.45
                title: "音频"
                subtitle: root.audioGroups.length + " 个档位"
                muted: root.videoHasAudio
                items: root.audioGroupRows
                selectionKey: root.audioKey
                onPicked: function (key) { root.pickAudioGroup(key) }
            }

            Rectangle { Layout.preferredWidth: 1; Layout.fillHeight: true; color: Theme.borderSoft }

            FormatColumn {
                Layout.fillWidth: true
                Layout.fillHeight: true
                enabled: root.autoMode === ""
                opacity: root.autoMode === "" ? 1.0 : 0.45
                title: "音频编码"
                subtitle: root.audioGroup ? root.audioGroup.label : "先选左侧档位"
                muted: root.videoHasAudio
                items: root.audioCodecRows
                selectionKey: root.audioCodec
                allowNone: false
                emptyText: "先选左侧档位"
                onPicked: function (key) { root.audioCodec = key }
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borderSoft }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: Theme.sp4
            spacing: Theme.sp3

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.sp3

                AppIcon {
                    name: (root.resultId === "" && root.autoMode === "") ? "warning" : "completed"
                    size: 15
                    iconColor: (root.resultId === "" && root.autoMode === "") ? Theme.warning : Theme.success
                }
                Text {
                    Layout.fillWidth: true
                    text: {
                        if (root.resultId === "" && root.autoMode === "") return "请至少选择一个视频或音频格式"
                        if (root.autoMode !== "") return "将下载：" + root.autoLabel + "（自动选最优画质并合并）"
                        if (root.videoHasAudio && root.pickedVideo !== null)
                            return "将下载：" + root.brief(root.pickedVideo)
                                   + root.sizeOf(root.pickedVideo) + "（自带声音）"
                        var line = "将下载：" + root.resultLabel
                        if (root.totalBytes > 0) line += "　合计约 " + root.human(root.totalBytes)
                        return line
                    }
                    color: (root.resultId === "" && root.autoMode === "") ? Theme.warning : Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSmall
                    wrapMode: Text.Wrap
                    maximumLineCount: 2
                    lineHeight: 1.4
                }
            }

            AppCheckBox {
                id: mergeBox
                visible: root.needsBoth
                text: "自动合并音视频"
                checked: root.autoMerge
                onToggled: function (value) { root.autoMerge = value }
            }

            Text {
                Layout.fillWidth: true
                visible: root.needsBoth && !root.autoMerge
                text: "不合并时会分别保存画面和声音两个文件。"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsSmall
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                AppButton {
                    text: "取消"
                    variant: "secondary"
                    small: true
                    onClicked: root.close()
                }
                AppButton {
                    text: "确定"
                    small: true
                    enabled: root.resultId !== "" || root.autoMode !== ""
                    onClicked: {
                        if (root.autoMode !== "") {
                            root.picked({
                                "formatId": root.autoMode,
                                "label": root.autoLabel,
                                "autoTier": root.autoMode,
                                "autoMerge": true,
                                "videoId": "",
                                "audioId": "",
                                "videoLabel": "",
                                "audioLabel": ""
                            })
                            root.close()
                            return
                        }
                        root.picked({
                            "formatId": root.resultId,
                            "label": root.resultLabel,
                            "autoMerge": root.autoMerge,
                            "videoId": root.pickedVideo ? root.pickedVideo.formatId : "",
                            "audioId": root.needsBoth && root.pickedAudio
                                       ? root.pickedAudio.formatId : "",
                            "videoLabel": root.pickedVideo ? root.pickedVideo.label : "",
                            "audioLabel": root.pickedAudio ? root.pickedAudio.label : "",
                            /* 只选了音频 = 仅音频下载（按“音频格式”设置处理，默认保持原始） */
                            "audioOnly": root.pickedVideo === null && root.pickedAudio !== null
                        })
                        root.close()
                    }
                }
            }
        }
    }
}
