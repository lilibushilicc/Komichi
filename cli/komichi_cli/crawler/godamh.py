from __future__ import annotations

import re
from typing import List, Optional

from curl_cffi import requests
from parsel import Selector

from ..api.client import NetworkError
from .base import BaseCrawler, ChapterInfo, WorkInfo

BASE_URL = "https://godamh.com"
API_HOST = "https://v2.apikk.top"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Referer": "https://godamh.com/",
}


class GodamhCrawler(BaseCrawler):
    """godamh.com 漫画爬虫：爬取封面 URL + 章节名称，不下载图片"""

    def crawl(self) -> WorkInfo:
        src = self.source.strip()

        if src.startswith(BASE_URL) and "/manga/" in src:
            manga_url = src
        else:
            manga_url = self._search(src)

        return self._parse_manga(manga_url)

    def _search(self, keyword: str) -> str:
        resp = requests.get(
            f"{BASE_URL}/s/", params={"q": keyword}, impersonate="chrome120", headers=HEADERS
        )
        sel = Selector(resp.text)
        results = sel.css(".cardlist a[href*='/manga/']")
        if not results:
            raise ValueError(f"在 godamh.com 上未找到「{keyword}」")
        for a in results:
            text = a.css("::attr(title)").get() or a.css("h3::text").get() or ""
            href = a.attrib.get("href", "")
            if keyword in text:
                link = href
                return link if link.startswith("http") else f"{BASE_URL}{link}"
        titles = "\n".join(
            f"  - {a.css('::attr(title)').get() or a.css('h3::text').get() or '?'}"
            for a in results[:10]
        )
        raise ValueError(
            f"未找到完全匹配「{keyword}」的结果，请改用漫画 URL 导入。\n"
            f"搜索结果（前 10 条）：\n{titles}\n"
            f"例如: komichi-cli import godamh https://godamh.com/manga/xxx"
        )

    def _get_mid(self, url: str) -> str:
        resp = requests.get(url, impersonate="chrome120", headers=HEADERS)
        m = re.search(r'\bmid["\']?\s*[:=]\s*["\']?(\d+)', resp.text)
        if not m:
            raise ValueError(f"无法获取作品 ID: {url}")
        return m.group(1)

    def _parse_manga(self, url: str) -> WorkInfo:
        mid = self._get_mid(url)

        resp = requests.get(
            f"{API_HOST}/api/v2/manga/get",
            params={"mid": mid, "mode": "all"},
            impersonate="chrome120",
            headers=HEADERS,
        )
        data = resp.json()
        d = data.get("data", {})

        title = d.get("title") or self.title or "未命名"

        cover = self.cover or d.get("cover", "")

        chapters_raw = d.get("chapters", [])
        chapters: List[ChapterInfo] = []
        for i, ch in enumerate(chapters_raw, start=1):
            attrs = ch.get("attributes", ch)
            raw_title = attrs.get("title", "")
            chapters.append(ChapterInfo(chapter_num=i, chapter_title=raw_title, image_paths=[]))

        return WorkInfo(
            title=title,
            category=self.category or "",
            cover_path=cover,
            source_url=url,
            status="ongoing",
            chapters=chapters,
        )
