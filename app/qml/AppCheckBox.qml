import QtQuick

/* 复选框 */
Item {
    id: root

    property bool checked: false
    property string text: ""
    signal toggled(bool value)

    implicitHeight: 22
    implicitWidth: box.width + (text === "" ? 0 : label.implicitWidth + 9)
    height: implicitHeight
    width: implicitWidth
    opacity: root.enabled ? 1 : 0.45

    Rectangle {
        id: box
        width: 18
        height: 18
        radius: 5
        anchors.verticalCenter: parent.verticalCenter
        color: root.checked ? Theme.accent : (mouse.containsMouse ? Theme.surfaceHover : "transparent")
        border.width: root.checked ? 0 : 1.5
        border.color: mouse.containsMouse ? Theme.borderStrong : Theme.border
        Behavior on color { ColorAnimation { duration: Theme.durFast } }

        AppIcon {
            anchors.centerIn: parent
            name: "check"
            size: 12
            iconColor: Theme.accentFg
            opacity: root.checked ? 1 : 0
            scale: root.checked ? 1 : 0.6
            Behavior on opacity { NumberAnimation { duration: Theme.durFast } }
            Behavior on scale { NumberAnimation { duration: Theme.durFast; easing.type: Easing.OutBack } }
        }
    }

    Text {
        id: label
        visible: root.text !== ""
        text: root.text
        anchors.left: box.right
        anchors.leftMargin: 9
        anchors.verticalCenter: parent.verticalCenter
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fsBody
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        enabled: root.enabled
        onClicked: root.toggled(!root.checked)
    }
}
