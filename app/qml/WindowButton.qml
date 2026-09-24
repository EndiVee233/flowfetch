import QtQuick

/* 标题栏窗口按钮 */
Rectangle {
    id: root

    property string iconName: "close"
    property bool danger: false

    signal clicked()

    width: 46
    height: parent ? parent.height : 46
    color: mouse.containsMouse
           ? (danger ? "#E5484D" : (Theme.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.06)))
           : "transparent"

    Behavior on color { ColorAnimation { duration: Theme.durFast } }

    AppIcon {
        anchors.centerIn: parent
        name: root.iconName
        size: 12
        iconColor: (root.danger && mouse.containsMouse) ? "#FFFFFF" : Theme.textDim
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
