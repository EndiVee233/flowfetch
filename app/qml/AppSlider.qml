import QtQuick
import QtQuick.Controls

/* 滑块 */
Slider {
    id: control

    implicitHeight: 26
    implicitWidth: 180
    from: 0
    to: 100
    stepSize: 1

    background: Rectangle {
        x: 0
        y: (control.height - height) / 2
        width: control.width
        height: 5
        radius: height / 2
        color: Theme.track

        Rectangle {
            width: control.visualPosition * parent.width
            height: parent.height
            radius: height / 2
            color: Theme.accent
        }
    }

    handle: Rectangle {
        x: control.visualPosition * (control.width - width)
        y: (control.height - height) / 2
        width: 16
        height: 16
        radius: 8
        color: Theme.dark ? "#FFFFFF" : Theme.accent
        border.width: 2
        border.color: Theme.accent
        scale: control.pressed ? 1.12 : 1.0
        Behavior on scale { NumberAnimation { duration: Theme.durFast } }
    }
}
