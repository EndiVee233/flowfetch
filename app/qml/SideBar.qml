import QtQuick
import QtQuick.Layouts

/* 左侧导航栏 */
Item {
    id: root

    property int current: 0
    property bool compact: false
    property int activeCount: 0
    property int queueCount: 0
    property int pendingCount: 0
    property string speedText: "空闲"

    signal navigate(int index)

    implicitWidth: compact ? 70 : 214

    readonly property var items: [
        { icon: "download", label: "下载" },
        { icon: "queue",    label: "任务" },
        { icon: "history",  label: "历史记录" },
        { icon: "settings", label: "设置" },
        { icon: "info",     label: "关于" }
    ]

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.tint(Theme.sidebarBg, Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.05)) }
            GradientStop { position: 0.45; color: Theme.sidebarBg }
            GradientStop { position: 1.0; color: Theme.sidebarBg }
        }
    }

    Rectangle {
        width: 1
        height: parent.height
        anchors.right: parent.right
        color: Theme.border
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 18
        anchors.bottomMargin: 14
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        spacing: 4

        Repeater {
            model: root.items
            delegate: NavButton {
                required property var modelData
                required property int index
                Layout.fillWidth: true
                compact: root.compact
                iconName: modelData.icon
                label: modelData.label
                selected: root.current === index
                badge: index === 1 ? root.queueCount : 0
                onClicked: root.navigate(index)
            }
        }

        Item { Layout.fillHeight: true }

        // 底部状态卡
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.compact ? 44 : 78
            radius: Theme.rMd
            color: Theme.accentFaint
            border.width: 1
            border.color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.22)

            Column {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: 13
                anchors.rightMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4
                visible: !root.compact

                Row {
                    spacing: 7
                    AppIcon {
                        name: root.activeCount > 0 ? "bolt" : "check"
                        size: 13
                        iconColor: Theme.accentText
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: root.activeCount > 0
                              ? ("正在下载 " + root.activeCount + " 项"
                                 + (root.pendingCount > 0 ? " · " + root.pendingCount + " 排队" : ""))
                              : (root.pendingCount > 0 ? root.pendingCount + " 项排队中" : "当前空闲")
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fsLabel
                        font.weight: Font.DemiBold
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 20
                    visible: root.activeCount > 0
                    text: "总速度 " + root.speedText
                    color: Theme.textDim
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSmall
                }
            }

            AppIcon {
                anchors.centerIn: parent
                visible: root.compact
                name: root.activeCount > 0 ? "bolt" : "check"
                size: 16
                iconColor: Theme.accentText
            }
        }
    }
}
