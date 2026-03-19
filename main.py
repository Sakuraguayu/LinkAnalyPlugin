from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot import logger
import re
from typing import Optional, Any

# ====================== 导入解析器（core/__init__.py 已导出） ======================
from .core import (
    BilibiliParser, GitParser, DouyinParser, ScreenshotParser,
    AcFunParser, WeiboParser, NGAParser, XHSparser, YoutubeParser
)


@register("linkanaly", "sheetung", "链接解析插件（支持 Bilibili 等 + 网页截图）", "1.6.3", "https://github.com/sheetung/LinkAnalyPlugin")
class LinkAnaly(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
        # AstrBot 配置兼容层（让所有 Parser 的 self.plugin.get_config() 正常工作）
        def get_config(self):
            return getattr(context, "config", {}) or getattr(context, "plugin_config", {}) or {}
        self.get_config = get_config.__get__(self)  # 绑定到实例
        
        cfg = self.get_config()
        
        # 完全复制原插件默认值
        self.screensnap_enabled = cfg.get("screenshotsnap", False)
        self.enable_github_gitee = cfg.get("enable_github_gitee", True)
        self.enable_bilibili = cfg.get("enable_bilibili", True)
        self.enable_douyin = cfg.get("enable_douyin", True)
        self.enable_acfun = cfg.get("enable_acfun", True)
        self.enable_weibo = cfg.get("enable_weibo", False)
        self.enable_nga = cfg.get("enable_nga", False)
        self.enable_xhs = cfg.get("enable_xhs", False)
        self.enable_youtube = cfg.get("enable_youtube", True)
        
        # 初始化所有解析器（传 self，让 get_config 生效）
        self.bilibili_parser = BilibiliParser(self)
        self.git_parser = GitParser(self)
        self.douyin_parser = DouyinParser(self)
        self.screenshot_parser = ScreenshotParser(self)
        self.acfun_parser = AcFunParser(self)
        self.weibo_parser = WeiboParser(self)
        self.nga_parser = NGAParser(self)
        self.xhs_parser = XHSparser(self)
        self.youtube_parser = YoutubeParser(self)
        
        # ====================== 完全复制原插件的 link_handlers ======================
        self.link_handlers = {}
        
        if self.enable_bilibili:
            self.link_handlers["bilibili"] = {
                "patterns": [
                    r"www\.bilibili\.com/video/(BV\w+)",
                    r"b23\.tv/(BV\w+)",
                    r"www\.bilibili\.com/video/av(\d+)"
                ],
                "handler": self.bilibili_parser.handle
            }
        
        if self.enable_github_gitee:
            self.link_handlers["github"] = {
                "patterns": [r"github\.com/([^/]+)/([^/?#]+)"],
                "handler": self.git_parser.handle_github
            }
            self.link_handlers["gitee"] = {
                "patterns": [r"gitee\.com/([^/]+)/([^/?#]+)"],
                "handler": self.git_parser.handle_gitee
            }
        
        if self.enable_douyin:
            self.link_handlers["douyin"] = {
                "patterns": [
                    r"v\.douyin\.com/([^/]+)/",
                    r"www\.douyin\.com/video/([^/]+)/"
                ],
                "handler": self.douyin_parser.handle
            }
        
        if self.enable_acfun:
            self.link_handlers["acfun"] = {
                "patterns": [
                    r"www\.acfun\.cn/v/(\w+)",
                    r"acfun\.cn/v/(\w+)"
                ],
                "handler": self.acfun_parser.handle
            }
        
        if self.enable_weibo:
            self.link_handlers["weibo"] = {
                "patterns": [
                    r"weibo\.com/\d+/([a-zA-Z0-9]+)",
                    r"sina\.weibo\.com/\d+/([a-zA-Z0-9]+)",
                    r"weibo\.cn/\d+/([a-zA-Z0-9]+)"
                ],
                "handler": self.weibo_parser.handle
            }
        
        if self.enable_nga:
            self.link_handlers["nga"] = {
                "patterns": [
                    r"nga\.178\.com/read\?tid=(\d+)",
                    r"bbs\.nga\.cn/read\?tid=(\d+)",
                    r"ngabbs\.com/read\?tid=(\d+)",
                    r"nga\.178\.com/thread-(\d+)-(\d+)-(\d+)\.html",
                    r"bbs\.nga\.cn/thread-(\d+)-(\d+)-(\d+)\.html",
                    r"ngabbs\.com/thread-(\d+)-(\d+)-(\d+)\.html"
                ],
                "handler": self.nga_parser.handle
            }
        
        if self.enable_xhs:
            self.link_handlers["xhs"] = {
                "patterns": [
                    r"xhs\.com/notes/(\d+)",
                    r"xiaohongshu\.com/notes/(\d+)",
                    r"xhs\.com/(explore|home)/(\d+)",
                    r"xiaohongshu\.com/(explore|home)/(\d+)",
                    r"xiaohongshu\.com/discovery/item/(\w+)"
                ],
                "handler": self.xhs_parser.handle
            }
        
        if self.enable_youtube:
            self.link_handlers["youtube"] = {
                "patterns": [
                    r'www\.youtube\.com/watch\?v=([\w-]{11})',
                    r'youtu\.be/([\w-]{11})',
                    r'youtube\.com/shorts/([\w-]{11})'
                ],
                "handler": self.youtube_parser.handle
            }
        
        if self.screensnap_enabled:
            self.link_handlers["screenshot"] = {
                "patterns": [r"(https?://[^\s]+)"],
                "handler": self.screenshot_parser.handle
                # 最后加入 = 兜底（原插件逻辑）
            }

    @filter.on_message()
    async def on_message(self, event: AstrMessageEvent):
        msg = str(event.message_str or "").strip()

        for platform in self.link_handlers.values():
            match = self._match_link(msg, platform["patterns"])
            if match:
                result: dict = await platform["handler"](match)
                
                if result.get("skip"):
                    continue
                
                if result.get("success"):
                    # 发送图片（截图用 base64，B站用 url，YouTube 无图）
                    if result.get("image_url"):
                        await event.send_image(result["image_url"])
                    elif result.get("image_base64"):
                        await event.send_image(base64=result["image_base64"])
                    
                    await event.reply(result["message"])
                else:
                    await event.reply(result["message"])
                
                # 阻止后续处理器（原 prevent_default）
                event.stop_propagation()
                return

    # ====================== 原插件工具方法 ======================
    def _match_link(self, msg: str, patterns: list) -> Optional[re.Match]:
        for pattern in patterns:
            if match := re.search(pattern, msg):
                return match
        return None
