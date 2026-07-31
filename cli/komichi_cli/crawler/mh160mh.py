"""漫画160 (mh160mh.com) 爬虫

基于 qingtiancms 模板的静态详情页：
- 作品详情: https://www.mh160mh.com/kanmanhua/<id>/
- 章节页:   https://www.mh160mh.com/kanmanhua/<id>/<chapter_id>.html

注：该站站内搜索端点（/statics/searchelxt1e1.aspx）已失效（404），
    因此仅支持 URL 导入；关键词导入会抛出 SourceNotFound 触发换备。
"""
from __future__ import annotations

import re
from typing import List, Optional

import httpx
from parsel import Selector

from .base import BaseCrawler, ChapterInfo, SourceNotFound, SourceUnavailable, WorkInfo
from .registry import register_source

BASE_URL = "https://www.mh160mh.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Referer": BASE_URL + "/",
}

CHAPTER_RE = re.compile(r"/kanmanhua/[^/]+/(\d+)\.html")

STATUS_MAP = {
    "连载中": "ongoing",
    "连载": "ongoing",
    "更新中": "ongoing",
    "完结": "completed",
    "已完结": "completed",
    "全本": "completed",
}


@register_source
class Mh160mhCrawler(BaseCrawler):
    """漫画160 爬虫：爬取封面 URL + 章节名称，不下载图片"""

    name = "mh160mh"
    display_name = "漫画160 (mh160mh.com)"
    domains = ["mh160mh.com"]

    def crawl(self) -> WorkInfo:
        src = self.source.strip()
        if not src.lower().startswith(("http://", "https://")):
            raise SourceNotFound(
                f"「{src}」: mh160mh.com 站内搜索不可用（该站已关闭搜索功能），"
                f"请改用漫画 URL 导入。\n"
                f"例如: komichi-cli import https://www.mh160mh.com/kanmanhua/94/"
            )
        return self._parse_detail(src)

    def _fetch(self, url: str) -> Selector:
        try:
            resp = httpx.get(url, timeout=30, follow_redirects=True, headers=HEADERS)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise SourceUnavailable(f"请求 {url} 失败: {e}") from e
        if resp.status_code == 404 or "无法找到该资源" in resp.text:
            raise SourceNotFound(f"作品页不存在或已被移除: {url}")
        return Selector(resp.text)

    def _parse_detail(self, url: str) -> WorkInfo:
        sel = self._fetch(url)

        title = (sel.css(".mh-date-info-name h4 a::text").get() or "").strip()
        if not title:
            raise SourceUnavailable(f"未能解析作品标题: {url}（页面结构可能已变更）")

        cover = (sel.css(".mh-date-bgpic img::attr(src)").get() or "").strip()
        cover = self.cover or cover
        if cover and not cover.startswith("http"):
            cover = BASE_URL + cover

        status = self._parse_status(sel)
        category = (sel.css(".mh-label a::text").get() or "").strip() or self.category
        category = self.category or category

        description = self._parse_description(sel)

        chapters = self._parse_chapters(sel)

        if not chapters:
            raise SourceNotFound(f"「{title}」在 mh160mh 上无章节列表")

        return WorkInfo(
            title=title,
            category=category or "",
            description=description,
            cover_path=cover or "",
            source_url=url,
            status=status,
            chapters=chapters,
        )

    @staticmethod
    def _parse_description(sel: Selector) -> str:
        """从 og:description 提取简介，去除站点推广尾巴"""
        text = (
            sel.css('meta[property="og:description"]::attr(content)').get() or ""
        ).strip()
        if not text:
            return ""
        # 站点在简介末尾追加推广文案（如「xxx漫画网收集自互联网，xxx_为你做最好的漫画」）
        cut = re.split(r"(?:收集自|转载自|来源于|来自)", text, maxsplit=1)[0]
        # 残留的站点名尾巴（如「笨狗漫画网」）
        cut = re.sub(r"[\u4e00-\u9fa5]{0,10}漫画网$", "", cut.strip())
        return cut.strip()

    @staticmethod
    def _parse_status(sel: Selector) -> str:
        """从「状态：<em>连载中</em>」解析作品状态"""
        for p in sel.css(".works-info-tc"):
            em = p.css("em::text").get()
            if em:
                em = em.strip()
                if em:
                    return STATUS_MAP.get(em, "ongoing")
        return "ongoing"

    @staticmethod
    def _parse_chapters(sel: Selector) -> List[ChapterInfo]:
        """解析章节列表（页面为降序，转为升序并顺序编号）"""
        result: List[ChapterInfo] = []
        for ul in sel.css('ul[id^="mh-chapter-list-ol-"]'):
            items = ul.css("li a")
            for a in reversed(items):
                href = a.attrib.get("href", "") or ""
                title = (a.css("p::text").get() or "").strip() or ""
                m = CHAPTER_RE.search(href)
                if not m:
                    continue
                result.append(
                    ChapterInfo(
                        chapter_num=len(result) + 1,
                        chapter_title=title or f"第{len(result) + 1}话",
                    )
                )
        return result
