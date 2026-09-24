import QtQuick

/* 进度条，支持确定 / 不确定 / 条纹动画 */
Item {
    id: root

    property real value: 0            // 0..1
    property bool indeterminate: false
    property bool striped: false
    property color barColor: Theme.accent
    property color trackColor: Theme.track
    property int barHeight: 6

    implicitHeight: barHeight
    height: barHeight

    Rectangle {
        id: track
        anchors.fill: parent
        radius: height / 2
        color: root.trackColor
        Behavior on color { ColorAnimation { duration: Theme.durBase } }
        clip: true

        Rectangle {
            id: fill
            visible: !root.indeterminate
            height: parent.height
            radius: height / 2
            width: Math.max(root.value > 0 ? height : 0, parent.width * Math.min(1, Math.max(0, root.value)))
            color: root.barColor
            Behavior on width { NumberAnimation { duration: Theme.durBase; easing.type: Easing.OutCubic } }
            Behavior on color { ColorAnimation { duration: Theme.durBase } }

            Rectangle {
                anchors.fill: parent
                radius: parent.radius
                visible: root.striped
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.16) }
                    GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.0) }
                    GradientStop { position: 1.0; color: Qt.rgba(1, 1, 1, 0.16) }
                }
                NumberAnimation on x { running: root.striped && Theme.animationsOn;
                                       from: -60; to: 60; duration: 900; loops: Animation.Infinite }
            }
        }

        Rectangle {
            id: indet
            visible: root.indeterminate
            height: parent.height
            width: parent.width * 0.32
            radius: height / 2
            color: root.barColor
            NumberAnimation on x {
                running: root.indeterminate && Theme.animationsOn
                from: -parent.width * 0.32
                to: parent.width
                duration: 1150
                loops: Animation.Infinite
            }
        }
    }
}
