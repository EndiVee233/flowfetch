pragma Singleton
import QtQuick

QtObject {
    id: theme

    // ---------------------------------------------------------------
    // 可变状态
    // ---------------------------------------------------------------
    property bool dark: true
    property string accentKey: "violet"
    property real fontScale: 1.0
    property bool animationsOn: true
    property bool glassOn: true

    readonly property string fontFamily: backend ? backend.fontFamily : "Microsoft YaHei UI"
    readonly property string iconFamily: backend ? backend.iconFamily : "Segoe Fluent Icons"

    // ---------------------------------------------------------------
    // 主题色板
    // ---------------------------------------------------------------
    readonly property var darkPalette: ({
        bg0:        "#090C13",
        bg1:        "#101522",
        bg2:        "#0C1018",
        sidebarBg:  "#0B0F17",
        surface:    "#1E2534",
        surfaceAlt: "#262F41",
        surfaceHover: "#2E3749",
        inputBg:    "#0E131D",
        popupBg:    "#1F2634",
        border:     "#354055",
        borderSoft: "#2A3342",
        borderStrong: "#4C5A75",
        text:       "#EEF1F8",
        textDim:    "#BCC4D4",
        textMuted:  "#9AA5BA",
        overlay:    "#D9060810",
        shadow:     "#000000",
        track:      "#2B3345"
    })

    readonly property var lightPalette: ({
        bg0:        "#E9ECF5",
        bg1:        "#F9FAFD",
        bg2:        "#FFFFFF",
        sidebarBg:  "#F2F4FA",
        surface:    "#FFFFFF",
        surfaceAlt: "#F1F3FA",
        surfaceHover: "#E6EAF4",
        inputBg:    "#FFFFFF",
        popupBg:    "#FFFFFF",
        border:     "#DCE2EE",
        borderSoft: "#E9EDF6",
        borderStrong: "#C3CCDF",
        text:       "#12161F",
        textDim:    "#48505F",
        textMuted:  "#6E7889",
        overlay:    "#66151822",
        shadow:     "#8A93A6",
        track:      "#E1E6F0"
    })

    readonly property var pal: dark ? darkPalette : lightPalette

    readonly property color bg0: pal.bg0
    readonly property color bg1: pal.bg1
    readonly property color bg2: pal.bg2
    readonly property color sidebarBg: pal.sidebarBg
    readonly property color surface: pal.surface
    readonly property color surfaceAlt: pal.surfaceAlt
    readonly property color surfaceHover: pal.surfaceHover
    readonly property color inputBg: pal.inputBg
    readonly property color inputBgFocus: Qt.rgba(
        (pal.inputBg.r * 0.88 + accent.r * 0.12),
        (pal.inputBg.g * 0.88 + accent.g * 0.12),
        (pal.inputBg.b * 0.88 + accent.b * 0.12), 1.0)
    readonly property color popupBg: pal.popupBg
    readonly property color border: pal.border
    readonly property color borderSoft: pal.borderSoft
    readonly property color borderStrong: pal.borderStrong
    readonly property color text: pal.text
    readonly property color textDim: pal.textDim
    readonly property color textMuted: pal.textMuted
    readonly property color overlay: pal.overlay
    readonly property color shadow: pal.shadow
    readonly property color track: pal.track

    readonly property color success: dark ? "#3FD68C" : "#12A05C"
    readonly property color warning: dark ? "#F7BC4A" : "#C98209"
    readonly property color danger:  dark ? "#FF6F6F" : "#DC3B3B"
    readonly property color info:    dark ? "#5EA8FF" : "#2C6FE0"

    // ---------------------------------------------------------------
    // 强调色
    // ---------------------------------------------------------------
    /* base 用于填充与描边；text 是可在深色背景上安全阅读的同色系亮色 */
    readonly property var accentPalette: ({
        violet:  { base: "#7C5CFF", hover: "#8E72FF", press: "#6A48F0", text: "#AB97FF", fg: "#FFFFFF" },
        blue:    { base: "#3B82F6", hover: "#5A96F8", press: "#2C6FE0", text: "#74AAFF", fg: "#FFFFFF" },
        cyan:    { base: "#06B6D4", hover: "#22C7E2", press: "#0899B4", text: "#4FD6EC", fg: "#04202A" },
        emerald: { base: "#10B981", hover: "#2ACB95", press: "#0E9C6C", text: "#48D8A6", fg: "#04241A" },
        amber:   { base: "#F59E0B", hover: "#F8B02C", press: "#D98A05", text: "#FBC154", fg: "#2B1B02" },
        rose:    { base: "#F43F5E", hover: "#F75F79", press: "#DC2E4C", text: "#FF8199", fg: "#FFFFFF" }
    })

    readonly property var acc: accentPalette[accentKey] !== undefined ? accentPalette[accentKey] : accentPalette.violet

    readonly property color accent: acc.base
    readonly property color accentHover: acc.hover
    readonly property color accentPress: acc.press
    /* 用于文字与图标的强调色：深色主题下取更亮的同色系 */
    readonly property color accentText: dark ? acc.text : acc.base
    /* 强调色上的前景色。注意：属性名不能以 on 开头，否则会与 QML 信号处理器命名冲突。 */
    readonly property color accentFg: acc ? (acc.fg || "#FFFFFF") : "#FFFFFF"
    readonly property color accentSoft: Qt.rgba(accent.r, accent.g, accent.b, dark ? 0.16 : 0.12)
    readonly property color accentFaint: Qt.rgba(accent.r, accent.g, accent.b, dark ? 0.09 : 0.07)

    readonly property var accentKeys: ["violet", "blue", "cyan", "emerald", "amber", "rose"]
    readonly property var accentNames: ({
        violet: "紫罗兰", blue: "深海蓝", cyan: "青碧",
        emerald: "翡翠绿", amber: "琥珀金", rose: "玫瑰红"
    })

    // ---------------------------------------------------------------
    // 尺寸
    // ---------------------------------------------------------------
    readonly property int rXs: 6
    readonly property int rSm: 8
    readonly property int rMd: 10
    readonly property int rLg: 14
    readonly property int rXl: 18
    readonly property int rFull: 999

    readonly property int sp1: 4
    readonly property int sp2: 8
    readonly property int sp3: 12
    readonly property int sp4: 16
    readonly property int sp5: 20
    readonly property int sp6: 24
    readonly property int sp8: 32

    function fs(px) { return Math.round(px * fontScale) }

    readonly property int fsTiny: fs(11)
    readonly property int fsSmall: fs(12)
    readonly property int fsBody: fs(14)
    readonly property int fsLabel: fs(13)
    readonly property int fsSubtitle: fs(16)
    readonly property int fsTitle: fs(20)
    readonly property int fsDisplay: fs(25)

    // ---------------------------------------------------------------
    // 动画
    // ---------------------------------------------------------------
    /* 所有动画时长都由 animationsOn 控制：关闭动画时一律为 0，
       界面上的过渡会退化成瞬时切换，新增动画也要使用这里的属性。 */
    readonly property int durFast: animationsOn ? 120 : 0
    readonly property int durBase: animationsOn ? 200 : 0
    readonly property int durSlow: animationsOn ? 320 : 0
    /* 窗口启动 / 退出比其他过渡慢一些，让进出更从容 */
    readonly property int durIntro: animationsOn ? 340 : 0
    readonly property int durExit: animationsOn ? 260 : 0
    readonly property int ease: Easing.OutCubic
    readonly property int easeIn: Easing.InCubic

    // ---------------------------------------------------------------
    // 图标（Segoe Fluent Icons，已逐个校验）
    // ---------------------------------------------------------------
    readonly property var icons: ({
        download:   "\uE896",
        queue:      "\uE8FD",
        history:    "\uE81C",
        settings:   "\uE713",
        info:       "\uE946",
        home:       "\uE80F",
        folder:     "\uE8B7",
        paste:      "\uE77F",
        play:       "\uE768",
        pause:      "\uE769",
        refresh:    "\uE72C",
        trash:      "\uE74D",
        copy:       "\uE8C8",
        video:      "\uE714",
        globe:      "\uE774",
        star:       "\uE734",
        check:      "\uE73E",
        clock:      "\uE823",
        link:       "\uE71B",
        search:     "\uE721",
        warning:    "\uE7BA",
        chevronDown:"\uE70D",
        chevronRight:"\uE76C",
        close:      "\uE8BB",
        minimize:   "\uE921",
        maximize:   "\uE922",
        restore:    "\uE923",
        add:        "\uE710",
        more:       "\uE712",
        error:      "\uEA39",
        completed:  "\uE930",
        bolt:       "\uE945",
        volume:     "\uE8D6",
        shield:     "\uEA18",
        openNew:    "\uE8A7",
        grid:       "\uE80A",
        filter:     "\uE71C",
        document:   "\uE8A5",
        sync:       "\uE895",
        rename:     "\uE8AC",
        save:       "\uE74E",
        fullscreen: "\uE740",
        library:    "\uE8F1",
        view:       "\uE890",
        stopwatch:  "\uE916",
        cloud:      "\uE753",
        picture:    "\uEB9F",
        keyboard:   "\uE765",
        admin:      "\uE7EF",
        devices:    "\uE772",
        lock:       "\uE72E",
        unlock:     "\uE785"
    })

    function icon(name) {
        const v = icons[name]
        return v === undefined ? "" : v
    }

    function accentColor(key) {
        const a = accentPalette[key]
        return a === undefined ? accentPalette.violet.base : a.base
    }

    // ---------------------------------------------------------------
    // 状态颜色 / 文案
    // ---------------------------------------------------------------
    function statusColor(status) {
        switch (status) {
        case "completed": return success
        case "failed":    return danger
        case "canceled":  return textMuted
        case "paused":    return warning
        case "downloading":
        case "processing": return accentText
        case "analyzing": return info
        default:          return textDim
        }
    }

    function statusLabel(status) {
        switch (status) {
        case "queued":      return "排队中"
        case "analyzing":   return "解析中"
        case "downloading": return "下载中"
        case "processing":  return "处理中"
        case "paused":      return "已暂停"
        case "completed":   return "已完成"
        case "failed":      return "已失败"
        case "canceled":    return "已取消"
        default:            return status
        }
    }
}
