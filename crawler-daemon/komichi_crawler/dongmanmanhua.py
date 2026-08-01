"""咚漫漫画 (dongmanmanhua.cn) 爬虫 — 远程追更版

Naver Webtoon 中国版，服务端渲染页面：
- 作品列表页: https://www.dongmanmanhua.cn/<CATEGORY>/<slug>/list?title_no=<id>
- 搜索页:     https://www.dongmanmanhua.cn/search?keyword=<关键词>&searchMode=TITLE

依赖：pip install parsel
"""
from __future__ import annotations

import re
from typing import Any, Dict, List
from urllib.parse import urlparse, quote

import httpx
from parsel import Selector

# 多源统一接口（供 registry 调度）
NAME = "dongmanmanhua"
DOMAINS = ["dongmanmanhua.cn", "www.dongmanmanhua.cn"]

BASE_URL = "https://www.dongmanmanhua.cn"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": BASE_URL + "/",
}

# 匹配 title_no 参数
TITLE_NO_RE = re.compile(r"title_no=(\d+)", re.I)
# 匹配 /episodeList?titleNo=<id> 格式（搜索结果链接）
EPISODE_LIST_RE = re.compile(r"/episodeList\?titleNo=(\d+)", re.I)
# 匹配 list 页面 URL
LIST_URL_RE = re.compile(r"/[^/]+/[^/]+/list\?title_no=\d+", re.I)

STATUS_MAP = {
    "连载中": "ongoing",
    "连载": "ongoing",
    "更新中": "ongoing",
    "完结": "completed",
    "已完结": "completed",
    "完結": "completed",
}


class DongmanmanhuaCrawlError(Exception):
    """dongmanmanhua 爬取失败"""


CrawlError = DongmanmanhuaCrawlError


