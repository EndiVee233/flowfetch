import QtQuick
import QtQuick.Controls

/* 下拉选择框 */
ComboBox {
    id: control

    property string iconName: ""
    property string prefix: ""

    implicitHeight: 38
    implicitWidth: 190
    font.family: Theme.fontFamily
    font.pixelSize: Theme.fsBody
    leftPadding: iconName === "" ? 12 : 34
    rightPadding: 32
    hoverEnabled: true

    contentItem: Text {
        leftPadding: control.leftPadding
        rightPadding: control.rightPadding
        text: control.displayText
        font: control.font
        color: control.enabled ? Theme.text : Theme.textMuted
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    AppIcon {
        visible: control.iconName !== ""
        name: control.iconName
        size: 15
        iconColor: Theme.textMuted
        anchors.left: parent.left
        anchors.leftMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        z: 2
    }

    indicator: AppIcon {
        name: "chevronDown"
        size: 13
        iconColor: Theme.textMuted
        x: control.width - width - 11
        y: (control.height - height) / 2
        rotation: control.popup.visible ? 180 : 0
        Behavior on rotation { NumberAnimation { duration: Theme.durBase; easing.type: Easing.OutCubic } }
    }

    background: Rectangle {
        radius: Theme.rSm + 1
        color: control.enabled ? Theme.inputBg : Theme.surfaceAlt
        border.width: 1
        border.color: control.popup.visible
                      ? Theme.accent
                      : (control.hovered ? Theme.borderStrong : Theme.border)
        Behavior on border.color { ColorAnimation { duration: Theme.durFast } }
    }

    delegate: ItemDelegate {
        id: item
        required property var model
        required property int index
        width: control.width - 8
        height: 34
        highlighted: control.highlightedIndex === index

        contentItem: Text {
            text: item.model[control.textRole] !== undefined ? item.model[control.textRole] : item.model
            color: item.highlighted ? Theme.accent : Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fsBody
            verticalAlignment: Text.AlignVCenter
            leftPadding: 8
            elide: Text.ElideRight
        }

        background: Rectangle {
            radius: Theme.rXs
            color: item.highlighted ? Theme.accentFaint : "transparent"
        }
    }

    popup: Popup {
        y: control.height + 5
        width: control.width
        implicitHeight: Math.min(contentItem.implicitHeight + 10, 320)
        padding: 5

        background: Rectangle {
            radius: Theme.rSm + 2
            color: Theme.popupBg
            border.width: 1
            border.color: Theme.border
        }

        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            boundsBehavior: Flickable.StopAtBounds

            ScrollIndicator.vertical: ScrollIndicator { }
        }

        enter: Transition {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.durFast }
            NumberAnimation { property: "scale"; from: 0.97; to: 1; duration: Theme.durFast; easing.type: Easing.OutCubic }
        }
        exit: Transition {
            NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.durFast }
        }
    }
}
