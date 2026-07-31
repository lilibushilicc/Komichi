"""爬虫模块"""
from .base import BaseCrawler, ChapterInfo, WorkInfo
from .generic import LocalCrawler, UrlCrawler
from .godamh import GodamhCrawler

__all__ = [
    "BaseCrawler",
    "ChapterInfo",
    "WorkInfo",
    "LocalCrawler",
    "UrlCrawler",
    "GodamhCrawler",
]
