import QtQuick
import QtQuick.Controls

/* 文本输入框 */
TextField {
    id: control

    property string iconName: ""
    property string suffixText: ""
    property bool monospace: false

    placeholderTextColor: Theme.textMuted
    color: Theme.text
    selectionColor: Theme.accent
    selectedTextColor: Theme.accentFg
    font.family: monospace ? "Cascadia Mono" : Theme.fontFamily
    font.pixelSize: Theme.fsBody
    selectByMouse: true
    persistentSelection: true
    leftPadding: iconName === "" ? 12 : 36
    rightPadding: suffixText === "" ? 12 : 40
    topPadding: 9
    bottomPadding: 9
    implicitHeight: 38

    AppIcon {
        visible: control.iconName !== ""
        name: control.iconName
        size: 15
        iconColor: control.activeFocus ? Theme.accent : Theme.textMuted
        anchors.left: parent.left
        anchors.leftMargin: 12
        anchors.verticalCenter: parent.verticalCenter
    }

    Text {
        visible: control.suffixText !== ""
        text: control.suffixText
        anchors.right: parent.right
        anchors.rightMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fsLabel
    }

    background: Rectangle {
        radius: Theme.rSm + 1
        color: !control.enabled ? Theme.surfaceAlt
                                : (control.activeFocus ? Theme.inputBgFocus : Theme.inputBg)
        border.width: 1
        border.color: control.activeFocus
                      ? Theme.accent
                      : (control.hovered ? Theme.borderStrong : Theme.border)
        Behavior on border.color { ColorAnimation { duration: Theme.durFast } }
        Behavior on color { ColorAnimation { duration: Theme.durFast } }
    }
}
