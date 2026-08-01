"""快看漫画 (kuaikanmanhua.com) 爬虫 — CLI 类接口 + daemon 模块接口共用

PC 端为 Nuxt SPA，数据走内部 JSON API：
- 作品页:  https://www.kuaikanmanhua.com/web/comic/<comic_id>
- 详情1:   GET /v2/pweb/comic/inner/<comic_id>   → 返回 topic_id
- 详情2:   GET /v2/pweb/topic/<topic_id>         → 作品信息 + 完整章节列表（升序）
- 搜索:     GET /search/web/complex?q=<关键词>   → 作品列表
"""
from __future__ import annotations

import re
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx

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
NAME = "kuaikan"
DOMAINS = ["kuaikanmanhua.com"]
HAS_SEARCH = True

BASE_URL = "https://www.kuaikanmanhua.com"
API_URL = "https://www.kuaikanmanhua.com/v2/pweb"
# 快看接口走 JSON，覆盖 Accept
HEADERS = {
    **BROWSER_HEADERS,
    "Accept": "application/json",
    "Referer": BASE_URL + "/web/comic/",
}

COMIC_RE = re.compile(r"/web/comic/(\d+)")


def is_supported(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    return host == "kuaikanmanhua.com" or host.endswith(".kuaikanmanhua.com")


def crawl(source_url: str, timeout_ms: int = 45000) -> Dict[str, Any]:
    """爬取快看漫画作品页，返回结构化数据。

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
    m = COMIC_RE.search(source_url)
    if not m:
        raise SourceNotFound(
            f"无法识别快看漫画作品链接: {source_url}\n"
            f"正确的格式: https://www.kuaikanmanhua.com/web/comic/<id>"
        )
    comic_id = m.group(1)
    timeout = timeout_ms / 1000

    # 1. inner 接口 → topic_id
    inner = _get_json(
        f"{API_URL}/comic/inner/{comic_id}?source=&pc_go_app_exp=", timeout
    )
    topic = (inner.get("data") or {}).get("topic_info") or {}
    topic_id = topic.get("id")
    if not topic_id:
        raise SourceNotFound(f"快看漫画作品不存在或已下线: {comic_id}")

    # 2. topic 接口 → 作品信息 + 章节列表
    detail = _get_json(
        f"{API_URL}/topic/{topic_id}?source=&pc_go_app_exp=", timeout
    )
    info = (detail.get("data") or {}).get("topic_info") or {}

    title = str(info.get("title", "") or "").strip()
    if not title:
        raise SourceUnavailable(
            f"未能解析作品标题: {comic_id}（页面结构可能已变更）"
        )

    cover = str(
        info.get("vertical_image_url") or info.get("cover_image_url") or ""
    ).strip()

    status = STATUS_MAP.get(str(info.get("update_status", "")).strip(), "ongoing")
    category = ""
    if info.get("tags"):
        category = " ".join(str(t) for t in info["tags"] if t)

    description = str(info.get("description") or "").strip()

    chapters = _parse_chapters(info.get("comics") or [])
    if not chapters:
        raise SourceNotFound(f"「{title}」在 kuaikanmanhua 上无章节列表")

    return {
        "title": title,
        "cover_url": cover,
        "description": description,
        "category": category,
        "status": status,
        "chapters": chapters,
    }


def _get_json(url: str, timeout: float) -> dict:
    try:
        resp = httpx.get(
            url, timeout=timeout, follow_redirects=True, headers=HEADERS
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        raise SourceUnavailable(f"请求 {url} 失败: {e}") from e
    if data.get("code") != 200:
        raise SourceUnavailable(
            f"快看接口返回异常 (code={data.get('code')}, "
            f"msg={data.get('message')}): {url}"
        )
    return data


def _parse_chapters(comics: List[dict]) -> List[Dict[str, Any]]:
    """解析章节列表（接口返回按发布时间升序）"""
    result: List[Dict[str, Any]] = []
    for c in comics:
        if not isinstance(c, dict) or not c.get("id"):
            continue
        title = str(c.get("title", "") or "").strip()
        result.append({
            "chapter_num": len(result) + 1,
            "chapter_title": title or f"第{len(result) + 1}话",
        })
    return result


def search(keyword: str, timeout_ms: int = 45000) -> List[Dict[str, str]]:
    """搜索快看漫画，返回 [{title, url}]

    使用 PC 端搜索 API: /search/web/complex?q=<关键词>
    """
    from urllib.parse import quote

    timeout = timeout_ms / 1000
    search_url = (
        f"{BASE_URL}/search/web/complex"
        f"?q={quote(keyword, safe='')}&since=0&siz=20"
    )

    try:
        resp = httpx.get(
            search_url, timeout=timeout, follow_redirects=True, headers=HEADERS
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        raise SourceUnavailable(f"搜索请求失败: {e}") from e

    if data.get("code") != 200:
        raise SourceUnavailable(
            f"搜索接口返回异常 (code={data.get('code')}, "
            f"msg={data.get('message')}): {keyword}"
        )

    hits = ((data.get("data") or {}).get("topics") or {}).get("hit") or []
    # 快看搜索会混入推荐内容，只保留标题含关键词的结果
    results: List[Dict[str, str]] = []
    for h in hits:
        if not h.get("id") or not h.get("title"):
            continue
        title = str(h.get("title", "") or "").strip()
        if keyword in title:
            results.append({
                "title": title,
                "url": f"{BASE_URL}/web/comic/{h['id']}",
            })
    return results


# 类接口（CLI 使用）
@register_source
class KuaikanCrawler(BaseCrawler):
    """快看漫画 爬虫：爬取封面 URL + 章节名称，不下载图片"""

    name = "kuaikan"
    display_name = "快看漫画 (kuaikanmanhua.com)"
    domains = ["kuaikanmanhua.com"]

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
