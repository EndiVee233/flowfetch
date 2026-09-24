import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

/* 外部组件（FFmpeg / yt-dlp）的提示与进度对话框 */
Popup {
    id: root

    property string mode: "ask"        // ask | progress | update | error
    property string title: ""
    property string message: ""
    property string kind: "ffmpeg"
    property string detail: ""
    property string question: ""
    property bool detailClickable: false

    signal accepted()
    signal rejected()
    signal detailClicked()

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: 460
    implicitHeight: box.implicitHeight + Theme.sp6 * 2
    modal: true
    Overlay.modal: Rectangle { color: Theme.overlay }
    focus: true
    padding: 0
    closePolicy: root.mode === "progress" ? Popup.NoAutoClose
                                          : (Popup.CloseOnEscape | Popup.CloseOnPressOutside)

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
        id: box
        anchors.fill: parent
        anchors.margins: Theme.sp6
        spacing: Theme.sp3

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.sp3

            Rectangle {
                Layout.preferredWidth: 40
                Layout.preferredHeight: 40
                radius: 12
                color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.16)
                AppIcon {
                    anchors.centerIn: parent
                    name: root.kind === "ytdlp" ? "cloud" : "video"
                    size: 20
                    iconColor: Theme.accentText
                    spin: root.mode === "progress"
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    Layout.fillWidth: true
                    text: root.title
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSubtitle
                    font.weight: Font.DemiBold
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: root.message
            color: Theme.textDim
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fsBody
            wrapMode: Text.Wrap
            lineHeight: 1.45
        }

        Text {
            Layout.fillWidth: true
            visible: root.question !== ""
            text: root.question
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fsBody
            font.weight: Font.DemiBold
            wrapMode: Text.Wrap
            lineHeight: 1.45
        }

        Text {
            Layout.fillWidth: true
            visible: root.detail !== ""
            text: root.detail
            textFormat: Text.RichText
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fsSmall
            wrapMode: Text.Wrap
            lineHeight: 1.5
            onLinkActivated: root.detailClicked()
        }

        AppProgressBar {
            Layout.fillWidth: true
            visible: root.mode === "progress"
            value: backend.deps.busyPercent / 100
            barHeight: 6
        }

        Text {
            Layout.fillWidth: true
            visible: root.mode === "progress"
            text: backend.deps.busyMessage
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fsSmall
            elide: Text.ElideRight
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: Theme.sp2
            spacing: Theme.sp2

            Item { Layout.fillWidth: true }

            AppButton {
                visible: root.mode !== "progress"
                text: "取消"
                variant: "secondary"
                small: true
                onClicked: { root.close(); root.rejected() }
            }
            AppButton {
                visible: root.mode === "ask" || root.mode === "update"
                text: root.kind === "ytdlp" ? "更新" : "下载"
                iconName: "download"
                small: true
                onClicked: { root.accepted(); }
            }
            AppButton {
                visible: root.mode === "error"
                text: "确定"
                small: true
                onClicked: { root.close(); root.rejected() }
            }
        }
    }
}
