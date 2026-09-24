import QtQuick
import QtQuick.Window

/* 方形图标按钮 */
Rectangle {
    id: root

    property string iconName: ""
    property string tooltip: ""
    property real iconSize: 16
    property int boxSize: 32
    property string variant: "ghost"
    property color tint: Theme.textDim

    signal clicked()

    width: boxSize
    height: boxSize
    radius: Theme.rSm
    color: {
        if (!root.enabled) return "transparent"
        if (variant === "danger") return mouse.containsMouse ? Qt.rgba(1, 0.45, 0.45, 0.16) : "transparent"
        return mouse.containsMouse ? Theme.surfaceHover : "transparent"
    }
    border.width: variant === "outline" ? 1 : 0
    border.color: Theme.border
    opacity: root.enabled ? 1 : 0.4

    readonly property bool hovered: mouse.containsMouse

    Behavior on color { ColorAnimation { duration: Theme.durFast } }

    AppIcon {
        anchors.centerIn: parent
        name: root.iconName
        size: root.iconSize
        iconColor: root.variant === "danger" && mouse.containsMouse ? Theme.danger : root.tint
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        enabled: root.enabled
        onClicked: root.clicked()
        onEntered: {
            if (root.tooltip === "") return
            var win = Window.window
            if (win && win.showTip) win.showTip(root, root.tooltip)
        }
        onExited: {
            var win = Window.window
            if (win && win.hideTip) win.hideTip()
        }
    }
}
