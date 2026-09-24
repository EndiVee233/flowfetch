import QtQuick

/* 侧边栏导航项 */
Rectangle {
    id: root

    property string iconName: ""
    property string label: ""
    property bool selected: false
    property bool compact: false
    property int badge: 0

    signal clicked()

    implicitHeight: 42
    height: 42
    radius: Theme.rSm + 1

    color: selected
           ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.15)
           : (mouse.containsMouse ? Theme.surfaceHover : "transparent")

    Behavior on color { ColorAnimation { duration: Theme.durFast } }

    /* 选中指示条：切换页面时纵向展开 / 收起，而不是硬切 */
    Rectangle {
        width: 3
        height: root.selected ? parent.height : parent.height * 0.3
        radius: 2
        color: Theme.accent
        opacity: root.selected ? 1 : 0
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter

        Behavior on height { NumberAnimation { duration: Theme.durBase; easing.type: Theme.ease } }
        Behavior on opacity { NumberAnimation { duration: Theme.durFast } }
    }

    Row {
        anchors.left: parent.left
        anchors.leftMargin: root.compact ? (parent.width - width) / 2 : 13
        anchors.verticalCenter: parent.verticalCenter
        spacing: 12

        AppIcon {
            name: root.iconName
            size: 17
            iconColor: root.selected ? Theme.accentText : Theme.textDim
            anchors.verticalCenter: parent.verticalCenter
        }

        Text {
            visible: !root.compact
            text: root.label
            color: root.selected ? Theme.text : Theme.textDim
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fsBody
            font.weight: root.selected ? Font.DemiBold : Font.Normal
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    Rectangle {
        visible: root.badge > 0 && !root.compact
        width: Math.max(20, badgeText.implicitWidth + 12)
        height: 19
        radius: 10
        color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.2)
        anchors.right: parent.right
        anchors.rightMargin: 11
        anchors.verticalCenter: parent.verticalCenter

        Text {
            id: badgeText
            anchors.centerIn: parent
            text: root.badge
            color: Theme.accentText
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fsSmall
            font.weight: Font.DemiBold
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
