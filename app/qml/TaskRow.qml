import QtQuick
import QtQuick.Layouts

/* 队列中的单个任务卡片 */
Rectangle {
    id: root

    required property string taskId
    required property string title
    required property string uploader
    required property string thumbnail
    required property string status
    required property string statusText
    required property real progress
    required property string progressText
    required property string sizeText
    required property string speedText
    required property string etaText
    required property string error
    required property string errorKind
    required property string formatLabel
    required property string filePath
    required property string outputDir
    required property string playlistLabel
    required property bool audioOnly
    required property bool isActive

    property bool expanded: false
    signal act(string action)
    signal toggleExpand()

    readonly property bool running: status === "downloading" || status === "processing"
                                    || status === "analyzing"
    readonly property bool queued: status === "queued"
    readonly property bool finished: status === "completed"
    readonly property bool failed: status === "failed" || status === "canceled"

    implicitHeight: mainRow.implicitHeight + (expanded ? detailArea.implicitHeight + 12 : 0) + 24
    radius: Theme.rLg
    color: hover.containsMouse ? Theme.surfaceHover : Theme.surface
    border.width: 1
    border.color: running ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.34) : Theme.border

    Behavior on color { ColorAnimation { duration: Theme.durFast } }
    Behavior on border.color { ColorAnimation { duration: Theme.durBase } }

    MouseArea {
        id: hover
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.sp3
        spacing: 0

        RowLayout {
            id: mainRow
            Layout.fillWidth: true
            spacing: Theme.sp3

            // 缩略图
            Rectangle {
                Layout.preferredWidth: 96
                Layout.preferredHeight: 54
                Layout.alignment: Qt.AlignTop
                radius: Theme.rSm
                color: Theme.surfaceAlt
                clip: true

                Image {
                    id: thumb
                    anchors.fill: parent
                    source: root.thumbnail
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: true
                    visible: status === Image.Ready
                }

                AppIcon {
                    anchors.centerIn: parent
                    visible: thumb.status !== Image.Ready
                    name: root.audioOnly ? "volume" : "video"
                    size: 22
                    iconColor: Theme.textMuted
                }

                Rectangle {
                    visible: root.finished
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: 4
                    width: 18
                    height: 18
                    radius: 9
                    color: Theme.success
                    border.width: 2
                    border.color: Theme.surface
                    AppIcon {
                        anchors.centerIn: parent
                        name: "check"
                        size: 10
                        iconColor: "#04241A"
                    }
                }
            }

            // 主体
            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                spacing: 5

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.sp2

                    Text {
                        Layout.fillWidth: true
                        text: root.title
                        color: Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fsBody
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                        maximumLineCount: 1
                    }

                    Rectangle {
                        Layout.preferredWidth: pillText.implicitWidth + 16
                        Layout.preferredHeight: 21
                        radius: 7
                        color: Qt.rgba(Theme.statusColor(root.status).r,
                                       Theme.statusColor(root.status).g,
                                       Theme.statusColor(root.status).b, 0.15)
                        Text {
                            id: pillText
                            anchors.centerIn: parent
                            text: root.statusText
                            color: Theme.statusColor(root.status)
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.fsTiny
                            font.weight: Font.DemiBold
                        }
                    }
                }

                Row {
                    spacing: Theme.sp3
                    Text {
                        visible: root.formatLabel !== ""
                        text: root.formatLabel
                        color: Theme.textMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fsSmall
                    }
                    Text {
                        visible: root.playlistLabel !== ""
                        text: root.playlistLabel
                        color: Theme.textMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fsSmall
                    }
                }

                AppProgressBar {
                    Layout.fillWidth: true
                    Layout.topMargin: 1
                    value: root.failed ? 0 : root.progress
                    indeterminate: root.status === "analyzing" || root.status === "processing"
                    barColor: root.finished ? Theme.success
                              : (root.status === "paused" ? Theme.warning : Theme.accent)
                    trackColor: root.queued
                                ? Qt.rgba(1, 1, 1, Theme.dark ? 0.05 : 0.5)
                                : Theme.track
                    barHeight: 5
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.sp3

                    Text {
                        text: root.progressText
                        color: root.finished ? Theme.success : Theme.text
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fsSmall
                        font.weight: Font.DemiBold
                    }
                    Text {
                        visible: root.sizeText !== "—"
                        text: root.sizeText
                        color: Theme.textMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fsSmall
                    }
                    Text {
                        visible: root.running && root.speedText !== "—"
                        text: root.speedText
                        color: Theme.accentText
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fsSmall
                    }
                    Text {
                        visible: root.running && root.etaText !== "—"
                        text: "剩余 " + root.etaText
                        color: Theme.textMuted
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fsSmall
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        visible: root.error !== ""
                        text: root.errorKind !== "" ? root.errorKind : "下载失败"
                        color: Theme.danger
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fsSmall
                        elide: Text.ElideRight
                    }
                    Text {
                        visible: root.error !== ""
                        text: "查看原因"
                        color: Theme.accentText
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.fsSmall
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.toggleExpand()
                        }
                    }
                }
            }

            // 操作（固定宽度并右对齐，保证各卡片进度条与按钮右端都对齐）
            Item {
                Layout.alignment: Qt.AlignTop
                Layout.preferredWidth: 104
                Layout.maximumWidth: 104
                Layout.preferredHeight: 32
                implicitHeight: 32

                Row {
                    anchors.right: parent.right
                    anchors.top: parent.top
                    spacing: 2

                IconButton {
                    visible: root.status === "paused"
                    iconName: "play"
                    tooltip: "继续下载（自动断点续传）"
                    onClicked: root.act("resume")
                }
                IconButton {
                    visible: (root.running || root.queued) && root.status !== "paused"
                    iconName: "pause"
                    tooltip: "暂停（继续时自动断点续传）"
                    onClicked: root.act("pause")
                }
                IconButton {
                    visible: root.queued || root.running || root.status === "paused"
                    iconName: "close"
                    tooltip: "取消任务"
                    onClicked: root.act("cancel")
                }
                IconButton {
                    visible: root.finished
                    iconName: "folder"
                    tooltip: "打开所在文件夹"
                    onClicked: root.act("open")
                }
                IconButton {
                    visible: root.finished
                    iconName: "play"
                    tooltip: "播放文件"
                    onClicked: root.act("play")
                }
                IconButton {
                    visible: root.failed
                    iconName: "refresh"
                    tooltip: "重新下载"
                    onClicked: root.act("retry")
                }
                IconButton {
                    visible: !root.running && !root.queued
                    iconName: "trash"
                    tooltip: "从列表移除"
                    variant: "danger"
                    onClicked: root.act("remove")
                }
                }
            }
        }

        // 详情
        Item {
            id: detailArea
            Layout.fillWidth: true
            Layout.leftMargin: 108
            implicitHeight: expanded ? detailCol.implicitHeight + 10 : 0
            clip: true
            visible: expanded

            Column {
                id: detailCol
                width: parent.width
                spacing: 5
                topPadding: 8

                Rectangle {
                    width: parent.width
                    height: 1
                    color: Theme.borderSoft
                }
                Text {
                    width: parent.width
                    text: root.error !== "" ? root.error : "该任务没有更多信息"
                    color: root.error !== "" ? Theme.danger : Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSmall
                    wrapMode: Text.Wrap
                }
                Text {
                    width: parent.width
                    visible: root.filePath !== ""
                    text: "文件位置：" + root.filePath
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSmall
                    elide: Text.ElideMiddle
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.act("open")
                    }
                }
            }
        }
    }
}
