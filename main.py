from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import re
from typing import Optional

# ====================== 导入解析器（core/__init__.py 已导出所有） ======================
from .core import (
    BilibiliParser, GitParser, DouyinParser, ScreenshotParser,
    AcFunParser, WeiboParser, NGAParser, XHSparser, YoutubeParser
)


@register("linkanaly", "sheetung", "链接解析插件（支持 Bilibili 等 + 网页截图）", "1.6.3", "https://github.com/sheetung/LinkAnalyPlugin")
class LinkAnaly(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        
        # ==================== 给所有 Parser 提供 get_config() 兼容层 ====================
        def get_config(self_obj):
            cfg = config or getattr(context, "config", {}) or getattr(context, "plugin_config", {}) or {}
            return cfg
        self.get_config = get_config.__get__(self)
        
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
        
        # 初始化解析器
        self.bilibili_parser = BilibiliParser(self)
        self.git_parser = GitParser(self)
        self.douyin_parser = DouyinParser(self)
        self.screenshot_parser = ScreenshotParser(self)
        self.acfun_parser = AcFunParser(self)
        self.weibo_parser = WeiboParser(self)
        self.nga_parser = NGAParser(self)
        self.xhs_parser = XHSparser(self)
        self.youtube_parser = YoutubeParser(self)
        
        # ====================== 完全复制原插件 link_handlers ======================
        self.link_handlers = {}
        
        if self.enable_bilibili:
            self.link_handlers["bilibili"] = {
                "patterns": [r"www\.bilibili\.com/video/(BV\w+)", r"b23\.tv/(BV\w+)", r"www\.bilibili\.com/video/av(\d+)"],
                "handler": self.bilibili_parser.handle
            }
        
        if self.enable_github_gitee:
            self.link_handlers["github"] = {"patterns": [r"github\.com/([^/]+)/([^/?#]+)"], "handler": self.git_parser.handle_github}
            self.link_handlers["gitee"] = {"patterns": [r"gitee\.com/([^/]+)/([^/?#]+)"], "handler": self.git_parser.handle_gitee}
        
        if self.enable_douyin:
            self.link_handlers["douyin"] = {
                "patterns": [r"v\.douyin\.com/([^/]+)/", r"www\.douyin\.com/video/([^/]+)/"],
                "handler": self.douyin_parser.handle
            }
        
        if self.enable_acfun:
            self.link_handlers["acfun"] = {
                "patterns": [r"www\.acfun\.cn/v/(\w+)", r"acfun\.cn/v/(\w+)"],
                "handler": self.acfun_parser.handle
            }
        
        if self.enable_weibo:
            self.link_handlers["weibo"] = {
                "patterns": [r"weibo\.com/\d+/([a-zA-Z0-9]+)", r"sina\.weibo\.com/\d+/([a-zA-Z0-9]+)", r"weibo\.cn/\d+/([a-zA-Z0-9]+)"],
                "handler": self.weibo_parser.handle
            }
        
        if self.enable_nga:
            self.link_handlers["nga"] = {
                "patterns": [
                    r"nga\.178\.com/read\?tid=(\d+)", r"bbs\.nga\.cn/read\?tid=(\d+)", r"ngabbs\.com/read\?tid=(\d+)",
                    r"nga\.178\.com/thread-(\d+)-(\d+)-(\d+)\.html", r"bbs\.nga\.cn/thread-(\d+)-(\d+)-(\d+)\.html"
                ],
                "handler": self.nga_parser.handle
            }
        
        if self.enable_xhs:
            self.link_handlers["xhs"] = {
                "patterns": [
                    r"xhs\.com/notes/(\d+)", r"xiaohongshu\.com/notes/(\d+)",
                    r"xhs\.com/(explore|home)/(\d+)", r"xiaohongshu\.com/(explore|home)/(\d+)"
                ],
                "handler": self.xhs_parser.handle
            }
        
        if self.enable_youtube:
            self.link_handlers["youtube"] = {
                "patterns": [
                    r'www\.youtube\.com/watch\?v=([\w-]{11})', r'youtu\.be/([\w-]{11})', r'youtube\.com/shorts/([\w-]{11})'
                ],
                "handler": self.youtube_parser.handle
            }
        
        if self.screensnap_enabled:
            self.link_handlers["screenshot"] = {
                "patterns": [r"(https?://[^\s]+)"],
                "handler": self.screenshot_parser.handle
            }

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听所有消息，检测链接并解析"""
        msg = (event.message_str or "").strip()
        if not msg:
            return

        for platform in self.link_handlers.values():
            match = self._match_link(msg, platform["patterns"])
            if match:
                result: dict = await platform["handler"](match)
                
                if result.get("skip"):
                    continue
                
                # 发送图片（截图服务返回 URL）
                if result.get("image_url"):
                    yield event.image_result(result["image_url"])
                
                # 发送文字
                if result.get("message"):
                    yield event.plain_result(result["message"])
                
                # 阻止后续处理器（和原 Langbot 一致）
                event.stop_event()
                return

    def _match_link(self, msg: str, patterns: list) -> Optional[re.Match]:
        for pattern in patterns:
            if match := re.search(pattern, msg):
                return match
        return None
