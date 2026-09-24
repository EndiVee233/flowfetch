import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

/* 哔哩哔哩扫码登录 */
Popup {
    id: root

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: 380
    implicitHeight: box.implicitHeight + Theme.sp6 * 2
    modal: true
    focus: true
    padding: 0
    closePolicy: Popup.CloseOnEscape
    Overlay.modal: Rectangle { color: Theme.overlay }

    onOpened: backend.bilibili.startLogin()
    onClosed: backend.bilibili.cancelLogin()

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

    Connections {
        target: backend.bilibili
        function onLoginSucceeded(name) {
            successTimer.restart()
        }
    }

    Timer {
        id: successTimer
        interval: 1200
        onTriggered: root.close()
    }

    ColumnLayout {
        id: box
        anchors.fill: parent
        anchors.margins: Theme.sp6
        spacing: Theme.sp4

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.sp3
            Rectangle {
                Layout.preferredWidth: 38
                Layout.preferredHeight: 38
                radius: 11
                color: backend.bilibili.loggedIn
                       ? Qt.rgba(Theme.success.r, Theme.success.g, Theme.success.b, 0.16)
                       : Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.16)
                AppIcon {
                    anchors.centerIn: parent
                    name: backend.bilibili.loggedIn ? "completed" : "shield"
                    size: 19
                    iconColor: backend.bilibili.loggedIn ? Theme.success : Theme.accentText
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    Layout.fillWidth: true
                    text: backend.bilibili.loggedIn ? "登录成功" : "登录哔哩哔哩"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSubtitle
                    font.weight: Font.DemiBold
                }
                Text {
                    Layout.fillWidth: true
                    visible: backend.bilibili.loggedIn
                    text: backend.bilibili.statusText
                    color: Theme.textDim
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSmall
                }
            }
            IconButton {
                Layout.alignment: Qt.AlignTop
                iconName: "close"
                onClicked: root.close()
            }
        }

        // 二维码
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 214
            Layout.preferredHeight: 214
            radius: Theme.rLg
            color: "#FFFFFF"
            visible: !backend.bilibili.loggedIn

            Image {
                id: qrImage
                anchors.fill: parent
                anchors.margins: 8
                source: backend.bilibili.qrPath
                fillMode: Image.PreserveAspectFit
                smooth: false
                cache: false
                asynchronous: true
            }

            Column {
                anchors.centerIn: parent
                spacing: Theme.sp2
                visible: qrImage.status !== Image.Ready
                AppIcon {
                    anchors.horizontalCenter: parent.horizontalCenter
                    name: "sync"
                    size: 26
                    iconColor: "#7C5CFF"
                    spin: true
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "正在获取二维码…"
                    color: "#6B7280"
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSmall
                }
            }
        }

        Text {
            Layout.fillWidth: true
            visible: !backend.bilibili.loggedIn
            text: backend.bilibili.statusText
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fsBody
            font.weight: Font.DemiBold
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
        }

        Text {
            Layout.fillWidth: true
            visible: !backend.bilibili.loggedIn
            text: "登录后可以解析到 1080P 高码率、4K、8K、HDR 与 60fps 等画质。"
                  + "登录凭据只保存在本机，用于下载时携带 Cookies。"
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fsSmall
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            lineHeight: 1.45
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.sp2
            Item { Layout.fillWidth: true }

            AppButton {
                visible: !backend.bilibili.loggedIn
                text: "刷新二维码"
                iconName: "refresh"
                variant: "secondary"
                small: true
                onClicked: backend.bilibili.startLogin()
            }
            AppButton {
                visible: !backend.bilibili.loggedIn
                text: "取消"
                variant: "ghost"
                small: true
                onClicked: root.close()
            }
            AppButton {
                visible: backend.bilibili.loggedIn
                text: "完成"
                small: true
                onClicked: root.close()
            }
        }
    }
}
