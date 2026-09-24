import QtQuick
import "../app/qml"

/* 仅供 tools/downloadpagetest.py 使用的宿主窗口：
   真加载 DownloadPage，并补上它从主窗口继承的两个上下文（cfg / urlFieldUrl）。 */
Window {
    id: win
    width: 1000
    height: 760
    visible: true

    /* DownloadPage 用 win.cfg 读全局设置，用 win.urlFieldUrl 回写解析链接 */
    property var cfg: ({})
    property string urlFieldUrl: ""
    /* 捕获 startDownload / startBatch 收到的 spec，供测试断言 */
    property var lastSpec: null
    property var lastBatch: []

    DownloadPage {
        id: page
        objectName: "page"
        anchors.fill: parent
        onRequestQueue: win.queueRequests += 1
    }

    property int queueRequests: 0
}
