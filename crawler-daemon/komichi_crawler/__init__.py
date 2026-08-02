"""Komichi 共享爬虫运行时（CLI 与 crawler-daemon 共用）

单一事实来源：
- 8 个站点爬虫（godamh / bilibili / guazi / kuaikan / mh160mh / tencent /
  dongmanmanhua / sfacg），同时暴露「模块接口」（daemon: NAME/DOMAINS/is_supported/crawl/search）
  与「类接口」（CLI: BaseCrawler 子类，支持标题/分类/封面覆盖与交互式换备）。
- Worker API 客户端（WorkerAPI），CLI 通过 komichi_cli.api.client 兼容层复用。

daemon 用法:
    python -m komichi_crawler refresh   # 追更所有 VPS 源作品（cron 调用）
    python -m komichi_crawler import <url>   # 导入新作品
    python -m komichi_crawler serve     # 启动 HTTP 服务（Worker 搜索代理）

CLI 用法（安装 komichi-cli 后）:
    komichi-cli import <url|keyword>    # 自动识别源导入
"""

__version__ = "1.1.0"

from .base import BaseCrawler, ChapterInfo, CrawlError, SourceNotFound, SourceUnavailable, WorkInfo
from .generic import LocalCrawler, UrlCrawler
from .bilibili import BilibiliCrawler
from .godamh import GodamhCrawler
from .guazi import GuaziCrawler
from .kuaikan import KuaikanCrawler
from .mh160mh import Mh160mhCrawler
from .tencent import TencentCrawler
from .dongmanmanhua import DongmanmanhuaCrawler
from .sfacg import SfacgCrawler
from .registry import (
    crawl_with_fallback,
    describe_sources,
    get_crawler,
    get_source,
    list_sources,
    register_source,
    resolve_source,
    search_all,
    search_sources,
    set_source_priority_provider,
    source_for_url,
    supported_names,
)
from .worker_api import APIError, NetworkError, WorkerAPI, set_config_provider

__all__ = [
    "__version__",
    # 异常与数据模型
    "BaseCrawler",
    "ChapterInfo",
    "CrawlError",
    "SourceNotFound",
    "SourceUnavailable",
    "WorkInfo",
    # 类接口（CLI）
    "LocalCrawler",
    "UrlCrawler",
    "GodamhCrawler",
    "GuaziCrawler",
    "KuaikanCrawler",
    "Mh160mhCrawler",
    "TencentCrawler",
    "BilibiliCrawler",
    "DongmanmanhuaCrawler",
    "SfacgCrawler",
    "list_sources",
    "describe_sources",
    "get_crawler",
    "source_for_url",
    "crawl_with_fallback",
    "register_source",
    "set_source_priority_provider",
    # 模块接口（daemon）
    "get_source",
    "resolve_source",
    "supported_names",
    "search_sources",
    "search_all",
    # API 客户端
    "WorkerAPI",
    "APIError",
    "NetworkError",
    "set_config_provider",
]
