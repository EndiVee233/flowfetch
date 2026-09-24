import QtQuick
import QtQuick.Layouts

/* 设置项一行 */
RowLayout {
    id: root

    property string label: ""
    property string hint: ""
    default property alias control: slot.data

    Layout.fillWidth: true
    spacing: Theme.sp4

    ColumnLayout {
        id: labelCol
        Layout.fillWidth: true
        Layout.minimumWidth: 120
        Layout.preferredWidth: 300
        spacing: 2

        Text {
            text: root.label
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fsBody
        }
        Text {
            Layout.fillWidth: true
            visible: root.hint !== ""
            text: root.hint
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fsSmall
            wrapMode: Text.Wrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }
    }

    Item {
        Layout.fillWidth: true
        Layout.preferredWidth: 0
        Layout.minimumWidth: 0
        implicitHeight: 1
    }

    RowLayout {
        id: slot
        Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
        spacing: Theme.sp2
    }
}
