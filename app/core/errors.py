"""把 yt-dlp 的英文报错翻译成用户看得懂的中文。

界面只展示友好说明与建议；原始报错仍然完整保留，
在任务详情里通过“查看原因”展开。
"""
from __future__ import annotations

import re
from typing import List, Tuple

# (匹配规则, 标题, 建议)
RULES: List[Tuple[re.Pattern, str, str]] = [
    (re.compile(r"ffmpeg|ffprobe", re.I),
     "缺少 FFmpeg 组件", "请在“设置 → 组件”中安装 FFmpeg 后再试。"),

    (re.compile(r"incomplete youtube id|looks truncated|is not a valid url|invalid url", re.I),
     "链接不完整", "看起来少复制了几个字符，请回到原页面重新复制完整链接。"),

    # 机器人风控：与是否登录无关，别把用户引去登录（登录也解决不了）
    (re.compile(r"not a bot|confirm you'?re not a bot|"
                r"page needs to be reloaded", re.I),
     "触发了站点的机器人检测",
     "站点把这次请求判定为自动化访问（常见于短时间多次访问同一站点）。"
     "这与是否登录无关：程序已自动携带访客凭据，稍等几分钟再试即可；"
     "若频繁遇到，可在“设置 → 访客 Cookie”中点“立即获取”换一份新的凭据。"),

    # 真正需要登录的内容（年龄限制、会员、需登录才可观看）
    (re.compile(r"age.?restricted|sign in to confirm|only available for registered|"
                r"login required|you need to log in|authentication|"
                r"may be inappropriate", re.I),
     "需要登录后才能访问",
     "请在“设置 → 账号登录”里登录一次，凭据会保存在本机并长期有效；"
     "也可以改用“设置 → 网络”中的 Cookies 文件。"),

    (re.compile(r"members.?only|premium|requires payment|purchase", re.I),
     "该内容仅限会员", "需要用已开通会员的账号登录后才能下载。"),

    (re.compile(r"private video|this video is private", re.I),
     "这是私享内容", "需要获得作者授权，或使用有权限的账号登录。"),

    (re.compile(r"video unavailable|is unavailable|removed by the uploader|"
                r"has been deleted|no longer available|content is not available", re.I),
     "内容不存在或已被删除", "请确认链接是否仍然有效。"),

    (re.compile(r"not available in your country|geo.?restrict|"
                r"blocked in your country|not available from your location", re.I),
     "当前地区无法访问", "该内容在所在地区不可用，可以尝试配置代理。"),

    (re.compile(r"http error 403|forbidden", re.I),
     "服务器拒绝了请求（403）", "可尝试在“设置 → 账号登录”中重新登录，或更换代理后再试。"),

    (re.compile(r"http error 404|\b404 not found|\bnot found\b(?!.*ffmpeg)", re.I),
     "资源不存在（404）", "内容可能已被删除或链接有误。"),

    (re.compile(r"http error 429|too many requests|rate.?limit", re.I),
     "请求过于频繁（429）", "请稍后再试，或在“设置 → 网络”中调低并发与限速。"),

    (re.compile(r"failed to resolve|getaddrinfo|name or service not known|"
                r"nodename nor servname|temporary failure in name resolution", re.I),
     "无法解析服务器地址", "请检查网络连接，或确认代理设置是否正确。"),

    (re.compile(r"connection refused|proxyerror|unable to connect to proxy|"
                r"cannot connect to proxy|connection reset", re.I),
     "无法建立连接", "代理可能未启动或地址有误，请检查“设置 → 网络”。"),

    (re.compile(r"timed out|timeout", re.I),
     "连接超时", "网络不稳定或代理较慢，可以在“设置 → 网络”中调大超时时间。"),

    (re.compile(r"certificate verify failed|ssl", re.I),
     "安全连接失败", "请检查代理设置与系统时间是否正确。"),

    (re.compile(r"unsupported url|no suitable extractor", re.I),
     "不支持这个链接", "该站点或链接形式暂不受支持，可以更新 yt-dlp 后再试。"),

    (re.compile(r"requested format is not available|no video formats found|"
                r"no formats found", re.I),
     "没有可用的下载格式", "请重新解析后选择其它格式，或先登录后再试。"),

    (re.compile(r"postprocessing", re.I),
     "后处理失败", "通常是 FFmpeg 相关的问题，可以在“设置 → 组件”中检查组件。"),

    (re.compile(r"permission denied|access is denied", re.I),
     "没有写入权限", "请更换保存位置，或检查该文件夹是否被其它程序占用。"),

    (re.compile(r"no space left|disk full", re.I),
     "磁盘空间不足", "请清理空间或更换保存位置。"),

    (re.compile(r"live event has ended", re.I),
     "直播已结束", "直播内容需要在其结束前录制。"),

    (re.compile(r"premieres in|will begin in", re.I),
     "内容尚未开播", "请等到首播开始后再试。"),

    (re.compile(r"playlist does not exist|playlist is empty", re.I),
     "播放列表为空或不存在", "请确认链接是否有效。"),
]


def describe(raw: str, fallback_title: str = "操作失败") -> Tuple[str, str]:
    """返回 (友好标题, 建议)。没有命中规则时只返回兜底标题。"""
    text = str(raw or "")
    for pattern, title, hint in RULES:
        if pattern.search(text):
            return title, hint
    return fallback_title, ""


def format_detail(raw: str, fallback_title: str = "操作失败") -> Tuple[str, str]:
    """返回 (友好标题, 完整详情)。详情里保留原始英文报错。"""
    title, hint = describe(raw, fallback_title)
    cleaned = str(raw or "").strip()
    parts = [title]
    if hint:
        parts.append(hint)
    if cleaned:
        parts.append("")
        parts.append("原始信息：")
        parts.append(cleaned)
    return title, "\n".join(parts)
