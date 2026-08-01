"""哔哩哔哩漫画 (manga.bilibili.com) 爬虫 — CLI 类接口 + daemon 模块接口共用

该站为 SPA，详情接口带 JS/WASM 加密签名（ultra_sign / m2），响应中的 bytesData
也需浏览器内解密，纯 HTTP 无法抓取。因此通过 Playwright 驱动真实 Chromium
渲染页面后从 DOM 提取：
- 作品详情: https://manga.bilibili.com/detail/mc<comic_id>
- 搜索:     https://manga.bilibili.com/search?keyword=<关键词>

依赖：pip install playwright && python -m playwright install chromium
"""
from __future__ import annotations

import re
from typing import Any, Dict, List
from urllib.parse import urlparse

from ._http import BROWSER_UA
from .base import (
    BaseCrawler,
    SourceNotFound,
    SourceUnavailable,
    WorkInfo,
    crawl_work,
)
from .registry import register_source

# 模块接口（供 registry 调度）
NAME = "bilibili"
DOMAINS = ["manga.bilibili.com"]
HAS_SEARCH = True

DETAIL_RE = re.compile(r"/detail/mc(\d+)")
BASE_URL = "https://manga.bilibili.com"

PLAYWRIGHT_HINT = (
    "该爬虫需要 Playwright + Chromium。\n"
    "请先安装: pip install playwright && python -m playwright install chromium\n"
    "ARM 平台(如 Oracle Cloud Ampere)还需: python -m playwright install-deps chromium"
)

PAGINATE_JS = """
async () => {
  const collect = () => {
    const out = [];
    const seen = new Set();
    for (const list of document.querySelectorAll('.list-data')) {
      for (const btn of list.querySelectorAll('button.list-item')) {
        const short = (btn.querySelector('.short-title')?.textContent || '').trim();
        const title = (btn.querySelector('.title')?.textContent || '').trim();
        const key = short + '|' + title;
        if (!seen.has(key)) { seen.add(key); out.push({short, title}); }
      }
    }
    return out;
  };

  const out = { chapters: collect() };

  const headerBtns = [...document.querySelectorAll('button.header-item')]
    .filter(b => /^\\d+ - \\d+$/.test((b.textContent || '').trim()));
  for (const btn of headerBtns) {
    if (btn.classList.contains('selected')) continue;
    const before = document.querySelectorAll('.list-data').length;
    btn.click();
    let loaded = false;
    for (let i = 0; i < 60; i++) {
      await new Promise(r => setTimeout(r, 100));
      if (document.querySelectorAll('.list-data').length > before) { loaded = true; break; }
    }
    if (loaded) out.chapters = collect();
  }

  const h1 = document.querySelector('h1.manga-title');
  out.title = (h1 && h1.textContent.trim().replace(/ - \\u54d4\\u54e9\\u54d4\\u54e9\\u6f2b\\u753b$/, '')) || '';
  out.author = (document.querySelector('h2.author-name')?.textContent || '').trim();
  out.cover = (document.querySelector('img.manga-cover')?.src || '');
  out.statusText = (document.querySelector('.status')?.textContent || '').trim();
  out.tags = [...document.querySelectorAll('.tag-list .tag')]
    .map(e => e.textContent.trim()).filter(Boolean);
  out.desc = (document.querySelector('.introduction-text')?.textContent || '').trim();
  return out;
}
"""

SEARCH_JS = """
async () => {
  const collect = () => {
    const out = [];
    const seen = new Set();
    for (const a of document.querySelectorAll('a[href*="/detail/mc"]')) {
      const title = (a.textContent || '').trim().replace(/\\s+/g, ' ');
      if (!title || seen.has(title)) continue;
      seen.add(title);
      const m = a.href.match(/\\/detail\\/mc(\\d+)/);
      if (m) out.push({title, comic_id: m[1]});
      if (out.length >= 10) break;
    }
    return out;
  };
  let out = collect();
  for (let i = 0; i < 50 && out.length === 0; i++) {
    await new Promise(r => setTimeout(r, 200));
    out = collect();
  }
  return out;
}
"""


def parse_comic_id(source_url: str) -> str:
    m = DETAIL_RE.search(source_url)
    if not m:
        raise SourceNotFound(
            f"无法识别哔哩哔哩漫画作品链接: {source_url}\n"
            f"正确格式: https://manga.bilibili.com/detail/mc<id>"
        )
    return m.group(1)


