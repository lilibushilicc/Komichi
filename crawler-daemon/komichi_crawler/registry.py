"""多源注册表（CLI 类接口 + daemon 模块接口 共用）

- 类接口（CLI 使用）：register_source 装饰器注册 BaseCrawler 子类，
  提供 get_crawler / source_for_url / crawl_with_fallback（交互式确认 + 换备）/ describe_sources。
- 模块接口（daemon 使用）：源模块声明 NAME / DOMAINS / is_supported / crawl(url, timeout_ms) /
  search(keyword, timeout_ms) / HAS_SEARCH，提供 resolve_source / get_source /
  supported_names / search_all。注册类时自动登记其所在模块。

新增源只需：实现模块接口（可选类接口）-> 在 __init__.py 导入 -> 注册类 -> 加入 source_priority。
"""
from __future__ import annotations

import sys
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

from .base import BaseCrawler, CrawlError, SourceNotFound, WorkInfo

# 关键词导入的默认源优先级（未配置 source_priority 时使用）
DEFAULT_SOURCE_ORDER = [
    "godamh", "mh160mh", "guazi", "kuaikan", "tencent", "bilibili",
    "dongmanmanhua", "sfacg",
]


class SourceRegistry:
    """源注册表：维护 name -> 爬虫类 的有序映射"""

    def __init__(self) -> None:
        self._sources: Dict[str, Type[BaseCrawler]] = {}
        self._modules: Dict[str, Any] = {}
        self._domains: Dict[str, str] = {}

    def register(self, crawler_cls: Type[BaseCrawler]) -> Type[BaseCrawler]:
        """注册一个爬虫源（装饰器用法），并登记其域名映射与所在模块"""
        name = crawler_cls.name
        if not name or name == "base":
            raise ValueError(f"爬虫 {crawler_cls.__name__} 必须声明 name")
        self._sources[name] = crawler_cls
        for domain in crawler_cls.domains or []:
            self._domains[domain.lower()] = name
        # 类所在模块若实现了模块接口（crawl/NAME），同时登记供 daemon 使用
        mod = sys.modules.get(crawler_cls.__module__)
        if mod is not None and hasattr(mod, "NAME") and hasattr(mod, "crawl"):
            self._modules[name] = mod
        return crawler_cls

    # ------------------------------------------------------------
    # 查询（类接口）
    # ------------------------------------------------------------
    def list_sources(self) -> List[str]:
        """返回所有已注册源的名字（按注册顺序）"""
        return list(self._sources.keys())

    def get(self, name: str) -> Optional[Type[BaseCrawler]]:
        """按名字获取爬虫类，未注册返回 None"""
        return self._sources.get(name)

    def resolve_name(self, url: str) -> Optional[str]:
        """根据 URL 的域名反查源名字，未匹配返回 None"""
        try:
            host = url.split("/", 3)[2].lower()
        except IndexError:
            return None
        for domain, name in self._domains.items():
            if host == domain or host.endswith("." + domain):
                return name
        return None

    def build_crawler(
        self, name: str, source: str, title: str = "", category: str = "", cover: str = ""
    ) -> BaseCrawler:
        """按名字构造爬虫实例，未注册抛出 ValueError"""
        cls = self._sources.get(name)
        if not cls:
            raise ValueError(
                f"未知源: {name}。可用源: {', '.join(self.list_sources()) or '(无)'}"
            )
        return cls(source=source, title=title, category=category, cover=cover)

    # ------------------------------------------------------------
    # 查询（模块接口，daemon 使用）
    # ------------------------------------------------------------
    def list_modules(self) -> List[Any]:
        """返回所有实现了模块接口的源模块（按注册顺序）"""
        return [self._modules[n] for n in self._sources if n in self._modules]

    def get_module(self, name: str) -> Optional[Any]:
        """按源名获取模块，未注册返回 None"""
        return self._modules.get(name)

    def resolve_module(self, url: str) -> Optional[Any]:
        """按 URL 匹配源模块（逐模块 is_supported，语义与 daemon 旧版一致）"""
        for mod in self.list_modules():
            try:
                if mod.is_supported(url):
                    return mod
            except Exception:
                continue
        return None


REGISTRY = SourceRegistry()

# 关键词导入优先级：可被 CLI 侧注入（读取 ~/.komichi/config.json 的 source_priority）
_priority_provider: Optional[Callable[[], Any]] = None


def set_source_priority_provider(fn: Optional[Callable[[], Any]]) -> None:
    """注册 source_priority 配置提供者（CLI 兼容层调用）"""
    global _priority_provider
    _priority_provider = fn


def _configured_source_order() -> List[str]:
    if _priority_provider is not None:
        try:
            prio = _priority_provider()
        except Exception:
            prio = None
        if isinstance(prio, str):
            return [s.strip() for s in prio.split(",") if s.strip()]
        if isinstance(prio, (list, tuple)) and prio:
            return [str(s).strip() for s in prio if str(s).strip()]
    return list(DEFAULT_SOURCE_ORDER)


# ============================================================
# 类接口（CLI 使用）
# ============================================================
def list_sources() -> List[str]:
    """列出所有可用源名字"""
    return REGISTRY.list_sources()


