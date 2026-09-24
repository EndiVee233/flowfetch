import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

/* 哔哩哔哩完整画质表 */
Popup {
    id: root

    property var available: []        // 当前视频真实可用的 qn
    property var unavailable: []      // 视频有、但当前账号拿不到的 qn
    property int currentQn: 0         // 界面当前选中的档位
    readonly property var tiers: backend.biliQualityTable()
    signal picked(int qn)

    // 自动挡用特殊 qn：-1 = 最高品质（自动），-2 = 最低品质（自动）
    readonly property int qnBest: -1
    readonly property int qnWorst: -2

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: 420
    height: Math.min(520, (parent ? parent.height : 600) - 80)
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

    readonly property bool hasData: available !== undefined && available !== null
                                     && available.length > 0
    readonly property bool accountLoggedIn: backend.bilibili.loggedIn
    readonly property bool accountVip: backend.bilibili.isVip

    function isAvailable(qn) {
        if (!root.hasData) return true       // 拿不到数据时不误判为不可用
        return root.available.indexOf(qn) >= 0
    }

    function inUnavailable(qn) {
        var list = root.unavailable
        if (!list || list.length === undefined) return false
        return list.indexOf(qn) >= 0
    }

    /* 每一档的真实状态：
         ok      当前账号确实能拿到
         login   需要先登录哔哩哔哩
         vip     需要大会员账号
         locked  视频有这一档，但当前账号拿不到（付费影片 / 地区限制等）
         none    视频根本没有这一档
       关键点：「视频没有」和「账号拿不到」是两回事，不能混为一谈。
       yt-dlp 会把「视频支持、但这次没拿到」的画质单独报出来，
       有那份名单才能分得清；名单为空就说明视频确实没有其余档位。 */
    function stateOf(qn) {
        if (!root.hasData) return "unknown"
        if (root.isAvailable(qn)) return "ok"
        if (!root.inUnavailable(qn)) return "none"
        if (!root.accountLoggedIn) return "login"
        return root.accountVip ? "locked" : "vip"
    }

    function stateText(state) {
        switch (state) {
        case "ok":     return "可用"
        case "login":  return "需要登录"
        case "vip":    return "需要大会员"
        case "locked": return "账号不可用"
        case "none":   return "视频无此画质"
        default:       return "未知"
        }
    }

    function reasonText(state) {
        switch (state) {
        case "login":  return "该画质需要先登录哔哩哔哩账号，请在设置里扫码登录。"
        case "vip":    return "该画质需要大会员账号。"
        case "locked": return "视频提供该画质，但当前账号无法下载：可能是付费影片、地区限制，或登录状态已失效。"
        default:       return "此视频未提供该画质。"
        }
    }

    ColumnLayout {
        id: box
        anchors.fill: parent
        anchors.margins: Theme.sp6
        spacing: Theme.sp3

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.sp3
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    text: "更多画质"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSubtitle
                    font.weight: Font.DemiBold
                }
                Text {
                    Layout.fillWidth: true
                    text: root.hasData
                          ? "每档右侧标注了真实原因：视频没有该画质，还是当前账号拿不到。"
                          : "尚未获取到该链接的可用画质，以下档位仅供参考。"
                    color: root.hasData ? Theme.textMuted : Theme.warning
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSmall
                    wrapMode: Text.Wrap
                }
            }
            IconButton {
                Layout.alignment: Qt.AlignTop
                iconName: "close"
                onClicked: root.close()
            }
        }

        Text {
            Layout.fillWidth: true
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
                selected: root.currentQn === root.qnBest
                onClicked: { root.picked(root.qnBest); root.close() }
            }
            Chip {
                text: "最低品质（自动）"
                compact: true
                selected: root.currentQn === root.qnWorst
                onClicked: { root.picked(root.qnWorst); root.close() }
            }
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.tiers
            spacing: 2
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: AppScrollBar { }

            delegate: Rectangle {
                id: row
                required property var modelData
                required property int index
                // 不要叫 state：那是 Item 自带的状态机属性
                readonly property string tierState: root.stateOf(modelData.value)
                readonly property bool ok: row.tierState === "ok"

                readonly property bool current: root.currentQn === row.modelData.value

                width: ListView.view.width
                height: 40
                radius: Theme.rSm
                color: current
                       ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.16)
                       : (rowMouse.containsMouse && ok ? Theme.surfaceHover : "transparent")

                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: row.ok ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: {
                        if (!row.ok) {
                            backend.notify(row.tierState === "none" ? "info" : "warning",
                                           row.modelData.label + " 不可用",
                                           root.reasonText(row.tierState))
                            return
                        }
                        root.picked(row.modelData.value)
                        root.close()
                    }
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.sp3
                    anchors.rightMargin: Theme.sp3
                    spacing: Theme.sp3

                    AppIcon {
                        name: row.tierState === "ok" ? "completed"
                              : (row.tierState === "none" ? "close" : "lock")
                        size: 14
                        iconColor: row.tierState === "ok" ? Theme.success
                                   : (row.tierState === "none" ? Theme.textDim : Theme.warning)
                    }
                    Text {
                        Layout.fillWidth: true
                        text: row.modelData.label + (row.current ? "　· 当前选择" : "")
                        color: row.ok ? (row.current ? Theme.accentText : Theme.text) : Theme.textMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fsLabel
                        font.weight: row.current ? Font.DemiBold : Font.Normal
                    }
                    Rectangle {
                        visible: row.modelData.vip === true
                        Layout.alignment: Qt.AlignVCenter
                        width: vipLabel.implicitWidth + 10
                        height: 17
                        radius: 5
                        color: Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.16)
                        Text {
                            id: vipLabel
                            anchors.centerIn: parent
                            text: "大会员"
                            color: Theme.warning
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsTiny
                        }
                    }
                    Text {
                        Layout.preferredWidth: 92
                        text: root.stateText(row.tierState)
                        color: row.tierState === "ok" ? Theme.success
                               : (row.tierState === "none" ? Theme.textMuted : Theme.warning)
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fsSmall
                        horizontalAlignment: Text.AlignRight
                    }
                }
            }
        }
    }
}
