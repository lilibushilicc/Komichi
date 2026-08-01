"""漫画160 (mh160mh.com) 爬虫 — CLI 类接口 + daemon 模块接口共用

基于 qingtiancms 模板的静态详情页（HTML 解析）：
- 作品详情: https://www.mh160mh.com/kanmanhua/<id>/
- 章节页:   https://www.mh160mh.com/kanmanhua/<id>/<chapter_id>.html

该站未提供可用站内搜索（搜索端点 404），仅支持 URL 导入。
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
NAME = "mh160mh"
DOMAINS = ["mh160mh.com"]
HAS_SEARCH = False

BASE_URL = "https://www.mh160mh.com"
HEADERS = {**BROWSER_HEADERS, "Referer": BASE_URL + "/"}

CHAPTER_RE = re.compile(r"/kanmanhua/[^/]+/(\d+)\.html")


def is_supported(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    return host == "mh160mh.com" or host.endswith(".mh160mh.com")


def crawl(source_url: str, timeout_ms: int = 45000) -> Dict[str, Any]:
    """爬取 mh160mh 作品详情页，返回结构化数据。

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
    timeout = timeout_ms / 1000

    try:
        resp = httpx.get(
            source_url, timeout=timeout, follow_redirects=True, headers=HEADERS
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise SourceUnavailable(f"请求 {source_url} 失败: {e}") from e

    if resp.status_code == 404 or "无法找到该资源" in resp.text:
        raise SourceNotFound(f"作品页不存在或已被移除: {source_url}")

    sel = Selector(resp.text)

    title = (sel.css(".mh-date-info-name h4 a::text").get() or "").strip()
    if not title:
        raise SourceUnavailable(
            f"未能解析作品标题: {source_url}（页面结构可能已变更）"
        )

    cover = (sel.css(".mh-date-bgpic img::attr(src)").get() or "").strip()
    if cover and not cover.startswith("http"):
        cover = BASE_URL + cover

    status = _parse_status(sel)
    category = (sel.css(".mh-label a::text").get() or "").strip()
    description = _parse_description(sel)
    chapters = _parse_chapters(sel)

    if not chapters:
        raise SourceNotFound(f"「{title}」在 mh160mh 上无章节列表")

    return {
        "title": title,
        "cover_url": cover,
        "description": description,
        "category": category,
        "status": status,
        "chapters": chapters,
    }


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


def _parse_status(sel: Selector) -> str:
    """从「状态：<em>连载中</em>」解析作品状态"""
    for p in sel.css(".works-info-tc"):
        em = p.css("em::text").get()
        if em:
            em = em.strip()
            if em:
                return STATUS_MAP.get(em, "ongoing")
    return "ongoing"


def _parse_chapters(sel: Selector) -> List[Dict[str, Any]]:
    """解析章节列表（页面为降序，转为升序并顺序编号）"""
    result: List[Dict[str, Any]] = []
    for ul in sel.css('ul[id^="mh-chapter-list-ol-"]'):
        items = ul.css("li a")
        for a in reversed(items):
            href = a.attrib.get("href", "") or ""
            title = (a.css("p::text").get() or "").strip() or ""
            if not CHAPTER_RE.search(href):
                continue
            result.append({
                "chapter_num": len(result) + 1,
                "chapter_title": title or f"第{len(result) + 1}话",
            })
    return result


# 类接口（CLI 使用）
@register_source
class Mh160mhCrawler(BaseCrawler):
    """漫画160 爬虫：爬取封面 URL + 章节名称，不下载图片"""

    name = "mh160mh"
    display_name = "漫画160 (mh160mh.com)"
    domains = ["mh160mh.com"]

    def crawl(self) -> WorkInfo:
        return crawl_work(
            self.source,
            name=self.name,
            display_name=self.display_name,
            crawl_fn=crawl,
            has_search=HAS_SEARCH,
            title=self.title,
            category=self.category,
            cover=self.cover,
        )