def get_crawler(name: str, source: str, title: str = "", category: str = "", cover: str = "") -> BaseCrawler:
    """构造指定源的爬虫实例"""
    return REGISTRY.build_crawler(name, source, title=title, category=category, cover=cover)


def source_for_url(url: str) -> Optional[str]:
    """根据 URL 匹配源名字（godamh.com -> godamh），未匹配返回 None"""
    return REGISTRY.resolve_name(url)


def crawl_with_fallback(
    query: str,
    sources: Optional[Union[str, List[str]]] = None,
    title: str = "",
    category: str = "",
    cover: str = "",
    confirm: Optional[Callable[[str, WorkInfo], bool]] = None,
) -> Tuple[WorkInfo, str]:
    """抓取作品，支持源自动换备。

    规则：
      1. query 为 http(s) URL 时按域名匹配源，不参与换备；
      2. query 为关键词时按 sources（默认取配置 source_priority）顺序逐个尝试，
         仅使用站点源（跳过 local / url 等非站点源）；
      3. 提供 confirm 回调时，每个源成功抓取后先调用 confirm(source_name, work)，
         返回 False 则换下一个源（用于 CLI 交互式确认）；
      4. 全部失败时抛出 SourceNotFound，附带各源的具体失败原因。
    返回 (WorkInfo, source_name)。
    """
    q = query.strip()
    errors: List[str] = []

    if q.lower().startswith(("http://", "https://")):
        name = source_for_url(q)
        if not name:
            raise SourceNotFound(
                f"无法从 URL 识别来源: {q}\n"
                f"可用源: {', '.join(list_sources()) or '(无)'}\n"
                f"或使用: komichi-cli import from <source> <URL>"
            )
        crawler = get_crawler(name, q, title=title, category=category, cover=cover)
        try:
            work = crawler.crawl()
        except CrawlError as e:
            errors.append(f"  [{name}] {e}")
            raise SourceNotFound("所有源均抓取失败:\n" + "\n".join(errors))
        if confirm is not None and not confirm(name, work):
            raise SourceNotFound(f"用户拒绝了来自 {name} 的抓取结果")
        return work, name

    # 关键词：按优先级换备
    if isinstance(sources, str):
        source_names = [s.strip() for s in sources.split(",") if s.strip()]
    elif sources is None:
        source_names = _configured_source_order()
    else:
        source_names = list(sources)

    # 仅保留已注册的站点源
    site_names = [
        n for n in source_names
        if REGISTRY.get(n) and n not in ("local", "url")
    ]
    if not site_names:
        raise SourceNotFound(
            f"没有可用的站点源（当前配置: {', '.join(source_names) or '(空)'}）\n"
            f"可用源: {', '.join(list_sources()) or '(无)'}"
        )

    for name in site_names:
        crawler = get_crawler(name, q, title=title, category=category, cover=cover)
        try:
            work = crawler.crawl()
        except CrawlError as e:
            errors.append(f"  [{crawler.display_name or name}] {e}")
            continue
        if confirm is not None:
            try:
                accepted = confirm(name, work)
            except (TypeError, ValueError, KeyError, OSError) as e:
                # confirm 回调自身异常时记录并视为接受，避免阻断换备流程
                errors.append(
                    f"  [{crawler.display_name or name}] 确认回调异常: {type(e).__name__}: {e}"
                )
                accepted = True
            if not accepted:
                errors.append(f"  [{crawler.display_name or name}] 用户拒绝，换下一个源")
                continue
        return work, name

    raise SourceNotFound(
        f"关键词「{q}」在以下源均未找到:\n" + "\n".join(errors)
    )


def register_source(crawler_cls: Type[BaseCrawler]) -> Type[BaseCrawler]:
    """注册源（供 crawler 模块内部装饰使用）"""
    return REGISTRY.register(crawler_cls)


def describe_sources() -> List[Tuple[str, str, List[str]]]:
    """返回 [(name, display_name, domains), ...] 用于展示"""
    return [
        (name, cls.display_name or name, list(cls.domains or []))
        for name, cls in REGISTRY._sources.items()
    ]


# ============================================================
# 模块接口（daemon 使用）
# ============================================================
def get_source(name: str) -> Optional[Any]:
    """按源名获取模块（runner 追更分发用）"""
    return REGISTRY.get_module(name)


def resolve_source(url: str) -> Optional[Any]:
    """按 URL 域名匹配源模块（runner import / server 搜索用）"""
    return REGISTRY.resolve_module(url)


def supported_names() -> List[str]:
    """所有已注册的站点源名（daemon 可爬取范围）"""
    return [name for name in REGISTRY.list_sources() if name in REGISTRY._modules]


def search_sources() -> List[Any]:
    """有搜索能力的源模块（声明了 HAS_SEARCH = True）"""
    return [m for m in REGISTRY.list_modules() if getattr(m, "HAS_SEARCH", False)]


def search_all(keyword: str, timeout_ms: int = 45000) -> Dict[str, List[Dict[str, str]]]:
    """对所有有搜索能力的源执行搜索，返回 {源名: [{title, url}]}。

    单个源失败不影响其他源，失败的源返回空列表。
    """
    results: Dict[str, List[Dict[str, str]]] = {}
    for src in search_sources():
        try:
            results[src.NAME] = src.search(keyword, timeout_ms=timeout_ms)
        except Exception:
            results[src.NAME] = []
    return results
