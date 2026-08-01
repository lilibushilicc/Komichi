"""godamh.com 漫画爬虫 — CLI 类接口 + daemon 模块接口共用

该站有 Cloudflare 反爬，需 TLS 指纹伪装（curl_cffi impersonate=chrome120）。
Worker 跑不了 TLS 伪装，故归入 VPS 板块。

依赖：pip install curl_cffi
"""
from __future__ import annotations

import re
from typing import Any, Dict, List
from urllib.parse import urlparse

from curl_cffi import requests as cffi_requests

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
NAME = "godamh"
DOMAINS = ["godamh.com"]
HAS_SEARCH = True

BASE_URL = "https://godamh.com"
API_HOST = "https://v2.apikk.top"
HEADERS = {**BROWSER_HEADERS, "Referer": BASE_URL + "/"}

MID_RE = re.compile(r'\bmid["\']?\s*[:=]\s*["\']?(\d+)')


def is_supported(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    return host == "godamh.com" or host.endswith(".godamh.com")


def crawl(source_url: str, timeout_ms: int = 45000) -> Dict[str, Any]:
    """爬取 godamh 作品页，返回结构化数据。

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

    # 1. 访问作品页，正则提取 mid
    try:
        resp = cffi_requests.get(
            source_url, impersonate="chrome120", headers=HEADERS, timeout=timeout
        )
    except Exception as e:
        raise SourceUnavailable(f"访问作品页失败: {e}") from e

    # 确保中文页面正确解码
    resp.encoding = "utf-8"
    m = MID_RE.search(resp.text)
    if not m:
        raise SourceUnavailable(
            f"无法获取作品 ID (mid): {source_url}（页面结构可能已变更）"
        )
    mid = m.group(1)

    # 2. 调 API 获取作品数据
    try:
        resp = cffi_requests.get(
            f"{API_HOST}/api/v2/manga/get",
            params={"mid": mid, "mode": "all"},
            impersonate="chrome120",
            headers=HEADERS,
            timeout=timeout,
        )
        data = resp.json()
    except Exception as e:
        raise SourceUnavailable(f"获取作品数据失败: {e}") from e

    d = data.get("data", {})
    title = d.get("title") or "未命名"
    cover = d.get("cover", "")
    description = str(d.get("desc") or "").strip()

    chapters_raw = d.get("chapters", [])
    chapters: List[Dict[str, Any]] = []
    for i, ch in enumerate(chapters_raw, start=1):
        attrs = ch.get("attributes", ch)
        raw_title = attrs.get("title", "")
        chapters.append({
            "chapter_num": i,
            "chapter_title": raw_title or f"第{i}话",
        })

    if not chapters:
        raise SourceNotFound(f"「{title}」无章节列表")

    return {
        "title": title,
        "cover_url": cover,
        "description": description,
        "category": "",
        "status": "ongoing",
        "chapters": chapters,
    }


def search(keyword: str, timeout_ms: int = 45000) -> List[Dict[str, str]]:
    """搜索 godamh 漫画，返回 [{title, url}]"""
    from parsel import Selector

    timeout = timeout_ms / 1000
    try:
        resp = cffi_requests.get(
            f"{BASE_URL}/s/",
            params={"q": keyword},
            impersonate="chrome120",
            headers=HEADERS,
            timeout=timeout,
        )
    except Exception as e:
        raise SourceUnavailable(f"搜索请求失败: {e}") from e

    # curl_cffi 在服务端未声明 charset 时默认用 Latin-1 解码，导致中文乱码
    resp.encoding = "utf-8"
    sel = Selector(resp.text)
    results: List[Dict[str, str]] = []
    for a in sel.css(".cardlist a[href*='/manga/']"):
        title = a.css("::attr(title)").get() or a.css("h3::text").get() or ""
        href = a.attrib.get("href", "")
        if not title:
            continue
        # 只保留标题含关键词的结果，过滤站点推荐内容
        if keyword not in title:
            continue
        link = href if href.startswith("http") else f"{BASE_URL}{href}"
        results.append({"title": title, "url": link})
    return results


# 类接口（CLI 使用）
@register_source
class GodamhCrawler(BaseCrawler):
    """godamh.com 漫画爬虫：爬取封面 URL + 章节名称，不下载图片"""

    name = "godamh"
    display_name = "godamh.com"
    domains = ["godamh.com"]

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
