import QtQuick
import QtQuick.Controls
import "../app/qml"

/* 仅供 tools/fmtdlgtest.py 使用的宿主窗口 */
ApplicationWindow {
    id: win
    width: 1120
    height: 720
    visible: true
    title: "fmtdlgtest"

    property alias dialog: dialog
    property bool backendOk: backend !== null && backend !== undefined

    FormatDialog {
        id: dialog
        objectName: "dialog"
    }
}
