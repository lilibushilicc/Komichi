"""快看漫画 (kuaikanmanhua.com) 爬虫

PC 端为 Nuxt SPA，数据走内部 JSON API：
- 作品页:  https://www.kuaikanmanhua.com/web/comic/<comic_id>
- 详情1:   GET /v2/pweb/comic/inner/<comic_id>   → 返回 topic_id
- 详情2:   GET /v2/pweb/topic/<topic_id>         → 作品信息 + 完整章节列表（升序）

注：该站 PC 端搜索接口已失效（/webs/search 404），仅支持 URL 导入。
"""
from __future__ import annotations

import re
from typing import List, Optional

import httpx

from .base import BaseCrawler, ChapterInfo, SourceNotFound, SourceUnavailable, WorkInfo
from .registry import register_source

BASE_URL = "https://www.kuaikanmanhua.com"
API_URL = "https://www.kuaikanmanhua.com/v2/pweb"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": BASE_URL + "/web/comic/",
}

COMIC_RE = re.compile(r"/web/comic/(\d+)")

STATUS_MAP = {
    "连载中": "ongoing",
    "连载": "ongoing",
    "更新中": "ongoing",
    "完结": "completed",
    "已完结": "completed",
    "完结啦": "completed",
}


@register_source
class KuaikanCrawler(BaseCrawler):
    """快看漫画 爬虫：爬取封面 URL + 章节名称，不下载图片"""

    name = "kuaikan"
    display_name = "快看漫画 (kuaikanmanhua.com)"
    domains = ["kuaikanmanhua.com"]

    def crawl(self) -> WorkInfo:
        src = self.source.strip()
        if not src.lower().startswith(("http://", "https://")):
            raise SourceNotFound(
                f"「{src}」: kuaikanmanhua.com 站内搜索不可用，"
                f"请改用漫画 URL 导入。\n"
                f"例如: komichi-cli import https://www.kuaikanmanhua.com/web/comic/847609"
            )
        m = COMIC_RE.search(src)
        if not m:
            raise SourceNotFound(
                f"无法识别快看漫画作品链接: {src}\n"
                f"正确的格式: https://www.kuaikanmanhua.com/web/comic/<id>"
            )
        return self._parse_detail(m.group(1))

    def _get_json(self, url: str) -> dict:
        try:
            resp = httpx.get(url, timeout=30, follow_redirects=True, headers=HEADERS)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise SourceUnavailable(f"请求 {url} 失败: {e}") from e
        if data.get("code") != 200:
            raise SourceUnavailable(
                f"快看接口返回异常 (code={data.get('code')}, msg={data.get('message')}): {url}"
            )
        return data

    def _parse_detail(self, comic_id: str) -> WorkInfo:
        inner = self._get_json(
            f"{API_URL}/comic/inner/{comic_id}?source=&pc_go_app_exp="
        )
        topic = (inner.get("data") or {}).get("topic_info") or {}
        topic_id = topic.get("id")
        if not topic_id:
            raise SourceNotFound(f"快看漫画作品不存在或已下线: {comic_id}")

        detail = self._get_json(
            f"{API_URL}/topic/{topic_id}?source=&pc_go_app_exp="
        )
        info = (detail.get("data") or {}).get("topic_info") or {}
        title = str(info.get("title", "") or "").strip()
        if not title:
            raise SourceUnavailable(
                f"未能解析作品标题: {comic_id}（页面结构可能已变更）"
            )

        cover = self.cover or str(
            info.get("vertical_image_url") or info.get("cover_image_url") or ""
        ).strip()

        status = STATUS_MAP.get(str(info.get("update_status", "")).strip(), "ongoing")
        category = self.category
        if not category and info.get("tags"):
            category = " ".join(str(t) for t in info["tags"] if t)

        description = str(info.get("description") or "").strip()

        chapters = self._parse_chapters(info.get("comics") or [])
        if not chapters:
            raise SourceNotFound(f"「{title}」在 kuaikanmanhua 上无章节列表")

        return WorkInfo(
            title=title,
            category=category or "",
            description=description,
            cover_path=cover or "",
            source_url=f"{BASE_URL}/web/comic/{comic_id}",
            status=status,
            chapters=chapters,
        )

    @staticmethod
    def _parse_chapters(comics: List[dict]) -> List[ChapterInfo]:
        """解析章节列表（接口返回按发布时间升序）"""
        result: List[ChapterInfo] = []
        for c in comics:
            if not isinstance(c, dict) or not c.get("id"):
                continue
            title = str(c.get("title", "") or "").strip()
            result.append(
                ChapterInfo(
                    chapter_num=len(result) + 1,
                    chapter_title=title or f"第{len(result) + 1}话",
                )
            )
        return result
