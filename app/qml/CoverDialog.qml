import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

/* 封面下载选项：是否下载，以及分辨率 */
Popup {
    id: root

    property string current: ""          // 当前选中的方式："none"/"original"/"640"/"320"
    signal accepted(string mode)

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: 380
    height: Math.min(440, (parent ? parent.height : 500) - 80)
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

    /* 打开时若没有显式选择，默认按“原图”处理 */
    onAboutToShow: if (root.current === "") root.current = "original"

    readonly property var options: [
        { mode: "none",     label: "不下载封面", desc: "本次下载不保存封面图" },
        { mode: "original", label: "原图",       desc: "按站点提供的原始分辨率下载" },
        { mode: "640",      label: "640 宽",     desc: "下载后缩放到宽度 640（保持比例）" },
        { mode: "320",      label: "320 宽",     desc: "下载后缩放到宽度 320（保持比例）" }
    ]

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
                    text: "封面下载"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSubtitle
                    font.weight: Font.DemiBold
                }
                Text {
                    Layout.fillWidth: true
                    text: "选择是否下载封面，以及封面的分辨率。"
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

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.options
            spacing: Theme.sp2
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: AppScrollBar { }

            delegate: Rectangle {
                id: row
                required property var modelData
                width: ListView.view.width
                height: 56
                radius: Theme.rMd
                color: root.current === row.modelData.mode
                       ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.14)
                       : (rowMouse.containsMouse ? Theme.surfaceHover : "transparent")

                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.current = row.modelData.mode
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.sp3
                    anchors.rightMargin: Theme.sp3
                    spacing: Theme.sp3

                    Rectangle {
                        Layout.preferredWidth: 16
                        Layout.preferredHeight: 16
                        radius: 8
                        color: "transparent"
                        border.width: root.current === row.modelData.mode ? 5 : 1.5
                        border.color: root.current === row.modelData.mode ? Theme.accent : Theme.borderStrong
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            text: row.modelData.label
                            color: root.current === row.modelData.mode ? Theme.accentText : Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsLabel
                            font.weight: root.current === row.modelData.mode ? Font.DemiBold : Font.Normal
                        }
                        Text {
                            text: row.modelData.desc
                            color: Theme.textMuted
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsSmall
                        }
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
                onClicked: { root.accepted(root.current); root.close() }
            }
        }
    }
}
