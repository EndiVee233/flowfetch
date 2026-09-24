import QtQuick

/* 窗口级提示气泡。
   放在窗口根部而不是按钮内部，这样不会被列表的 clip 裁掉。 */
Item {
    id: tip
    z: 9999

    property Item target: null
    property string text: ""
    property bool shown: false

    function show(item, message) {
        target = item
        text = message
        delay.restart()
    }
    function hide() {
        delay.stop()
        shown = false
    }

    visible: shown && text !== "" && target !== null
    width: parent ? parent.width : 0
    height: parent ? parent.height : 0

    Timer {
        id: delay
        interval: 420
        onTriggered: tip.shown = (tip.text !== "" && tip.target !== null)
    }

    Rectangle {
        id: bubble
        visible: tip.visible
        width: label.implicitWidth + 20
        height: label.implicitHeight + 12
        radius: Theme.rSm
        color: Theme.dark ? "#2A3140" : "#232A38"
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.10)

        x: {
            if (!tip.target) return 0
            var p = tip.target.mapToItem(tip, tip.target.width / 2, 0)
            var maxX = (tip.width || 0) - width - 6
            return Math.max(6, Math.min(p.x - width / 2, maxX))
        }
        y: {
            if (!tip.target) return 0
            var p = tip.target.mapToItem(tip, 0, 0)
            var above = p.y - height - 6
            return above < 4 ? (p.y + tip.target.height + 6) : above
        }

        Text {
            id: label
            anchors.centerIn: parent
            text: tip.text
            color: "#E8EBF2"
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fsSmall
        }
    }
}
