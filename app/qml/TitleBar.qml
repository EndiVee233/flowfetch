import QtQuick

/* 无边框窗口的自定义标题栏 */
Item {
    id: root

    property string title: "yt-dlp 图形用户界面"
    property string subtitle: ""
    property bool maximized: false

    signal minimizeRequested()
    signal toggleMaximizeRequested()
    signal closeRequested()
    signal updateClicked()

    implicitHeight: 48

    MouseArea {
        anchors.fill: parent
        anchors.rightMargin: 150
        acceptedButtons: Qt.LeftButton
        onPressed: {
            if (Window.window) Window.window.startSystemMove()
        }
        onDoubleClicked: root.toggleMaximizeRequested()
    }

    Row {
        anchors.left: parent.left
        anchors.leftMargin: 18
        anchors.verticalCenter: parent.verticalCenter
        spacing: 10

        Rectangle {
            width: 26
            height: 26
            radius: 8
            anchors.verticalCenter: parent.verticalCenter
            gradient: Gradient {
                GradientStop { position: 0.0; color: Theme.accentHover }
                GradientStop { position: 1.0; color: Theme.accentPress }
            }
            AppIcon {
                anchors.centerIn: parent
                name: "download"
                size: 14
                iconColor: Theme.accentFg
            }
        }

        Text {
            text: root.title
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fsLabel + 1
            font.weight: Font.DemiBold
            anchors.verticalCenter: parent.verticalCenter
        }

        Rectangle {
            id: versionPill
            visible: root.subtitle !== ""
            width: subtitleText.implicitWidth + (backend.deps.updateAvailable ? 34 : 16)
            height: 20
            radius: 6
            color: backend.deps.updateAvailable
                   ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18)
                   : Theme.surfaceAlt
            border.width: 1
            border.color: backend.deps.updateAvailable
                          ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.5)
                          : Theme.borderSoft
            anchors.verticalCenter: parent.verticalCenter

            Text {
                id: subtitleText
                anchors.centerIn: parent
                anchors.horizontalCenterOffset: backend.deps.updateAvailable ? -8 : 0
                text: root.subtitle
                color: backend.deps.updateAvailable ? Theme.accentText : Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsTiny
            }

            AppIcon {
                visible: backend.deps.updateAvailable
                name: "download"
                size: 11
                iconColor: Theme.accentText
                anchors.right: parent.right
                anchors.rightMargin: 7
                anchors.verticalCenter: parent.verticalCenter
            }

            MouseArea {
                anchors.fill: parent
                enabled: backend.deps.updateAvailable
                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: {
                    win.page = 3
                    backend.notify("info", "有可用更新",
                                   backend.deps.updateSummary + " 可供更新，请在“组件”分组中操作。")
                }
            }
        }
    }

    Row {
        anchors.right: parent.right
        anchors.top: parent.top
        height: parent.height

        WindowButton {
            iconName: "minimize"
            onClicked: root.minimizeRequested()
        }
        WindowButton {
            iconName: root.maximized ? "restore" : "maximize"
            onClicked: root.toggleMaximizeRequested()
        }
        WindowButton {
            iconName: "close"
            danger: true
            onClicked: root.closeRequested()
        }
    }
}
