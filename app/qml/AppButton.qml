import QtQuick

/* 通用按钮：primary / secondary / ghost / danger / success */
Rectangle {
    id: root

    property string text: ""
    property string iconName: ""
    property string variant: "primary"
    property bool small: false
    property bool block: false
    property bool busy: false

    signal clicked()

    implicitHeight: small ? 30 : 38
    implicitWidth: (block ? 0 : row.implicitWidth + (small ? 24 : 34))
    width: block ? parent.width : implicitWidth
    height: implicitHeight
    radius: Theme.rSm + 1

    readonly property bool hovered: mouse.containsMouse && root.enabled && !root.busy
    readonly property bool pressed: mouse.pressed && root.enabled && !root.busy

    readonly property color _fg: {
        if (!root.enabled) return Theme.textMuted
        if (variant === "primary") return Theme.accentFg
        if (variant === "danger") return "#FFFFFF"
        if (variant === "success") return Theme.dark ? "#05271A" : "#FFFFFF"
        if (variant === "dangerGhost") return hovered ? Theme.danger : Theme.textDim
        if (variant === "ghost") return hovered ? Theme.text : Theme.textDim
        return hovered ? Theme.text : Theme.textDim
    }

    color: {
        if (!root.enabled) return Theme.surfaceAlt
        if (variant === "primary") return pressed ? Theme.accentPress : (hovered ? Theme.accentHover : Theme.accent)
        if (variant === "secondary" && !root.enabled) return Theme.surfaceAlt
        if (variant === "danger") return pressed ? "#D93B3B" : (hovered ? "#FF8080" : Theme.danger)
        if (variant === "success") return pressed ? "#0E9C6C" : (hovered ? "#2ACB95" : Theme.success)
        if (variant === "secondary") return pressed ? Theme.surfaceHover : (hovered ? Theme.surfaceHover : Theme.surfaceAlt)
        if (variant === "dangerGhost")
            return hovered ? Qt.rgba(Theme.danger.r, Theme.danger.g, Theme.danger.b, 0.14) : "transparent"
        return pressed ? Theme.surfaceHover : (hovered ? Theme.surfaceAlt : "transparent")
    }

    border.width: (variant === "secondary" || variant === "ghost") ? 1 : 0
    border.color: (variant === "ghost" || variant === "dangerGhost") ? "transparent"
                                       : (root.enabled ? Theme.borderStrong : Theme.borderSoft)
    opacity: root.enabled ? 1.0 : 0.62
    scale: pressed ? 0.975 : 1.0

    Behavior on color { ColorAnimation { duration: Theme.durFast } }
    Behavior on scale { NumberAnimation { duration: Theme.durFast; easing.type: Theme.ease } }

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 7

        AppIcon {
            visible: root.iconName !== ""
            name: root.busy ? "sync" : root.iconName
            size: root.small ? 14 : 16
            iconColor: root._fg
            spin: root.busy
            anchors.verticalCenter: parent.verticalCenter
        }

        Text {
            visible: root.text !== ""
            text: root.text
            color: root._fg
            font.family: Theme.fontFamily
            font.pixelSize: root.small ? Theme.fsLabel : Theme.fsBody
            font.weight: Font.DemiBold
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        enabled: root.enabled && !root.busy
        onClicked: root.clicked()
    }
}
