import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

/* 关于页 */
Item {
    id: root

    readonly property var techs: [
        { name: "yt-dlp", desc: "下载引擎（" + backend.deps.ytdlpSourceText + "）",
          value: backend.deps.ytdlpVersion, tone: "normal" },
        { name: "Qt / PySide6", desc: "界面框架", value: "6.11", tone: "normal" },
        { name: "Python", desc: "运行时", value: backend.pythonVersion, tone: "normal" },
        { name: "FFmpeg", desc: backend.deps.ffmpegReady ? "音视频合并与转码" : "未安装，部分功能不可用",
          value: backend.deps.ffmpegReady ? backend.deps.ffmpegVersion : "未安装",
          tone: backend.deps.ffmpegReady ? "normal" : "warn" }
    ]

    readonly property var shortcuts: [
        { k: "Ctrl + V", d: "粘贴剪贴板中的链接" },
        { k: "Enter", d: "解析输入框中的链接" },
        { k: "Ctrl + 1 ~ 5", d: "切换左侧页面" },
        { k: "Ctrl + O", d: "打开保存位置" },
        { k: "F5", d: "重新解析当前链接" },
        { k: "Esc", d: "清除当前解析结果" }
    ]

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.sp6
        spacing: Theme.sp3

        Column {
            spacing: 3
            Text {
                text: "关于"
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsDisplay
                font.weight: Font.Bold
            }
            Text {
                text: "版本信息、运行环境与键盘快捷键。"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsLabel
            }
        }

        Flickable {
            id: flick
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width
            contentHeight: col.implicitHeight + 40
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: AppScrollBar { }

            ColumnLayout {
                id: col
                width: flick.width
                spacing: Theme.sp4

                // 品牌卡
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 152
                    radius: Theme.rXl
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.22) }
                        GradientStop { position: 0.62; color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.05) }
                        GradientStop { position: 1.0; color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.0) }
                    }
                    border.width: 1
                    border.color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.32)

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.sp6
                        spacing: Theme.sp5

                        Rectangle {
                            Layout.preferredWidth: 78
                            Layout.preferredHeight: 78
                            radius: 23
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: Theme.accentHover }
                                GradientStop { position: 1.0; color: Theme.accentPress }
                            }
                            AppIcon {
                                anchors.centerIn: parent
                                name: "download"
                                size: 38
                                iconColor: Theme.accentFg
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 6

                            RowLayout {
                                spacing: Theme.sp2
                                Text {
                                    text: backend.appName
                                    color: Theme.text
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fsDisplay + 2
                                    font.weight: Font.Bold
                                }
                                Rectangle {
                                    Layout.alignment: Qt.AlignVCenter
                                    width: verText.implicitWidth + 16
                                    height: 22
                                    radius: 7
                                    color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18)
                                    border.width: 1
                                    border.color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.45)
                                    Text {
                                        id: verText
                                        anchors.centerIn: parent
                                        text: "v" + backend.appVersion
                                        color: Theme.accentText
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.fsSmall
                                        font.weight: Font.DemiBold
                                    }
                                }
                            }

                            Text {
                                text: backend.appTagline
                                color: Theme.textDim
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fsLabel
                            }
                            Text {
                                Layout.fillWidth: true
                                text: "此应用程序为 yt-dlp 提供了一个图形用户界面。你的设备必须已安装 yt-dlp。"
                                      + "它支持 1800 多个站点，可批量下载播放列表，并可合并音视频、嵌入字幕与封面。"
                                color: Theme.textMuted
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fsLabel
                                wrapMode: Text.Wrap
                                lineHeight: 1.45
                            }
                        }
                    }
                }

                // 运行环境
                SectionCard {
                    title: "运行环境"
                    iconName: "devices"

                    Repeater {
                        model: root.techs
                        delegate: RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: Theme.sp4

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                Text {
                                    text: modelData.name
                                    color: Theme.text
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fsBody
                                }
                                Text {
                                    text: modelData.desc
                                    color: Theme.textMuted
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fsSmall
                                }
                            }

                            Text {
                                Layout.alignment: Qt.AlignVCenter
                                text: modelData.value
                                color: modelData.tone === "ok" ? Theme.success
                                       : (modelData.tone === "warn" ? Theme.warning : Theme.accentText)
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.fsLabel
                                font.weight: Font.DemiBold
                            }
                        }
                    }
                }

                // 快捷键（两列）
                SectionCard {
                    title: "快捷键"
                    iconName: "keyboard"

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: Theme.sp8
                        rowSpacing: Theme.sp3

                        Repeater {
                            model: root.shortcuts
                            delegate: RowLayout {
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: Theme.sp3

                                Text {
                                    Layout.fillWidth: true
                                    text: modelData.d
                                    color: Theme.textDim
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.fsLabel
                                    elide: Text.ElideRight
                                }
                                Rectangle {
                                    Layout.alignment: Qt.AlignVCenter
                                    width: Math.max(72, keyLabel.implicitWidth + 18)
                                    height: 26
                                    radius: Theme.rXs
                                    color: Theme.surfaceAlt
                                    border.width: 1
                                    border.color: Theme.border
                                    Text {
                                        id: keyLabel
                                        anchors.centerIn: parent
                                        text: modelData.k
                                        color: Theme.text
                                        font.family: "Cascadia Mono"
                                        font.pixelSize: Theme.fsSmall
                                    }
                                }
                            }
                        }
                    }
                }

                // 链接
                SectionCard {
                    title: "开源与致谢"
                    iconName: "star"

                    SettingRow {
                        label: "yt-dlp 项目主页"
                        hint: "此应用程序通过 yt-dlp 的公开接口完成下载"
                        AppButton {
                            text: "打开"
                            iconName: "openNew"
                            variant: "secondary"
                            small: true
                            onClicked: backend.openUrl("https://github.com/yt-dlp/yt-dlp")
                        }
                    }
                    SettingRow {
                        label: "配置文件位置"
                        hint: backend.dataDir
                        AppButton {
                            text: "打开"
                            iconName: "folder"
                            variant: "secondary"
                            small: true
                            onClicked: backend.openFolder(backend.dataDir)
                        }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: "yt-dlp 遵循 Unlicense 许可。请仅将此应用程序用于个人学习与合法备份，"
                          + "并遵守各站点的服务条款及当地法律法规。"
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fsSmall
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                }

                Item { Layout.preferredHeight: Theme.sp4 }
            }
        }
    }
}
