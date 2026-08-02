"""SF漫画 (sfacg.com) 爬虫 — 远程追更版

菠萝包轻漫画，服务端渲染页面：
- 作品详情: https://mm.sfacg.com/b/<comicFolder>/
- PC端详情: https://manhua.sfacg.com/mh/<comicFolder>/

无公开搜索接口，仅支持 URL 导入。

依赖：pip install parsel
"""
from __future__ import annotations

import re
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx
from parsel import Selector

from .base import BaseCrawler, SourceNotFound, SourceUnavailable, WorkInfo, crawl_work
from .registry import register_source

# 多源统一接口（供 registry 调度）
NAME = "sfacg"
DOMAINS = ["sfacg.com", "mm.sfacg.com", "manhua.sfacg.com"]

BASE_URL = "https://mm.sfacg.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Referer": BASE_URL + "/",
}

# 匹配 /b/<comicFolder>/ 或 /mh/<comicFolder>/
FOLDER_RE = re.compile(r"/(?:b|mh)/([A-Za-z0-9]+)/?", re.I)

STATUS_MAP = {
    "连载中": "ongoing",
    "连载": "ongoing",
    "更新中": "ongoing",
    "完结": "completed",
    "已完结": "completed",
}


class SfacgCrawlError(Exception):
    """sfacg 爬取失败"""


CrawlError = SfacgCrawlError


def is_supported(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    return host == "sfacg.com" or host.endswith(".sfacg.com")


def crawl(source_url: str, timeout_ms: int = 45000) -> Dict[str, Any]:
    """爬取 SF漫画作品页，返回结构化数据。

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
    m = FOLDER_RE.search(source_url)
    if not m:
        raise SfacgCrawlError(
            f"无法识别 SF漫画作品链接: {source_url}\n"
            f"正确的格式: https://mm.sfacg.com/b/<comicFolder>/"
        )
    comic_folder = m.group(1)
    # 统一使用移动端 URL
    detail_url = f"{BASE_URL}/b/{comic_folder}/"
    timeout = timeout_ms / 1000

    try:
        resp = httpx.get(
            detail_url, timeout=timeout, follow_redirects=True, headers=HEADERS
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise SfacgCrawlError(f"请求 {detail_url} 失败: {e}") from e

    if resp.status_code == 404 or len(resp.text) < 500:
        raise SfacgCrawlError(f"作品页不存在或已被移除: {detail_url}")

    sel = Selector(resp.text)

    # 标题
    title = (sel.css("span.book_newtitle::text").get() or "").strip()
    if not title:
        # 尝试 PC 端选择器
        title = (sel.css("h1.book_newtitle::text").get() or "").strip()
    if not title:
        raise SfacgCrawlError(
            f"未能解析作品标题: {detail_url}（页面结构可能已变更）"
        )

    # 封面
    cover = (sel.css(".book_info li img::attr(src)").get() or "").strip()
    if cover and not cover.startswith("http"):
        cover = "https:" + cover

    # 分类与状态
    info_spans = sel.css(".book_info2 span::text").getall()
    category = info_spans[0].strip() if len(info_spans) > 0 else ""
    status_text = info_spans[1].strip() if len(info_spans) > 1 else ""
    status = STATUS_MAP.get(status_text, "ongoing")

    # 简介
    description = (sel.css(".book_profile li.book_bk_qs1::text").get() or "").strip()

    # 章节列表（页面为降序，需翻转）
    chapters_raw: List[Dict[str, Any]] = []
    for a in sel.css(".comic_main_list a"):
        # 取整个 div 的文本（含 <b>VIP</b> 前缀），再去除标签、压缩空白
        div_html = a.css("div").get() or ""
        chapter_text = re.sub(r"<[^>]+>", "", div_html)
        chapter_text = re.sub(r"\s+", " ", chapter_text).strip()
        if chapter_text:
            chapters_raw.append({"chapter_title": chapter_text})

    if not chapters_raw:
        raise SfacgCrawlError(f"「{title}」在 sfacg 上无章节列表")

    # 页面为降序（最新在前），翻转为升序
    chapters_raw.reverse()
    chapters: List[Dict[str, Any]] = []
    for i, ch in enumerate(chapters_raw, start=1):
        chapters.append({
            "chapter_num": i,
            "chapter_title": ch["chapter_title"],
        })

    return {
        "title": title,
        "cover_url": cover,
        "description": description,
        "category": category,
        "status": status,
        "chapters": chapters,
    }


# 多源统一接口（供 registry 调度）
HAS_SEARCH = False


# 类接口（CLI 使用）
@register_source
class SfacgCrawler(BaseCrawler):
    """SF漫画 爬虫：爬取封面 URL + 章节名称，不下载图片"""

    name = "sfacg"
    display_name = "SF漫画 (sfacg.com)"
    domains = ["sfacg.com", "mm.sfacg.com", "manhua.sfacg.com"]

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
