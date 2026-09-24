import QtQuick

/* 基于 Segoe Fluent Icons 的矢量图标 */
Text {
    id: root

    property string name: ""
    property real size: 18
    property color iconColor: Theme.text
    property bool spin: false

    text: Theme.icon(name)
    font.family: Theme.iconFamily
    font.pixelSize: Math.round(size)
    color: enabled ? iconColor : Theme.textMuted
    horizontalAlignment: Text.AlignHCenter
    verticalAlignment: Text.AlignVCenter
    renderType: Text.QtRendering
    antialiasing: true
    opacity: enabled ? 1.0 : 0.45

    transformOrigin: Item.Center
    /* 旋转属于循环动画，同样受“启用界面动画”开关控制 */
    RotationAnimator on rotation {
        running: root.spin && Theme.animationsOn
        loops: Animation.Infinite
        from: 0
        to: 360
        duration: 1200
    }
}