def is_bilibili_url(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    return host == "manga.bilibili.com" or host.endswith(".bilibili.com")


def _launch_page(timeout_ms: int):
    """启动 Playwright 浏览器，返回 (page, browser)。缺依赖时抛出 SourceUnavailable。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise SourceUnavailable(PLAYWRIGHT_HINT) from e
    p = sync_playwright().start()
    try:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="zh-CN", user_agent=BROWSER_UA)
        page = context.new_page()
        return page, (p, browser)
    except Exception as e:
        p.stop()
        raise SourceUnavailable(f"浏览器启动失败: {type(e).__name__}: {e}") from e


def _close(handle: tuple) -> None:
    p, browser = handle
    try:
        browser.close()
    finally:
        p.stop()


def crawl(source_url: str, timeout_ms: int = 45000) -> Dict[str, Any]:
    """爬取 bilibili 漫画详情页，返回结构化数据。

    返回:
        {
            "title": str,
            "cover_url": str,        # 原始封面 URL（已去除 @参数后缀）
            "description": str,
            "category": str,         # 由 tags 拼接
            "status": "ongoing" | "completed",
            "chapters": [{"chapter_num": int, "chapter_title": str}, ...],
        }
    """
    comic_id = parse_comic_id(source_url)
    url = f"{BASE_URL}/detail/mc{comic_id}"

    page, handle = _launch_page(timeout_ms)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            page.wait_for_selector("h1.manga-title", state="attached", timeout=timeout_ms)
        except Exception as e:
            raise SourceNotFound(
                f"作品页不存在或加载失败: {url} ({type(e).__name__})"
            ) from e
        data: Dict[str, Any] = page.evaluate(PAGINATE_JS)
    except SourceUnavailable:
        raise
    except SourceNotFound:
        raise
    except Exception as e:
        raise SourceUnavailable(f"浏览器执行失败: {type(e).__name__}: {e}") from e
    finally:
        _close(handle)

    title = str(data.get("title") or "").strip()
    if not title:
        raise SourceUnavailable(f"未能解析作品标题: {url}（页面结构可能已变更）")

    cover = str(data.get("cover") or "").strip()
    if cover:
        cover = re.sub(r"@\w+\.\w+$", "", cover)

    status = "completed" if "[完结]" in (data.get("statusText") or "") else "ongoing"

    tags = data.get("tags") or []
    category = " ".join(str(t) for t in tags if t) if tags else ""

    description = str(data.get("desc") or "").strip()

    chapters = _parse_chapters(data.get("chapters") or [])
    if not chapters:
        raise SourceNotFound(f"「{title}」在 manga.bilibili.com 上无章节列表")

    return {
        "title": title,
        "cover_url": cover,
        "description": description,
        "category": category,
        "status": status,
        "chapters": chapters,
    }


def _parse_chapters(items: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """按 DOM 顺序（升序）编号"""
    result: List[Dict[str, Any]] = []
    for it in items:
        short = str(it.get("short") or "").strip()
        title = str(it.get("title") or "").strip()
        name = f"{short} {title}".strip() if short else title
        result.append({
            "chapter_num": len(result) + 1,
            "chapter_title": name or f"第{len(result) + 1}话",
        })
    return result


def search(keyword: str, timeout_ms: int = 45000) -> List[Dict[str, str]]:
    """搜索 bilibili 漫画，返回 [{title, url}]"""
    from urllib.parse import quote

    page, handle = _launch_page(timeout_ms)
    try:
        # 先访问首页建立 buvid cookie，否则搜索被风控拦截
        try:
            page.goto(BASE_URL + "/", wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(4000)
        except Exception:
            pass
        url = f"{BASE_URL}/search?keyword={quote(keyword, safe='')}"
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            page.wait_for_selector('a[href*="/detail/mc"]', state="attached", timeout=timeout_ms)
        except Exception as e:
            raise SourceUnavailable(f"搜索页加载失败: {e}") from e
        results = page.evaluate(SEARCH_JS)
    except SourceUnavailable:
        raise
    except Exception as e:
        raise SourceUnavailable(f"搜索失败: {e}") from e
    finally:
        _close(handle)

    return [
        {"title": r.get("title", ""), "url": f"{BASE_URL}/detail/mc{r['comic_id']}"}
        for r in results
    ]


# 模块接口别名（供 registry 调度）
is_supported = is_bilibili_url


# 类接口（CLI 使用）
@register_source
class BilibiliCrawler(BaseCrawler):
    """哔哩哔哩漫画 爬虫：Playwright 渲染 DOM 提取封面 URL + 章节名称"""

    name = "bilibili"
    display_name = "哔哩哔哩漫画 (manga.bilibili.com)"
    domains = ["manga.bilibili.com"]

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
