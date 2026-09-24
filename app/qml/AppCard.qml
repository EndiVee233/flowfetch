import QtQuick
import QtQuick.Layouts

/* 卡片容器：内容由内部 ColumnLayout 自动排布 */
Rectangle {
    id: root

    default property alias content: column.data
    property real padding: Theme.sp4
    property bool interactive: false
    property bool highlighted: false
    property int radiusSize: Theme.rLg
    property color fillColor: Theme.surface
    property color borderColor: Theme.border
    readonly property alias column: column

    radius: radiusSize
    color: highlighted ? Theme.accentFaint : fillColor
    border.width: 1
    border.color: highlighted ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.5) : borderColor
    implicitHeight: column.implicitHeight + padding * 2
    implicitWidth: column.implicitWidth + padding * 2
    clip: true

    Behavior on color { ColorAnimation { duration: Theme.durBase } }
    Behavior on border.color { ColorAnimation { duration: Theme.durBase } }

    ColumnLayout {
        id: column
        x: root.padding
        y: root.padding
        width: Math.max(0, root.width - root.padding * 2)
        height: Math.max(0, root.height - root.padding * 2)
        spacing: Theme.sp3
    }
}
