import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

/* 字幕选择：从解析结果里可用的语言里多选，并选择输出格式 */
Popup {
    id: root

    property var available: []        // 可用语言代码列表
    property var selected: []         // 当前已选语言代码列表
    property string format: "原始"     // 当前输出格式
    signal accepted(var langs, string format)

    readonly property var formats: ["原始", "srt", "vtt", "ass", "lrc"]

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: 440
    height: Math.min(560, (parent ? parent.height : 600) - 80)
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

    /* 打开时复制一份已选列表，供界面勾选，确定时回传 */
    onAboutToShow: {
        root._chosen = root.selected.slice()
        root._fmt = root.format !== "" ? root.format : "原始"
    }

    property var _chosen: []
    property string _fmt: "原始"

    function isOn(code) { return root._chosen.indexOf(code) >= 0 }
    function toggle(code) {
        var i = root._chosen.indexOf(code)
        if (i >= 0) root._chosen.splice(i, 1)
        else root._chosen.push(code)
        root._chosen = root._chosen.slice()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.sp5
        spacing: Theme.sp3

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.sp3
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    text: "字幕下载"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSubtitle
                    font.weight: Font.DemiBold
                }
                Text {
                    Layout.fillWidth: true
                    text: root.available.length > 0
                          ? "勾选要下载的字幕语言，可多选。"
                          : "该视频没有解析到可用的字幕语言。"
                    color: Theme.textMuted
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

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.sp1
            Text {
                text: "输出格式"
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsLabel
            }
            Flow {
                Layout.fillWidth: true
                spacing: Theme.sp2
                Repeater {
                    model: root.formats
                    delegate: Chip {
                        required property var modelData
                        text: modelData === "原始" ? "原始格式" : String(modelData).toUpperCase()
                        compact: true
                        selected: root._fmt === modelData
                        onClicked: root._fmt = modelData
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                text: root._fmt === "原始"
                      ? "保持网站提供的格式（YouTube 通常是 vtt）。"
                      : "下载后统一转换成 " + root._fmt.toUpperCase() + "，需要 FFmpeg。"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsTiny
                wrapMode: Text.Wrap
            }
        }

        RowLayout {
            visible: root.available.length > 0
            Layout.fillWidth: true
            spacing: Theme.sp2
            AppButton {
                text: "全选"
                variant: "ghost"
                small: true
                onClicked: root._chosen = root.available.slice()
            }
            AppButton {
                text: "清除"
                variant: "ghost"
                small: true
                onClicked: root._chosen = []
            }
            Item { Layout.fillWidth: true }
            Text {
                text: "已选 " + root._chosen.length + " 项"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsSmall
            }
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.available
            spacing: 2
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: AppScrollBar { }

            delegate: Rectangle {
                id: row
                required property var modelData
                width: ListView.view.width
                height: 40
                radius: Theme.rSm
                color: rowMouse.containsMouse ? Theme.surfaceHover : "transparent"

                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.toggle(row.modelData)
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.sp3
                    anchors.rightMargin: Theme.sp3
                    spacing: Theme.sp3

                    AppCheckBox {
                        checked: root.isOn(row.modelData)
                        onToggled: root.toggle(row.modelData)
                    }
                    Text {
                        Layout.fillWidth: true
                        text: row.modelData
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fsLabel
                    }
                }
            }
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
                enabled: root._chosen.length > 0
                onClicked: { root.accepted(root._chosen, root._fmt); root.close() }
            }
        }
    }
}
