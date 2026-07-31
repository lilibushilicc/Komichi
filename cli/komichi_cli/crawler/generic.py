from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import List, Optional

import httpx

from ..api.client import NetworkError
from .base import BaseCrawler, ChapterInfo, WorkInfo

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def _natural_key(s: str) -> List:
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", s)]


def _parse_chapter_num(name: str) -> Optional[int]:
    m = re.search(r"(\d+)", name)
    return int(m.group(1)) if m else None


class LocalCrawler(BaseCrawler):
    """本地文件夹爬虫：扫描子文件夹作为章节，不采集图片"""

    def __init__(self, source: str, title: str = "", category: str = "", cover: str = ""):
        super().__init__(source, title, category, cover)
        self.path = Path(source)
        if not self.path.exists():
            raise FileNotFoundError(f"路径不存在: {source}")
        if not self.path.is_dir():
            raise NotADirectoryError(f"不是目录: {source}")

    def crawl(self) -> WorkInfo:
        title = self.title or self.path.name

        cover_path = self.cover or None
        if not cover_path:
            for candidate in sorted(self.path.iterdir(), key=lambda p: _natural_key(p.name)):
                if candidate.is_file() and candidate.suffix.lower() in IMAGE_EXTS:
                    cover_path = str(candidate)
                    break

        chapters = self.fetch_chapters()
        return WorkInfo(
            title=title,
            category=self.category,
            cover_path=cover_path,
            source_url=str(self.path.resolve()),
            chapters=chapters,
        )

    def fetch_chapters(self) -> List[ChapterInfo]:
        chapters: List[ChapterInfo] = []

        chapter_dirs = sorted(
            [d for d in self.path.iterdir() if d.is_dir()],
            key=lambda p: _natural_key(p.name),
        )

        if not chapter_dirs:
            chapters.append(
                ChapterInfo(
                    chapter_num=1,
                    chapter_title=self.title or self.path.name,
                    image_paths=[],
                )
            )
            return chapters

        parsed = [_parse_chapter_num(d.name) for d in chapter_dirs]
        use_parsed = (
            all(p is not None for p in parsed)
            and len(set(parsed)) == len(parsed)
        )

        for idx, d in enumerate(chapter_dirs, start=1):
            num = parsed[idx - 1] if use_parsed else idx
            chapters.append(
                ChapterInfo(
                    chapter_num=num,
                    chapter_title=d.name,
                    image_paths=[],
                )
            )
        return chapters


class UrlCrawler(BaseCrawler):
    """URL 列表爬虫（预留接口框架）"""

    def crawl(self) -> WorkInfo:
        src = self.source
        if not src:
            raise ValueError("未提供来源 URL")

        if os.path.exists(src):
            return self._crawl_local_file(Path(src))

        if src.lower().startswith(("http://", "https://")):
            return self._crawl_remote(src)

        raise NotImplementedError(
            f"无法识别的来源: {src}。URL 导入目前支持本地/远程 .txt 图片URL列表 或 .json "
            "manifest 文件；具体站点页面解析需实现子类。"
        )

    def _crawl_local_file(self, path: Path) -> WorkInfo:
        ext = path.suffix.lower()
        if ext == ".json":
            with open(path, "r", encoding="utf-8-sig") as f:
                manifest = json.load(f)
            return self._build_from_manifest(manifest)
        if ext == ".txt":
            urls = self._read_url_lines(path.read_text(encoding="utf-8-sig"))
            return self._build_from_urls(urls)
        raise NotImplementedError(f"不支持的本地文件类型: {ext}（仅支持 .txt / .json）")

    def _crawl_remote(self, url: str) -> WorkInfo:
        try:
            resp = httpx.get(url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise NetworkError(f"下载远程资源失败: {e}") from e

        ct = resp.headers.get("content-type", "")
        text = resp.text
        if "json" in ct or url.lower().endswith(".json"):
            try:
                manifest = json.loads(text)
            except json.JSONDecodeError as e:
                raise ValueError(f"远程 JSON 解析失败: {e}") from e
            return self._build_from_manifest(manifest)
        urls = self._read_url_lines(text)
        return self._build_from_urls(urls)

    def _build_from_manifest(self, m: dict) -> WorkInfo:
        title = self.title or m.get("title") or "未命名作品"
        cover = m.get("cover") or self.cover or ""
        chapters: List[ChapterInfo] = []
        for idx, c in enumerate(m.get("chapters", []), start=1):
            chapters.append(
                ChapterInfo(
                    chapter_num=c.get("chapter_num", idx),
                    chapter_title=c.get("title") or c.get("chapter_title") or f"第{idx}章",
                    image_paths=[],
                )
            )
        return WorkInfo(
            title=title,
            category=self.category,
            cover_path=cover,
            source_url=self.source,
            chapters=chapters,
        )

    def _build_from_urls(self, urls: List[str]) -> WorkInfo:
        title = self.title or "未命名作品"
        chapters = [ChapterInfo(chapter_num=1, chapter_title="第1章", image_paths=[])]
        return WorkInfo(
            title=title,
            category=self.category,
            cover_path=self.cover or "",
            source_url=self.source,
            chapters=chapters,
        )

    @staticmethod
    def _read_url_lines(text: str) -> List[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]
