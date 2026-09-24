import QtQuick
import QtQuick.Layouts

/* 设置分组卡片，可折叠 */
ColumnLayout {
    id: root

    property string title: ""
    property string iconName: "settings"
    property bool collapsible: false
    property bool expanded: true
    default property alias content: box.data

    Layout.fillWidth: true
    spacing: Theme.sp2

    Item {
        Layout.fillWidth: true
        implicitHeight: 26

        Row {
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8

            AppIcon {
                name: root.iconName
                size: 14
                iconColor: Theme.accentText
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: root.title
                color: Theme.textDim
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsLabel
                font.weight: Font.DemiBold
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        Row {
            visible: root.collapsible
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6

            Text {
                text: root.expanded ? "收起" : "展开"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsSmall
                anchors.verticalCenter: parent.verticalCenter
            }
            AppIcon {
                name: "chevronDown"
                size: 12
                iconColor: Theme.textMuted
                rotation: root.expanded ? 180 : 0
                anchors.verticalCenter: parent.verticalCenter
                Behavior on rotation { NumberAnimation { duration: Theme.durBase; easing.type: Easing.OutCubic } }
            }
        }

        MouseArea {
            anchors.fill: parent
            enabled: root.collapsible
            cursorShape: root.collapsible ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: root.expanded = !root.expanded
        }
    }

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: box.implicitHeight + Theme.sp5 * 2
        visible: root.expanded || backend.demoExpandSections
        radius: Theme.rLg
        color: Theme.surface
        border.width: 1
        border.color: Theme.border

        ColumnLayout {
            id: box
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: Theme.sp5
            spacing: Theme.sp4
        }
    }
}
