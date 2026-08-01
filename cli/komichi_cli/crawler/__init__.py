"""爬虫兼容层（CLI → 共享包 komichi_crawler）

实现已合并至 crawler-daemon/komichi_crawler/（开发环境由 komichi_cli/__init__.py
自动加入 sys.path），本模块仅做再导出，并注册 CLI 配置
（~/.komichi/config.json 的 source_priority）为关键词导入的源优先级。
"""
from __future__ import annotations

import komichi_crawler.registry as _registry

from komichi_crawler import (  # noqa: F401,E402
    BaseCrawler,
    BilibiliCrawler,
    ChapterInfo,
    CrawlError,
    GodamhCrawler,
    GuaziCrawler,
    KuaikanCrawler,
    LocalCrawler,
    Mh160mhCrawler,
    SourceNotFound,
    SourceUnavailable,
    TencentCrawler,
    UrlCrawler,
    WorkInfo,
    crawl_with_fallback,
    describe_sources,
    get_crawler,
    list_sources,
    source_for_url,
)

from .. import config as _cfg  # noqa: E402

_registry.set_source_priority_provider(
    lambda: _cfg.load_config().get("source_priority")
)

__all__ = [
    "BaseCrawler",
    "BilibiliCrawler",
    "ChapterInfo",
    "CrawlError",
    "GodamhCrawler",
    "GuaziCrawler",
    "KuaikanCrawler",
    "LocalCrawler",
    "Mh160mhCrawler",
    "SourceNotFound",
    "SourceUnavailable",
    "TencentCrawler",
    "UrlCrawler",
    "WorkInfo",
    "crawl_with_fallback",
    "describe_sources",
    "get_crawler",
    "list_sources",
    "source_for_url",
]
