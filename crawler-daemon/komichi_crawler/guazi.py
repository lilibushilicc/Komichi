"""瓜子漫画 (guazimanhua.com) 爬虫 — CLI 类接口 + daemon 模块接口共用

基于静态详情页 + JSON-LD 结构化数据（schema.org 的 ComicStory + ItemList）：
- 作品详情: https://www.guazimanhua.com/comic.php?id=<id>

作品信息与完整章节列表（position 升序）均可直接从 JSON-LD 解析。
该站未提供可用站内搜索，仅支持 URL 导入。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx

from ._http import BROWSER_HEADERS
from .base import (
    BaseCrawler,
    SourceNotFound,
    SourceUnavailable,
    WorkInfo,
    crawl_work,
)
from .registry import register_source

# 模块接口（供 registry 调度）
NAME = "guazi"
DOMAINS = ["guazimanhua.com"]
HAS_SEARCH = False

BASE_URL = "https://www.guazimanhua.com"
HEADERS = {**BROWSER_HEADERS, "Referer": BASE_URL + "/"}

JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S
)


def is_supported(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    return host == "guazimanhua.com" or host.endswith(".guazimanhua.com")


def crawl(source_url: str, timeout_ms: int = 45000) -> Dict[str, Any]:
    """爬取瓜子漫画作品页，返回结构化数据。

    返回:
        {
            "title": str,
            "cover_url": str,
            "description": str,
            "category": str,
            "status": "ongoing",
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

    if resp.status_code == 404:
        raise SourceNotFound(f"作品页不存在或已被移除: {source_url}")

    graph = _extract_jsonld(resp.text)
    if not graph:
        raise SourceUnavailable(
            f"未能解析 JSON-LD 数据: {source_url}（页面结构可能已变更）"
        )

    comic = next((g for g in graph if g.get("@type") == "ComicStory"), None)
    chapter_list = next((g for g in graph if g.get("@type") == "ItemList"), None)
    if not comic or not comic.get("name"):
        raise SourceUnavailable(
            f"未能解析作品信息: {source_url}（页面结构可能已变更）"
        )

    title = str(comic.get("name", "")).strip()

    cover = str(comic.get("image", "") or "").strip()
    if cover and not cover.startswith("http"):
        cover = BASE_URL + cover

    genre = comic.get("genre")
    if isinstance(genre, list):
        genre = " ".join(str(g) for g in genre)
    category = str(genre or "").strip()

    description = str(comic.get("description") or "").strip()

    chapters = _parse_chapters(chapter_list or {})
    if not chapters:
        raise SourceNotFound(f"「{title}」在 guazimanhua 上无章节列表")

    return {
        "title": title,
        "cover_url": cover,
        "description": description,
        "category": category,
        "status": "ongoing",
        "chapters": chapters,
    }


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


def _parse_chapters(item_list: Dict) -> List[Dict[str, Any]]:
    """解析 ItemList 章节（position 升序，直接编号）"""
    result: List[Dict[str, Any]] = []
    for item in item_list.get("itemListElement", []) or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "") or "").strip()
        result.append({
            "chapter_num": len(result) + 1,
            "chapter_title": name or f"第{len(result) + 1}话",
        })
    return result


# 类接口（CLI 使用）
@register_source
class GuaziCrawler(BaseCrawler):
    """瓜子漫画 爬虫：爬取封面 URL + 章节名称，不下载图片"""

    name = "guazi"
    display_name = "瓜子漫画 (guazimanhua.com)"
    domains = ["guazimanhua.com"]

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
