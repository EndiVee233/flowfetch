import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

/* 格式选择弹窗里的一列。
   行的内容由调用方给好（档位行或编码行），这里只负责显示与单选。 */
Item {
    id: root

    property string title: ""
    property string subtitle: ""
    property var items: []            // [{key, label, sub}]
    property string selectionKey: ""
    /* 提供「不使用」，并允许再点一次已选中的行来取消选择 */
    property bool allowNone: true
    /* 该栏当前不参与组合（例如所选视频已自带声音） */
    property bool muted: false
    property string emptyText: "没有匹配的格式"

    signal picked(string key)         // 空字符串表示“不使用”

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 40

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.sp4
                anchors.rightMargin: Theme.sp4
                spacing: Theme.sp2
                Text {
                    text: root.title
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsBody
                    font.weight: Font.DemiBold
                }
                Text {
                    Layout.fillWidth: true
                    text: root.muted ? "所选视频已自带声音" : root.subtitle
                    color: root.muted ? Theme.warning : Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSmall
                    elide: Text.ElideRight
                }
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borderSoft }

        /* 明确的“不使用这一栏”，比再点一次选中项更好发现 */
        Rectangle {
            id: noneRow
            visible: root.allowNone
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            color: root.selectionKey === ""
                   ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.14)
                   : (noneMouse.containsMouse ? Theme.surfaceHover : "transparent")

            MouseArea {
                id: noneMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.picked("")
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.sp3
                anchors.rightMargin: Theme.sp3
                spacing: Theme.sp2
                Rectangle {
                    Layout.preferredWidth: 16
                    Layout.preferredHeight: 16
                    radius: 8
                    color: "transparent"
                    border.width: root.selectionKey === "" ? 5 : 1.5
                    border.color: root.selectionKey === "" ? Theme.accent : Theme.borderStrong
                }
                Text {
                    Layout.fillWidth: true
                    text: "不使用"
                    color: root.selectionKey === "" ? Theme.accentText : Theme.textDim
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsLabel
                    font.weight: root.selectionKey === "" ? Font.DemiBold : Font.Normal
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.borderSoft
            visible: root.allowNone
        }

        ListView {
            id: view
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.items
            opacity: root.muted ? 0.45 : 1.0
            spacing: 1
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: AppScrollBar { }
            footer: Item { width: 1; height: 8 }

            delegate: Rectangle {
                id: row
                required property var modelData
                required property int index
                readonly property bool current: root.selectionKey !== ""
                                                 && String(root.selectionKey) === String(modelData.key)

                width: ListView.view.width
                height: 44
                color: current ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.16)
                               : (rowMouse.containsMouse ? Theme.surfaceHover : "transparent")

                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    // 再点一次已选中的行即取消选择（没有“不使用”的栏除外）
                    onClicked: root.picked(
                        (row.current && root.allowNone) ? "" : String(row.modelData.key))
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.sp3
                    anchors.rightMargin: Theme.sp3
                    spacing: Theme.sp2

                    /* 单选圆点 */
                    Rectangle {
                        Layout.preferredWidth: 16
                        Layout.preferredHeight: 16
                        radius: 8
                        color: "transparent"
                        border.width: row.current ? 5 : 1.5
                        border.color: row.current ? Theme.accent : Theme.borderStrong
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        Text {
                            Layout.fillWidth: true
                            text: row.modelData.label
                            color: row.current ? Theme.accentText : Theme.text
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsLabel
                            font.weight: row.current ? Font.DemiBold : Font.Normal
                            elide: Text.ElideRight
                        }
                        Text {
                            Layout.fillWidth: true
                            visible: (row.modelData.sub || "") !== ""
                            text: row.modelData.sub || ""
                            color: Theme.textMuted
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsTiny
                            elide: Text.ElideRight
                        }
                    }
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 34
            visible: view.count === 0
            Text {
                anchors.centerIn: parent
                text: root.emptyText
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsSmall
            }
        }
    }
}
