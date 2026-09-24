import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

/* 任务队列页 */
Item {
    id: root

    property var stats: ({})
    property string filter: "all"     // all | active | done | failed
    property string expandedId: ""

    Timer {
        interval: 700
        running: true
        repeat: true
        onTriggered: root.refresh()
    }

    // 仅用于截图/测试：把队列列表滚动到指定位置
    // （ListView 首次布局会重置 contentY，所以延迟到布局完成后再设置）
    Timer {
        interval: 600
        running: backend.demoScrollY > 0
        repeat: false
        onTriggered: taskList.contentY = backend.demoScrollY
    }

    function refresh() { root.stats = backend.stats() }

    function visibleCount() {
        var n = 0
        for (var i = 0; i < taskList.count; i++) n++
        return n
    }

    function matches(status) {
        if (filter === "all") return true
        if (filter === "active") return status === "downloading" || status === "queued"
                                   || status === "processing" || status === "analyzing"
                                   || status === "paused"
        if (filter === "done") return status === "completed"
        if (filter === "failed") return status === "failed" || status === "canceled"
        return true
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.sp6
        spacing: Theme.sp4

        // ── 标题与统计 ─────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.sp4

            Column {
                spacing: 3
                Text {
                    text: "任务"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsDisplay
                    font.weight: Font.Bold
                }
                Text {
                    text: (root.stats.total > 0
                           ? ("共 " + root.stats.total + " 个任务，其中 "
                              + (root.stats.active || 0) + " 个正在下载、"
                              + (root.stats.queued || 0) + " 个在等待"
                              + ((root.stats.paused || 0) > 0
                                 ? "、" + root.stats.paused + " 个已暂停。" : "。"))
                           : "当前没有任务。")
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsLabel
                }
            }

            Item { Layout.fillWidth: true }

            AppButton {
                Layout.alignment: Qt.AlignVCenter
                text: "清除已完成的任务"
                iconName: "trash"
                variant: "secondary"
                small: true
                enabled: root.stats.total > 0
                onClicked: backend.clearFinished()
            }

            AppButton {
                Layout.alignment: Qt.AlignVCenter
                text: "全部取消"
                iconName: "close"
                variant: "dangerGhost"
                small: true
                enabled: root.stats.active > 0 || root.stats.queued > 0
                         || root.stats.paused > 0
                onClicked: backend.cancelAll()
            }
        }

        // ── 过滤 ───────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.sp2

            Repeater {
                model: [
                    { key: "all",    label: "全部" },
                    { key: "active", label: "进行中（含排队）" },
                    { key: "done",   label: "已完成" },
                    { key: "failed", label: "已失败" }
                ]
                delegate: Chip {
                    required property var modelData
                    text: modelData.label
                    compact: true
                    selected: root.filter === modelData.key
                    onClicked: root.filter = modelData.key
                }
            }

            Item { Layout.fillWidth: true }

            Text {
                visible: taskList.count === 0
                text: ""
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsLabel
            }
        }

        // ── 列表 ───────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Column {
                anchors.centerIn: parent
                spacing: Theme.sp3
                visible: taskList.count === 0
                AppIcon {
                    anchors.horizontalCenter: parent.horizontalCenter
                    name: "queue"
                    size: 40
                    iconColor: Theme.textMuted
                    opacity: 0.6
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "任务列表为空"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSubtitle
                    font.weight: Font.DemiBold
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "请转到“下载”页面添加任务。"
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsLabel
                }
            }

            ListView {
                id: taskList
                anchors.fill: parent
                visible: count > 0
                clip: true
                spacing: Theme.sp2
                model: backend.tasks
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: AppScrollBar { }
                cacheBuffer: 800

                delegate: TaskRow {
                    width: taskList.width
                    visible: root.matches(status)
                    height: visible ? implicitHeight : 0
                    expanded: root.expandedId === taskId
                    onToggleExpand: root.expandedId = (root.expandedId === taskId ? "" : taskId)
                    onAct: function (action) { root.handleAction(taskId, action) }
                }
            }
        }
    }

    function handleAction(taskId, action) {
        switch (action) {
        case "cancel": backend.cancelTask(taskId); break
        case "retry":  backend.retryTask(taskId); break
        case "pause":  backend.pauseTask(taskId); break
        case "resume": backend.resumeTask(taskId); break
        case "remove": backend.removeTask(taskId); break
        case "open":
            var d = backend.taskDetail(taskId)
            if (d.filepath) backend.revealFile(d.filepath)
            else if (d.outputDir) backend.openFolder(d.outputDir)
            break
        case "play":
            var dd = backend.taskDetail(taskId)
            if (dd.filepath) backend.openUrl(dd.filepath)
            break
        }
    }
}
