"""腾讯动漫 (ac.qq.com) 爬虫

静态服务端渲染页面：
- 作品详情: https://ac.qq.com/Comic/comicInfo/id/<id>
- 搜索:     https://ac.qq.com/Comic/searchList/search/<关键词>

详情页内直接包含：标题、封面、状态、作者、简介与完整章节列表（升序）。
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

import httpx
from parsel import Selector

from .base import BaseCrawler, ChapterInfo, SourceNotFound, SourceUnavailable, WorkInfo
from .registry import register_source

BASE_URL = "https://ac.qq.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Referer": BASE_URL + "/",
}

DETAIL_RE = re.compile(r"/Comic/comicInfo/id/(\d+)")
CHAPTER_RE = re.compile(r"/ComicView/index/id/(\d+)/cid/(\d+)")

STATUS_MAP = {
    "连载中": "ongoing",
    "连载": "ongoing",
    "更新中": "ongoing",
    "完结": "completed",
    "已完结": "completed",
}


@register_source
class TencentCrawler(BaseCrawler):
    """腾讯动漫 爬虫：爬取封面 URL + 章节名称，不下载图片"""

    name = "tencent"
    display_name = "腾讯动漫 (ac.qq.com)"
    domains = ["ac.qq.com"]

    def crawl(self) -> WorkInfo:
        src = self.source.strip()
        if src.lower().startswith(("http://", "https://")):
            m = DETAIL_RE.search(src)
            if not m:
                raise SourceNotFound(
                    f"无法识别腾讯动漫作品链接: {src}\n"
                    f"正确的格式: https://ac.qq.com/Comic/comicInfo/id/<id>"
                )
            return self._parse_detail(src)
        return self._search(src)

    def _fetch(self, url: str) -> Selector:
        try:
            resp = httpx.get(url, timeout=30, follow_redirects=True, headers=HEADERS)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise SourceUnavailable(f"请求 {url} 失败: {e}") from e
        if resp.status_code == 404 or len(resp.text) < 500:
            raise SourceNotFound(f"作品页不存在或已被移除: {url}")
        return Selector(resp.text)

    def _search(self, keyword: str) -> WorkInfo:
        from urllib.parse import quote

        sel = self._fetch(
            f"{BASE_URL}/Comic/searchList/search/{quote(keyword, safe='')}"
        )
        results: List[Tuple[str, str]] = []
        for a in sel.css('a[href^="/Comic/comicInfo/id/"]'):
            href = a.attrib.get("href", "")
            text = (a.css("::text").get() or "").strip()
            if href and text and text != keyword:
                results.append((text, href))
        if not results:
            raise SourceNotFound(f"腾讯动漫搜索「{keyword}」无结果")
        _, url = results[0]
        return self._parse_detail(BASE_URL + url)

    def _parse_detail(self, url: str) -> WorkInfo:
        sel = self._fetch(url)

        title = (sel.css(".works-intro-title strong::text").get() or "").strip()
        if not title:
            raise SourceUnavailable(f"未能解析作品标题: {url}（页面结构可能已变更）")

        cover = (
            sel.css(".works-cover img::attr(src)").get() or ""
        ).strip()
        cover = self.cover or cover
        if cover and cover.startswith("//"):
            cover = "https:" + cover

        status = self._parse_status(sel)
        category = self.category
        if not category:
            category = (sel.css(".works-intro-category a::text").get() or "").strip()

        description = (sel.css("p.works-intro-short::text").get() or "").strip()
        description = re.sub(r"\[简介\]", "", description).strip()

        chapters = self._parse_chapters(sel)
        if not chapters:
            raise SourceNotFound(f"「{title}」在 ac.qq.com 上无章节列表")

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
    def _parse_status(sel: Selector) -> str:
        text = (sel.css("label.works-intro-status::text").get() or "").strip()
        return STATUS_MAP.get(text, "ongoing")

    @staticmethod
    def _parse_chapters(sel: Selector) -> List[ChapterInfo]:
        """解析完整章节列表（chapter-page-all 内为升序）"""
        result: List[ChapterInfo] = []
        for a in sel.css("ol.chapter-page-all li a"):
            href = a.attrib.get("href", "")
            title = a.attrib.get("title", "") or ""
            if not CHAPTER_RE.search(href):
                continue
            result.append(
                ChapterInfo(
                    chapter_num=len(result) + 1,
                    chapter_title=title.strip() or f"第{len(result) + 1}话",
                )
            )
        return result
