import QtQuick
import QtQuick.Controls

/* 细滚动条 */
ScrollBar {
    id: control

    policy: ScrollBar.AsNeeded
    padding: 2

    /* 内容超出可视区域（size < 1）或正在拖动时显示滑块 */
    readonly property bool overflowing: control.size > 0 && control.size < 0.999

    contentItem: Rectangle {
        implicitWidth: 6
        implicitHeight: 6
        radius: 3
        visible: control.active || control.overflowing
        color: (control.pressed || control.overflowing)
               ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.55)
               : (control.hovered ? Theme.borderStrong : Theme.border)
    }

    background: Item { }
}
