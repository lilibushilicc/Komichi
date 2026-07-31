"""爬虫模块"""
from .base import BaseCrawler, ChapterInfo, CrawlError, SourceNotFound, SourceUnavailable, WorkInfo
from .bilibili import BilibiliCrawler
from .generic import LocalCrawler, UrlCrawler
from .godamh import GodamhCrawler
from .guazi import GuaziCrawler
from .kuaikan import KuaikanCrawler
from .mh160mh import Mh160mhCrawler
from .tencent import TencentCrawler
from .registry import (
    crawl_with_fallback,
    describe_sources,
    get_crawler,
    list_sources,
    source_for_url,
)

__all__ = [
    "BaseCrawler",
    "ChapterInfo",
    "CrawlError",
    "SourceNotFound",
    "SourceUnavailable",
    "WorkInfo",
    "LocalCrawler",
    "UrlCrawler",
    "GodamhCrawler",
    "GuaziCrawler",
    "KuaikanCrawler",
    "Mh160mhCrawler",
    "TencentCrawler",
    "BilibiliCrawler",
    "list_sources",
    "describe_sources",
    "get_crawler",
    "source_for_url",
    "crawl_with_fallback",
]
