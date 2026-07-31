"""瓜子漫画 (guazimanhua.com) 爬虫

基于静态详情页 + JSON-LD 结构化数据：
- 作品详情: https://www.guazimanhua.com/comic.php?id=<id>
- 章节页:   https://www.guazimanhua.com/chapter.php?id=<id>

页面内嵌 schema.org JSON-LD（ComicStory + ItemList），
作品信息与完整章节列表（position 升序）均可直接解析。

注：该站未提供可用站内搜索，仅支持 URL 导入。
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

import httpx

from .base import BaseCrawler, ChapterInfo, SourceNotFound, SourceUnavailable, WorkInfo
from .registry import register_source

BASE_URL = "https://www.guazimanhua.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Referer": BASE_URL + "/",
}

JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S
)


@register_source
class GuaziCrawler(BaseCrawler):
    """瓜子漫画 爬虫：爬取封面 URL + 章节名称，不下载图片"""

    name = "guazi"
    display_name = "瓜子漫画 (guazimanhua.com)"
    domains = ["guazimanhua.com"]

    def crawl(self) -> WorkInfo:
        src = self.source.strip()
        if not src.lower().startswith(("http://", "https://")):
            raise SourceNotFound(
                f"「{src}」: guazimanhua.com 未提供站内搜索，"
                f"请改用漫画 URL 导入。\n"
                f"例如: komichi-cli import https://www.guazimanhua.com/comic.php?id=33993"
            )
        return self._parse_detail(src)

    def _fetch(self, url: str) -> str:
        try:
            resp = httpx.get(url, timeout=30, follow_redirects=True, headers=HEADERS)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise SourceUnavailable(f"请求 {url} 失败: {e}") from e
        if resp.status_code == 404:
            raise SourceNotFound(f"作品页不存在或已被移除: {url}")
        return resp.text

    def _parse_detail(self, url: str) -> WorkInfo:
        text = self._fetch(url)
        graph = self._extract_jsonld(text)
        if not graph:
            raise SourceUnavailable(
                f"未能解析 JSON-LD 数据: {url}（页面结构可能已变更）"
            )

        comic = next((g for g in graph if g.get("@type") == "ComicStory"), None)
        chapter_list = next((g for g in graph if g.get("@type") == "ItemList"), None)
        if not comic or not comic.get("name"):
            raise SourceUnavailable(f"未能解析作品信息: {url}（页面结构可能已变更）")

        title = str(comic.get("name", "")).strip()

        cover = self.cover or str(comic.get("image", "") or "").strip()
        if cover and not cover.startswith("http"):
            cover = BASE_URL + cover

        genre = comic.get("genre")
        if isinstance(genre, list):
            genre = " ".join(str(g) for g in genre)
        category = self.category or str(genre or "").strip()

        description = str(comic.get("description") or "").strip()

        chapters = self._parse_chapters(chapter_list)
        if not chapters:
            raise SourceNotFound(f"「{title}」在 guazimanhua 上无章节列表")

        return WorkInfo(
            title=title,
            category=category or "",
            description=description,
            cover_path=cover or "",
            source_url=url,
            status="ongoing",
            chapters=chapters,
        )

    @staticmethod
    def _extract_jsonld(text: str) -> List[Dict]:
        """提取页面内所有 JSON-LD 对象，合并 @graph"""
        result: List[Dict] = []
        for m in JSONLD_RE.finditer(text):
            try:
                data = json.loads(m.group(1))
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(data, dict):
                if isinstance(data.get("@graph"), list):
                    result.extend(g for g in data["@graph"] if isinstance(g, dict))
                else:
                    result.append(data)
            elif isinstance(data, list):
                result.extend(d for d in data if isinstance(d, dict))
        return result

    @staticmethod
    def _parse_chapters(item_list: Dict) -> List[ChapterInfo]:
        """解析 ItemList 章节（position 升序，直接编号）"""
        result: List[ChapterInfo] = []
        for item in item_list.get("itemListElement", []) or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "") or "").strip()
            result.append(
                ChapterInfo(
                    chapter_num=len(result) + 1,
                    chapter_title=name or f"第{len(result) + 1}话",
                )
            )
        return result
