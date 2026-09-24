import QtQuick

/* 开关 */
Item {
    id: root

    property bool checked: false
    property bool busy: false
    signal toggled(bool value)

    implicitWidth: 44
    implicitHeight: 24
    width: 44
    height: 24
    opacity: root.enabled ? 1 : 0.45

    Rectangle {
        id: track
        anchors.fill: parent
        radius: height / 2
        color: root.checked ? Theme.accent : (mouse.containsMouse ? Theme.borderStrong : Theme.track)
        border.width: root.checked ? 0 : 1
        border.color: Theme.border
        Behavior on color { ColorAnimation { duration: Theme.durBase } }
    }

    Rectangle {
        id: knob
        width: 18
        height: 18
        radius: 9
        y: 3
        x: root.checked ? parent.width - width - 3 : 3
        color: root.checked ? Theme.accentFg : (Theme.dark ? "#9AA3B6" : "#FFFFFF")
        Behavior on x { NumberAnimation { duration: Theme.durBase; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }
        Behavior on color { ColorAnimation { duration: Theme.durBase } }
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
