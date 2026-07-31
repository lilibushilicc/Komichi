"""哔哩哔哩漫画 (manga.bilibili.com) 爬虫

该站为 SPA，且详情接口带 JS/WASM 加密签名（ultra_sign / m2），
响应体 bytesData 也需浏览器内解密，纯 HTTP 无法抓取。
因此本爬虫通过 Playwright 驱动真实 Chromium 渲染页面后从 DOM 提取：

- 作品详情: https://manga.bilibili.com/detail/mc<comic_id>
- 搜索:     https://manga.bilibili.com/search?keyword=<关键词>

依赖：pip install playwright && python -m playwright install chromium
未安装时抛出 SourceUnavailable（含安装指引）。
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

from .base import BaseCrawler, ChapterInfo, SourceNotFound, SourceUnavailable, WorkInfo
from .registry import register_source

BASE_URL = "https://manga.bilibili.com"
DETAIL_RE = re.compile(r"/detail/mc(\d+)")

PLAYWRIGHT_HINT = (
    "该源需要浏览器支持（哔哩哔哩漫画接口带 JS 加密签名，无法纯 HTTP 抓取）。\n"
    "请先安装: pip install playwright && python -m playwright install chromium"
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
  out.desc = (document.querySelector('.introduction-text')?.textContent || '').trim();
  out.tags = [...document.querySelectorAll('.tag-list span.manga-styles')]
    .map(e => (e.textContent || '').trim()).filter(Boolean);
  out.statusText = (document.querySelector('.last-update')?.textContent || '').trim();
  const cover = document.querySelector('.header-info img.w-100');
  out.cover = (cover && cover.src) || '';
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


@register_source
class BilibiliCrawler(BaseCrawler):
    """哔哩哔哩漫画 爬虫：Playwright 渲染 DOM 提取封面 URL + 章节名称"""

    name = "bilibili"
    display_name = "哔哩哔哩漫画 (manga.bilibili.com)"
    domains = ["manga.bilibili.com"]

    def crawl(self) -> WorkInfo:
        src = self.source.strip()
        if src.lower().startswith(("http://", "https://")):
            m = DETAIL_RE.search(src)
            if not m:
                raise SourceNotFound(
                    f"无法识别哔哩哔哩漫画作品链接: {src}\n"
                    f"正确的格式: https://manga.bilibili.com/detail/mc<id>"
                )
            return self._with_browser(
                lambda page: self._detail_impl(page, m.group(1))
            )
        return self._with_browser(
            lambda page: self._search_and_detail_impl(page, src)
        )

    # ------------------------------------------------------------
    # Playwright 封装
    # ------------------------------------------------------------
    @staticmethod
    def _with_browser(fn: Callable[["Any"], WorkInfo]) -> WorkInfo:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise SourceUnavailable(PLAYWRIGHT_HINT) from e
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    context = browser.new_context(
                        locale="zh-CN",
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
                        ),
                    )
                    page = context.new_page()
                    return fn(page)
                finally:
                    browser.close()
        except SourceNotFound:
            raise
        except SourceUnavailable:
            raise
        except Exception as e:
            raise SourceUnavailable(f"浏览器执行失败: {type(e).__name__}: {e}") from e

    def _detail_impl(self, page: "Any", comic_id: str) -> WorkInfo:
        url = f"{BASE_URL}/detail/mc{comic_id}"
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_selector("h1.manga-title", state="attached", timeout=20000)
        except Exception as e:
            raise SourceNotFound(f"作品页不存在或加载失败: {url} ({type(e).__name__})") from e

        data: Dict[str, Any] = page.evaluate(PAGINATE_JS)
        title = str(data.get("title") or "").strip()
        if not title:
            raise SourceUnavailable(f"未能解析作品标题: {url}（页面结构可能已变更）")

        cover = self.cover or str(data.get("cover") or "").strip()
        if cover:
            cover = re.sub(r"@\w+\.\w+$", "", cover)

        status = "completed" if "[完结]" in data.get("statusText", "") else "ongoing"

        category = self.category
        if not category and data.get("tags"):
            category = " ".join(str(t) for t in data["tags"] if t)

        description = str(data.get("desc") or "").strip()

        chapters = self._parse_chapters(data.get("chapters") or [])
        if not chapters:
            raise SourceNotFound(f"「{title}」在 manga.bilibili.com 上无章节列表")

        return WorkInfo(
            title=title,
            category=category or "",
            description=description,
            cover_path=cover or "",
            source_url=url,
            status=status,
            chapters=chapters,
        )

    def _search_and_detail_impl(self, page: "Any", keyword: str) -> WorkInfo:
        from urllib.parse import quote

        # 无痕会话先访问首页建立 buvid cookie，否则搜索接口会被风控拦截
        try:
            page.goto(BASE_URL + "/", wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(4000)
        except Exception:
            pass

        url = f"{BASE_URL}/search?keyword={quote(keyword, safe='')}"
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_selector(
                'a[href*="/detail/mc"]', state="attached", timeout=20000
            )
        except Exception as e:
            raise SourceUnavailable(f"搜索页加载失败: {url} ({type(e).__name__})") from e

        results: List[Dict[str, str]] = page.evaluate(SEARCH_JS)
        if not results:
            raise SourceNotFound(f"哔哩哔哩漫画搜索「{keyword}」无结果")
        best = results[0]
        return self._detail_impl(page, str(best["comic_id"]))

    @staticmethod
    def _parse_chapters(items: List[Dict[str, str]]) -> List[ChapterInfo]:
        """按 DOM 顺序（升序）编号"""
        result: List[ChapterInfo] = []
        for it in items:
            short = str(it.get("short") or "").strip()
            title = str(it.get("title") or "").strip()
            name = f"{short} {title}".strip() if short else title
            result.append(
                ChapterInfo(
                    chapter_num=len(result) + 1,
                    chapter_title=name or f"第{len(result) + 1}话",
                )
            )
        return result
