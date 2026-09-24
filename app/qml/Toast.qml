import QtQuick

/* 顶部提示条 */
Item {
    id: root
    z: 9000

    property string level: "info"     // info | success | warning | error
    property string title: ""
    property string message: ""
    property bool shown: false

    readonly property color tone: {
        switch (level) {
        case "success": return Theme.success
        case "warning": return Theme.warning
        case "error":   return Theme.danger
        default:        return Theme.accentText
        }
    }
    readonly property string glyph: {
        switch (level) {
        case "success": return "completed"
        case "warning": return "warning"
        case "error":   return "error"
        default:        return "info"
        }
    }

    function push(lv, t, msg) {
        level = lv; title = t; message = msg
        shown = true
        hideTimer.restart()
    }

    Timer { id: hideTimer; interval: 4200; onTriggered: root.shown = false }

    width: Math.min(430, parent ? parent.width - 48 : 430)
    height: card.implicitHeight
    anchors.horizontalCenter: parent ? parent.horizontalCenter : undefined
    anchors.top: parent ? parent.top : undefined
    anchors.topMargin: 58
    opacity: shown ? 1 : 0
    y: shown ? 0 : -18
    visible: opacity > 0.01

    Behavior on opacity { NumberAnimation { duration: Theme.durBase } }
    Behavior on y { NumberAnimation { duration: Theme.durSlow; easing.type: Easing.OutCubic } }

    Rectangle {
        id: card
        width: parent.width
        implicitHeight: content.implicitHeight + 24
        radius: Theme.rLg
        color: Theme.popupBg
        border.width: 1
        border.color: Qt.rgba(root.tone.r, root.tone.g, root.tone.b, 0.4)

        Rectangle {
            width: 3
            height: parent.height - 20
            radius: 2
            color: root.tone
            anchors.left: parent.left
            anchors.leftMargin: 8
            anchors.verticalCenter: parent.verticalCenter
        }

        Row {
            id: content
            anchors.fill: parent
            anchors.margins: 14
            anchors.leftMargin: 20
            spacing: 11

            AppIcon {
                name: root.glyph
                size: 19
                iconColor: root.tone
                anchors.verticalCenter: parent.verticalCenter
            }

            Column {
                width: content.width - 30
                spacing: 3
                anchors.verticalCenter: parent.verticalCenter

                Text {
                    text: root.title
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsBody
                    font.weight: Font.DemiBold
                    width: parent.width
                    elide: Text.ElideRight
                }
                Text {
                    visible: root.message !== ""
                    text: root.message
                    color: Theme.textDim
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsLabel
                    width: parent.width
                    wrapMode: Text.Wrap
                    maximumLineCount: 3
                    elide: Text.ElideRight
                }
            }
        }

        MouseArea {
            anchors.fill: parent
            onClicked: root.shown = false
            cursorShape: Qt.PointingHandCursor
        }
    }
}
