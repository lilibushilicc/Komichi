"""腾讯动漫 (ac.qq.com) 爬虫 — CLI 类接口 + daemon 模块接口共用

静态服务端渲染页面：
- 作品详情: https://ac.qq.com/Comic/comicInfo/id/<id>
- 搜索:     https://ac.qq.com/Comic/searchList/search/<关键词>

详情页内直接包含：标题、封面、状态、作者、简介与完整章节列表（升序）。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx
from parsel import Selector

from ._http import BROWSER_HEADERS, STATUS_MAP
from .base import (
    BaseCrawler,
    SourceNotFound,
    SourceUnavailable,
    WorkInfo,
    crawl_work,
)
from .registry import register_source

# 模块接口（供 registry 调度）
NAME = "tencent"
DOMAINS = ["ac.qq.com"]
HAS_SEARCH = True

BASE_URL = "https://ac.qq.com"
HEADERS = {**BROWSER_HEADERS, "Referer": BASE_URL + "/"}

DETAIL_RE = re.compile(r"/Comic/comicInfo/id/(\d+)")
CHAPTER_RE = re.compile(r"/ComicView/index/id/(\d+)/cid/(\d+)")


def is_supported(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    return host == "ac.qq.com" or host.endswith(".ac.qq.com")


def crawl(source_url: str, timeout_ms: int = 45000) -> Dict[str, Any]:
    """爬取腾讯动漫作品页，返回结构化数据。

    返回:
        {
            "title": str,
            "cover_url": str,
            "description": str,
            "category": str,
            "status": "ongoing" | "completed",
            "chapters": [{"chapter_num": int, "chapter_title": str}, ...],
        }
    """
    if not DETAIL_RE.search(source_url):
        raise SourceNotFound(
            f"无法识别腾讯动漫作品链接: {source_url}\n"
            f"正确的格式: https://ac.qq.com/Comic/comicInfo/id/<id>"
        )

    timeout = timeout_ms / 1000

    try:
        resp = httpx.get(
            source_url, timeout=timeout, follow_redirects=True, headers=HEADERS
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise SourceUnavailable(f"请求 {source_url} 失败: {e}") from e

    if resp.status_code == 404 or len(resp.text) < 500:
        raise SourceNotFound(f"作品页不存在或已被移除: {source_url}")

    sel = Selector(resp.text)

    title = (sel.css(".works-intro-title strong::text").get() or "").strip()
    if not title:
        raise SourceUnavailable(
            f"未能解析作品标题: {source_url}（页面结构可能已变更）"
        )

    cover = (sel.css(".works-cover img::attr(src)").get() or "").strip()
    if cover and cover.startswith("//"):
        cover = "https:" + cover

    status = _parse_status(sel)
    category = (sel.css(".works-intro-category a::text").get() or "").strip()
    description = (sel.css("p.works-intro-short::text").get() or "").strip()
    description = re.sub(r"\[简介\]", "", description).strip()

    chapters = _parse_chapters(sel)
    if not chapters:
        raise SourceNotFound(f"「{title}」在 ac.qq.com 上无章节列表")

    return {
        "title": title,
        "cover_url": cover,
        "description": description,
        "category": category,
        "status": status,
        "chapters": chapters,
    }


def _parse_status(sel: Selector) -> str:
    text = (sel.css("label.works-intro-status::text").get() or "").strip()
    return STATUS_MAP.get(text, "ongoing")


def _parse_chapters(sel: Selector) -> List[Dict[str, Any]]:
    """解析完整章节列表（chapter-page-all 内为升序）"""
    result: List[Dict[str, Any]] = []
    for a in sel.css("ol.chapter-page-all li a"):
        href = a.attrib.get("href", "") or ""
        title = a.attrib.get("title", "") or ""
        if not CHAPTER_RE.search(href):
            continue
        result.append({
            "chapter_num": len(result) + 1,
            "chapter_title": title.strip() or f"第{len(result) + 1}话",
        })
    return result


def search(keyword: str, timeout_ms: int = 45000) -> List[Dict[str, str]]:
    """搜索腾讯动漫，返回 [{title, url}]

    搜索页: https://ac.qq.com/Comic/searchList/search/<关键词>
    解析搜索结果中的作品链接（去重）。
    """
    from urllib.parse import quote

    timeout = timeout_ms / 1000
    search_url = f"{BASE_URL}/Comic/searchList/search/{quote(keyword, safe='')}"

    try:
        resp = httpx.get(
            search_url, timeout=timeout, follow_redirects=True, headers=HEADERS
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise SourceUnavailable(f"搜索请求失败: {e}") from e

    sel = Selector(resp.text)
    results: List[Dict[str, str]] = []
    seen_urls: set = set()

    for a in sel.css('a[href^="/Comic/comicInfo/id/"]'):
        href = a.attrib.get("href", "") or ""
        text = (a.css("::text").get() or "").strip()
        if href and text and keyword in text:
            full_url = BASE_URL + href
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                results.append({"title": text, "url": full_url})

    return results


# 类接口（CLI 使用）
@register_source
class TencentCrawler(BaseCrawler):
    """腾讯动漫 爬虫：爬取封面 URL + 章节名称，不下载图片"""

    name = "tencent"
    display_name = "腾讯动漫 (ac.qq.com)"
    domains = ["ac.qq.com"]

    def crawl(self) -> WorkInfo:
        return crawl_work(
            self.source,
            name=self.name,
            display_name=self.display_name,
            crawl_fn=crawl,
            search_fn=search,
            has_search=HAS_SEARCH,
            title=self.title,
            category=self.category,
            cover=self.cover,
        )
