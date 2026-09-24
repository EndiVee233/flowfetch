import QtQuick
import QtQuick.Layouts

/* 可调整顺序的优先级列表（画质 / 音质 / 编码） */
ColumnLayout {
    id: root

    property string title: ""
    property string hint: ""
    property var table: []        // [{value,label,vip}]
    property var order: []        // 已排序的 value 数组
    property string settingsKey: ""
    /* 会员标记的文案：哔哩哔哩叫「大会员」，YouTube 叫「会员」 */
    property string vipLabel: "大会员"

    signal move(int index, int delta)
    signal reset()

    Layout.fillWidth: true
    spacing: Theme.sp1

    function labelOf(value) {
        for (var i = 0; i < table.length; i++)
            if (String(table[i].value) === String(value)) return table[i].label
        return String(value)
    }
    function vipOf(value) {
        for (var i = 0; i < table.length; i++)
            if (String(table[i].value) === String(value)) return table[i].vip === true
        return false
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: Theme.sp2
        Text {
            text: root.title
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fsBody
            font.weight: Font.DemiBold
        }
        Item { Layout.fillWidth: true }
        IconButton {
            iconName: "refresh"
            iconSize: 13
            boxSize: 24
            tooltip: "恢复默认顺序"
            onClicked: root.reset()
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        Layout.topMargin: 2
        spacing: 3

        Repeater {
            model: root.order
            delegate: Rectangle {
                id: row
                required property var modelData
                required property int index

                Layout.fillWidth: true
                Layout.preferredHeight: 30
                radius: Theme.rXs
                color: rowHover.containsMouse ? Qt.rgba(Theme.accent.r, Theme.accent.g,
                                                        Theme.accent.b, 0.10)
                                              : Theme.surfaceAlt

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 9
                    anchors.rightMargin: 2
                    spacing: 4

                    Text {
                        Layout.fillWidth: true
                        text: root.labelOf(row.modelData)
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fsLabel
                        elide: Text.ElideRight
                    }

                    Rectangle {
                        visible: root.vipOf(row.modelData)
                        Layout.alignment: Qt.AlignVCenter
                        width: vipText.implicitWidth + 10
                        height: 16
                        radius: 5
                        color: Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.16)
                        Text {
                            id: vipText
                            anchors.centerIn: parent
                            text: root.vipLabel
                            color: Theme.warning
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsTiny
                        }
                    }

                    IconButton {
                        iconName: "chevronDown"
                        iconSize: 11
                        boxSize: 22
                        rotation: 180          // 旋转后指向上方
                        tint: row.index === 0 ? Theme.textMuted : Theme.textDim
                        tooltip: "上移"
                        enabled: row.index > 0
                        onClicked: root.move(row.index, -1)
                    }
                    IconButton {
                        iconName: "chevronDown"
                        iconSize: 11
                        boxSize: 22
                        tint: row.index === root.order.length - 1 ? Theme.textMuted : Theme.textDim
                        tooltip: "下移"
                        enabled: row.index < root.order.length - 1
                        onClicked: root.move(row.index, 1)
                    }
                }

                MouseArea {
                    id: rowHover
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.NoButton
                }
            }
        }
    }

    Text {
        Layout.fillWidth: true
        Layout.topMargin: 2
        visible: root.hint !== ""
        text: root.hint
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fsTiny
        wrapMode: Text.Wrap
    }
}
