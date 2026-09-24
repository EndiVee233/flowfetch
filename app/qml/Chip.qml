import QtQuick

/* 可选中的胶囊标签 */
Rectangle {
    id: root

    property string text: ""
    property string iconName: ""
    property bool selected: false
    property bool compact: false
    /* 需要登录等条件才能解锁的档位 */
    property bool locked: false
    /* 已选中时把图标换成「对勾」，用于「默认」这类需要一眼看出状态的项 */
    property bool checkWhenSelected: false

    signal clicked()

    /* locked 时锁图标优先；勾选态图标只在已选中时顶掉普通图标 */
    readonly property string shownIcon: {
        if (root.locked) return "lock"
        if (root.selected && root.checkWhenSelected) return "check"
        return root.iconName
    }

    implicitWidth: content.implicitWidth + (compact ? 20 : 26)
    implicitHeight: compact ? 26 : 32
    width: implicitWidth
    height: implicitHeight
    radius: height / 2

    color: selected && !locked
           ? (mouse.containsMouse ? Theme.accentHover : Theme.accent)
           : (mouse.containsMouse ? Theme.surfaceHover : Theme.surfaceAlt)
    border.width: 1
    border.color: locked
                  ? (mouse.containsMouse ? Theme.accent : Theme.borderSoft)
                  : (selected ? Theme.accent
                              : (mouse.containsMouse ? Theme.borderStrong : Theme.border))

    Behavior on color { ColorAnimation { duration: Theme.durFast } }
    Behavior on border.color { ColorAnimation { duration: Theme.durFast } }

    Row {
        id: content
        anchors.centerIn: parent
        spacing: 6

        AppIcon {
            visible: root.shownIcon !== ""
            name: root.shownIcon
            size: root.compact ? 13 : 15
            iconColor: root.locked ? Theme.accentText
                                   : (root.selected ? Theme.accentFg : Theme.textDim)
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            text: root.text
            color: root.locked
                   ? Qt.rgba(Theme.textMuted.r, Theme.textMuted.g, Theme.textMuted.b, 0.62)
                   : (root.selected ? Theme.accentFg : Theme.textDim)
            font.family: Theme.fontFamily
            font.pixelSize: root.compact ? Theme.fsSmall : Theme.fsLabel
            font.weight: root.selected ? Font.DemiBold : Font.Normal
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        /* 置灰（enabled: false）时不响应，避免「默认」生效期间被误点 */
        enabled: root.enabled
        onClicked: root.clicked()
    }
}