def is_supported(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    return host == "dongmanmanhua.cn" or host.endswith(".dongmanmanhua.cn")


def crawl(source_url: str, timeout_ms: int = 45000) -> Dict[str, Any]:
    """爬取咚漫漫画作品页，返回结构化数据。

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

    # 处理两种 URL 格式：
    # 1. /<CATEGORY>/<slug>/list?title_no=<id>  (标准列表页)
    # 2. /episodeList?titleNo=<id>  (搜索结果跳转的简短链接)
    m_list = LIST_URL_RE.search(source_url)
    m_episode = EPISODE_LIST_RE.search(source_url)

    if m_list:
        # 已经是标准 list URL，直接使用
        detail_url = source_url if source_url.startswith("http") else BASE_URL + source_url
    elif m_episode:
        # 从 episodeList 链接无法直接获取详情，需要先搜索标题
        # 这种情况理论上不会出现在 crawl 中（crawl 接收的是 source_url）
        raise DongmanmanhuaCrawlError(
            f"请使用作品列表页链接: https://www.dongmanmanhua.cn/<分类>/<名称>/list?title_no=<id>\n"
            f"当前链接 {source_url} 是搜索结果链接，无法直接爬取"
        )
    else:
        raise DongmanmanhuaCrawlError(
            f"无法识别咚漫漫画作品链接: {source_url}\n"
            f"正确的格式: https://www.dongmanmanhua.cn/<分类>/<名称>/list?title_no=<id>"
        )

    try:
        resp = httpx.get(
            detail_url, timeout=timeout, follow_redirects=True, headers=HEADERS
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise DongmanmanhuaCrawlError(f"请求 {detail_url} 失败: {e}") from e

    if resp.status_code == 404 or len(resp.text) < 500:
        raise DongmanmanhuaCrawlError(f"作品页不存在或已被移除: {detail_url}")

    sel = Selector(resp.text)

    # 标题：从 <title> 标签提取（格式: xxx_官方在线漫画阅读-咚漫漫画）
    page_title = (sel.css("title::text").get() or "").strip()
    title = ""
    if page_title:
        title = re.sub(r"_官方在线漫画阅读.*$", "", page_title).strip()
    if not title:
        title = (sel.css("h1::text").get() or "").strip()
    if not title:
        raise DongmanmanhuaCrawlError(
            f"未能解析作品标题: {detail_url}（页面结构可能已变更）"
        )

    # 封面图
    cover = ""
    for img in sel.css("img"):
        src = (img.attrib.get("src") or "").strip()
        if "aka.doubaocdn.com" in src or "dongmanmanhua.cn" in src:
            cover = src
            break
    if cover and not cover.startswith("http"):
        cover = "https:" + cover

    # 状态与分类：从页面文本提取
    status = "ongoing"
    category = ""
    body_text = sel.css("body::text").get() or ""
    for key, val in STATUS_MAP.items():
        if key in body_text:
            status = val
            break

    # 简介
    description = ""
    desc_sel = sel.css(".detail_text::text").get() or sel.css(".description::text").get()
    if desc_sel:
        description = desc_sel.strip()

    # 章节列表
    # 选择器：a[data-sc-name="PC_detail-page_related-title-list-item"]
    # 章节名：img[width="77"][height="73"] 的 alt 属性
    chapters_raw: List[str] = []

    # 方式1：通过 data-sc-name 属性提取章节链接
    chapter_links = sel.css('a[data-sc-name="PC_detail-page_related-title-list-item"]')
    if chapter_links:
        for a in chapter_links:
            # 章节名可能在 alt 属性或文本中
            img_alt = a.css("img::attr(alt)").get() or ""
            text = (a.css("::text").get() or "").strip()
            chapter_title = img_alt or text
            if chapter_title:
                chapters_raw.append(chapter_title)

    # 方式2：通过缩略图 alt 提取章节名
    if not chapters_raw:
        for img in sel.css('img[width="77"][height="73"]'):
            alt = (img.attrib.get("alt") or "").strip()
            if alt:
                chapters_raw.append(alt)

    # 方式3：从包含 episode_no 的链接附近提取
    if not chapters_raw:
        for a in sel.css("a[href*='episode_no']"):
            text = (a.css("::text").get() or "").strip()
            if text:
                chapters_raw.append(text)

    if not chapters_raw:
        raise DongmanmanhuaCrawlError(f"「{title}」在 dongmanmanhua 上无章节列表")

    # 页面通常为降序（最新在前），翻转为升序
    chapters_raw.reverse()
    chapters: List[Dict[str, Any]] = []
    for i, ch_title in enumerate(chapters_raw, start=1):
        chapters.append({
            "chapter_num": i,
            "chapter_title": ch_title or f"第{i}话",
        })

    return {
        "title": title,
        "cover_url": cover,
        "description": description,
        "category": category,
        "status": status,
        "chapters": chapters,
    }


def search(keyword: str, timeout_ms: int = 45000) -> List[Dict[str, str]]:
    """搜索咚漫漫画，返回 [{title, url}]

    搜索页: https://www.dongmanmanhua.cn/search?keyword=<关键词>&searchMode=TITLE
    搜索结果中的链接为 /episodeList?titleNo=<id>，需转换为标准 list URL。
    """
    timeout = timeout_ms / 1000
    search_url = f"{BASE_URL}/search?keyword={quote(keyword, safe='')}&searchMode=TITLE"

    try:
        resp = httpx.get(
            search_url, timeout=timeout, follow_redirects=True, headers=HEADERS
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise DongmanmanhuaCrawlError(f"搜索请求失败: {e}") from e

    sel = Selector(resp.text)
    results: List[Dict[str, str]] = []
    seen_urls: set = set()

    # 搜索结果中的漫画链接：/episodeList?titleNo=<id>
    for a in sel.css("a[href*='episodeList']"):
        href = a.attrib.get("href", "") or ""
        text = (a.css("::text").get() or "").strip()
        if not text:
            # 尝试从子元素获取文本
            text = (a.css("img::attr(alt)").get() or "").strip()
        if href and text and keyword in text:
            full_url = href if href.startswith("http") else BASE_URL + href
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                results.append({"title": text, "url": full_url})

    # 也尝试匹配标准 list URL 格式
    for a in sel.css("a[href*='list?title_no']"):
        href = a.attrib.get("href", "") or ""
        text = (a.css("::text").get() or "").strip()
        if not text:
            text = (a.css("img::attr(alt)").get() or "").strip()
        if href and text and keyword in text:
            full_url = href if href.startswith("http") else BASE_URL + href
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                results.append({"title": text, "url": full_url})

    return results


# 多源统一接口（供 registry 调度）
HAS_SEARCH = True
