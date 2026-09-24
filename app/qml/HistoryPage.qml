import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

/* 历史记录页 */
Item {
    id: root

    property string keyword: ""
    property int pendingRow: -1
    property string pendingTitle: ""
    property string pendingFile: ""

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.sp6
        spacing: Theme.sp4

        RowLayout {
            Layout.fillWidth: true
            Column {
                spacing: 3
                Text {
                    text: "历史记录"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsDisplay
                    font.weight: Font.Bold
                }
                Text {
                    text: "共 " + backend.history.count + " 条记录，合计 "
                          + backend.history.summary.totalSize + "。"
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsLabel
                }
            }
            Item { Layout.fillWidth: true }

            AppTextField {
                Layout.preferredWidth: 220
                iconName: "search"
                placeholderText: "搜索标题"
                onTextChanged: root.keyword = text
            }

            AppButton {
                Layout.alignment: Qt.AlignVCenter
                text: "导出为 CSV…"
                iconName: "save"
                variant: "secondary"
                small: true
                enabled: backend.history.count > 0
                onClicked: {
                    var p = backend.pickFile("history")
                    if (p !== "") {
                        var r = backend.exportHistory(p)
                        backend.notify("success", "导出成功", r)
                    }
                }
            }

            AppButton {
                Layout.alignment: Qt.AlignVCenter
                text: "清除记录"
                iconName: "trash"
                variant: "dangerGhost"
                small: true
                enabled: backend.history.count > 0
                onClicked: clearConfirm.open()
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Column {
                anchors.centerIn: parent
                spacing: Theme.sp3
                visible: historyList.count === 0
                AppIcon {
                    anchors.horizontalCenter: parent.horizontalCenter
                    name: "history"
                    size: 40
                    iconColor: Theme.textMuted
                    opacity: 0.6
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "没有历史记录"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSubtitle
                    font.weight: Font.DemiBold
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "下载完成的项目会显示在此处。"
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsLabel
                }
            }

            ListView {
                id: historyList
                anchors.fill: parent
                visible: count > 0
                clip: true
                spacing: Theme.sp2
                model: backend.history
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: AppScrollBar { }

                delegate: Rectangle {
                    id: hrow
                    required property int index
                    required property string title
                    required property string uploader
                    required property string thumbnail
                    required property string filePath
                    required property string outputDir
                    required property string sizeText
                    required property string timeText
                    required property bool audioOnly
                    required property string url
                    required property string kind

                    width: historyList.width
                    height: visible ? 74 : 0
                    visible: root.keyword.trim() === ""
                             || title.toLowerCase().indexOf(root.keyword.trim().toLowerCase()) >= 0
                    radius: Theme.rMd
                    color: rowHover.containsMouse ? Theme.surfaceHover : Theme.surface
                    border.width: 1
                    border.color: Theme.border

                    Behavior on color { ColorAnimation { duration: Theme.durFast } }

                    MouseArea {
                        id: rowHover
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.NoButton
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.sp2
                        spacing: Theme.sp3

                        Rectangle {
                            Layout.preferredWidth: 88
                            Layout.preferredHeight: 50
                            radius: Theme.rSm
                            color: Theme.surfaceAlt
                            clip: true

                            Image {
                                id: hthumb
                                anchors.fill: parent
                                source: hrow.thumbnail
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: true
                                visible: status === Image.Ready
                            }
                            AppIcon {
                                anchors.centerIn: parent
                                visible: hthumb.status !== Image.Ready
                                name: hrow.audioOnly ? "volume" : "video"
                                size: 20
                                iconColor: Theme.textMuted
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            Text {
                                Layout.fillWidth: true
                                text: hrow.title
                                color: Theme.text
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fsBody
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                            Row {
                                spacing: Theme.sp3
                                Text {
                                    text: hrow.uploader
                                    color: Theme.textMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fsSmall
                                }
                                Text {
                                    text: hrow.timeText
                                    color: Theme.textMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fsSmall
                                }
                                Text {
                                    text: hrow.sizeText
                                    color: Theme.textDim
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fsSmall
                                }
                                Rectangle {
                                    visible: hrow.kind !== ""
                                    width: kindLabel.implicitWidth + 12
                                    height: 18
                                    radius: 4
                                    color: hrow.kind === "complete" ? Qt.rgba(Theme.success.r, Theme.success.g, Theme.success.b, 0.18)
                                          : hrow.kind === "video_only" ? Qt.rgba(Theme.info.r, Theme.info.g, Theme.info.b, 0.18)
                                          : Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.18)
                                    Text {
                                        id: kindLabel
                                        anchors.centerIn: parent
                                        text: hrow.kind === "complete" ? "完整"
                                              : hrow.kind === "video_only" ? "仅视频"
                                              : hrow.kind === "audio_only" ? "仅音频" : ""
                                        color: hrow.kind === "complete" ? Theme.success
                                              : hrow.kind === "video_only" ? Theme.info
                                              : Theme.warning
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fsTiny
                                        font.weight: Font.DemiBold
                                    }
                                }
                            }
                        }

                        Row {
                            spacing: 2
                            IconButton {
                                iconName: "folder"
                                tooltip: "打开所在文件夹"
                                onClicked: {
                                    if (hrow.filePath) backend.revealFile(hrow.filePath)
                                    else backend.openFolder(hrow.outputDir)
                                }
                            }
                            IconButton {
                                iconName: "link"
                                tooltip: "打开原链接"
                                onClicked: backend.openUrl(hrow.url)
                            }
                            IconButton {
                                iconName: "trash"
                                tooltip: "删除记录"
                                variant: "danger"
                                onClicked: {
                                    pendingRow = hrow.index
                                    pendingTitle = hrow.title
                                    pendingFile = hrow.filePath
                                    deleteConfirm.open()
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Popup {
        id: deleteConfirm
        parent: Overlay.overlay
        anchors.centerIn: parent
        modal: true
        width: 400
        padding: Theme.sp5
        Overlay.modal: Rectangle { color: Theme.overlay }
        background: Rectangle {
            radius: Theme.rLg
            color: Theme.popupBg
            border.width: 1
            border.color: Theme.borderStrong
        }
        ColumnLayout {
            anchors.fill: parent
            spacing: Theme.sp4
            Text {
                Layout.fillWidth: true
                text: "要删除这条记录吗？"
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsSubtitle
                font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                text: root.pendingTitle
                color: Theme.textDim
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsLabel
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
            AppCheckBox {
                id: alsoFile
                text: root.pendingFile !== "" ? "同时删除本地文件" : "同时删除本地文件（无文件）"
                enabled: root.pendingFile !== ""
                checked: false
            }
            Text {
                Layout.fillWidth: true
                visible: root.pendingFile === ""
                text: "这条记录没有对应的本地文件，只能删除历史记录。"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsSmall
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                AppButton {
                    text: "取消"
                    variant: "secondary"
                    small: true
                    onClicked: deleteConfirm.close()
                }
                AppButton {
                    text: alsoFile.checked ? "删除记录和文件" : "仅删除记录"
                    variant: "danger"
                    small: true
                    onClicked: {
                        var msg = backend.removeHistory(root.pendingRow, alsoFile.checked)
                        deleteConfirm.close()
                        backend.notify("success",
                                       alsoFile.checked ? "已删除记录和文件" : "已删除记录", msg)
                    }
                }
            }
        }
        onClosed: alsoFile.checked = false
    }

    Popup {
        id: clearConfirm
        parent: Overlay.overlay
        anchors.centerIn: parent
        modal: true
        Overlay.modal: Rectangle { color: Theme.overlay }
        width: 340
        padding: Theme.sp5
        background: Rectangle {
            radius: Theme.rLg
            color: Theme.popupBg
            border.width: 1
            border.color: Theme.borderStrong
        }
        ColumnLayout {
            anchors.fill: parent
            spacing: Theme.sp4
            Text {
                text: "要清除全部历史记录吗？"
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsSubtitle
                font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                text: "仅删除记录列表，已下载的文件不会受到影响。此操作无法撤销。"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsLabel
                wrapMode: Text.Wrap
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                AppButton {
                    text: "取消"
                    variant: "secondary"
                    small: true
                    onClicked: clearConfirm.close()
                }
                AppButton {
                    text: "清除"
                    variant: "danger"
                    small: true
                    onClicked: {
                        backend.history.clear()
                        clearConfirm.close()
                    }
                }
            }
        }
    }
}
