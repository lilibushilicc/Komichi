"""爬虫基类、异常与数据模型（CLI 与 crawler-daemon 共用）

本模块是 Komichi 爬虫的单一事实来源：
- 异常体系：CrawlError -> SourceNotFound / SourceUnavailable，供 CLI 换备与 daemon 追更统一捕获
- 数据模型：WorkInfo / ChapterInfo（CLI 类接口使用），模块接口返回同名 dict
- 通用助手：crawl_work() 把「模块接口」包装成「类接口」，避免每个源重复实现
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ._http import DEFAULT_TIMEOUT


class CrawlError(ValueError):
    """爬取失败基类（继承 ValueError，兼容旧 catch 逻辑）"""


class SourceNotFound(CrawlError):
    """源上未找到目标作品（关键词无结果 / 站内搜索不可用），应触发换备"""


class SourceUnavailable(CrawlError):
    """源不可用（网络失败 / 反爬拦截 / 页面解析失败），应触发换备"""


@dataclass
class ChapterInfo:
    """章节数据

    image_paths: 图片来源（本地文件路径或远程图片 URL）
    r2_paths:    上传到 R2 后的对象路径（上传完成后回填）
    """

    chapter_num: int
    chapter_title: str
    image_paths: List[str] = field(default_factory=list)
    r2_paths: List[str] = field(default_factory=list)


@dataclass
class WorkInfo:
    """作品数据"""

    title: str
    category: str = ""
    description: str = ""                # 作品简介
    cover_path: Optional[str] = None     # 封面来源（本地路径或 URL）
    cover_r2_path: Optional[str] = None  # 封面上传到 R2 后的路径
    source_url: str = ""                 # 作品来源（本地目录或抓取 URL）
    status: str = "ongoing"              # 状态：ongoing / completed
    chapters: List[ChapterInfo] = field(default_factory=list)


class BaseCrawler(ABC):
    """爬虫抽象基类，定义统一抓取接口（CLI 类接口）

    子类需声明：
        name         源唯一标识（如 "godamh"），用于 CLI 与配置
        display_name 源展示名称（如 "godamh.com"）
        domains      该源拥有的域名列表，用于 URL 自动匹配
    """

    name: str = "base"
    display_name: str = ""
    domains: List[str] = []

    def __init__(
        self,
        source: str,
        title: str = "",
        category: str = "",
        cover: str = "",
    ):
        self.source = source
        self.title = title
        self.category = category
        self.cover = cover

    @abstractmethod
    def crawl(self) -> WorkInfo:
        """抓取作品信息及所有章节图片，返回 WorkInfo"""
        raise NotImplementedError


# ============================================================
# 模块接口 <-> 类接口 通用转换
# ============================================================

def crawl_work(
    source: str,
    *,
    name: str,
    display_name: str,
    crawl_fn: Callable[..., Dict[str, Any]],
    search_fn: Optional[Callable[..., List[Dict[str, str]]]] = None,
    has_search: bool = False,
    title: str = "",
    category: str = "",
    cover: str = "",
    timeout_ms: int = DEFAULT_TIMEOUT,
) -> WorkInfo:
    """把模块接口（crawl(url, timeout_ms) / search(keyword, timeout_ms)）包装为类接口。

    - source 为 http(s) URL 时直接爬取；
    - source 为关键词且源支持搜索时，搜索后取第一条结果爬取；
    - 源不支持搜索时抛出 SourceNotFound 引导改用 URL 导入。
    返回 WorkInfo（title/category/cover 可用构造参数覆盖）。
    """
    src = source.strip()
    if not src.lower().startswith(("http://", "https://")):
        if has_search and search_fn is not None:
            results = search_fn(src, timeout_ms=timeout_ms) or []
            if not results:
                raise SourceNotFound(
                    f"在 {display_name} 上未找到「{src}」，请改用漫画 URL 导入"
                )
            src = str(results[0].get("url") or "")
        else:
            raise SourceNotFound(
                f"「{src}」: {display_name} 未提供站内搜索，请改用漫画 URL 导入"
            )

    data = crawl_fn(src, timeout_ms=timeout_ms)

    chapters: List[ChapterInfo] = []
    for idx, ch in enumerate(data.get("chapters") or [], start=1):
        chapters.append(
            ChapterInfo(
                chapter_num=int(ch.get("chapter_num") or idx),
                chapter_title=str(ch.get("chapter_title") or f"第{idx}话"),
            )
        )

    return WorkInfo(
        title=title or data.get("title") or "未命名",
        category=category or data.get("category") or "",
        description=data.get("description") or "",
        cover_path=cover or data.get("cover_url") or "",
        source_url=src,
        status=data.get("status") or "ongoing",
        chapters=chapters,
    )
