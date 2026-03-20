from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star
from astrbot.api import logger
import re
import httpx

class LinkAnalyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        logger.info("LinkAnalyPlugin 已加载 - 支持微博/NGA/小红书网页截图")

    # 自动监听所有消息，检测链接
    @filter.event_message_type(filter.EventMessageType.ALL)()
    async def handle_link(self, event: AstrMessageEvent):
        msg = event.get_message().strip()
        if not msg:
            return

        # 提取所有 URL
        urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', msg)
        
        for url in urls:
            url_lower = url.lower()
            if any(domain in url_lower for domain in [
                "xiaohongshu.com", 
                "nga.cn", 
                "bbs.nga.cn", 
                "weibo.com", 
                "weibo.cn"
            ]):
                logger.info(f"检测到目标链接: {url}")
                
                try:
                    screenshot_bytes = await self._take_screenshot(url)
                    if screenshot_bytes:
                        result = MessageEventResult()
                        result.message(f"网站截图 | {url}")
                        result.image(screenshot_bytes)  # 直接发送截图图片
                        event.set_result(result)
                        return  # 处理完一个就返回，避免重复
                    else:
                        event.set_result(MessageEventResult().message(f"网站截图 | {url}（截图生成失败）"))
                except Exception as e:
                    logger.error(f"截图失败 {url}: {str(e)}")
                    event.set_result(MessageEventResult().message(f"网站截图 | {url}（截图异常）"))

    async def _take_screenshot(self, url: str):
        """使用 ScreenshotSnap 免费 API 截图（无需 key，轻量稳定）"""
        api_url = "https://screenshotsnap.com/api/screenshot"
        params = {
            "url": url,
            "format": "png",
            "width": "1280",
            "height": "800",
            "full_page": "false",
            "wait": "2"  # 等待页面加载（对小红书/微博友好）
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(api_url, params=params)
            if resp.status_code == 200 and len(resp.content) > 1000:
                return resp.content  # 返回图片 bytes
            else:
                logger.error(f"API 返回状态码: {resp.status_code}")
                return None
