"""多源注册表与换备机制

- 所有爬虫源在此注册，通过 name 唯一标识。
- 提供 URL 域名自动匹配（source_for_url）与关键词多源自动换备（crawl_with_fallback）。
- 新增源只需：实现 BaseCrawler 子类 -> 在 __init__.py 导入 -> 注册 -> 加入 config 的 source_priority。
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple, Type, Union

from .. import config as cfg_module
from .base import BaseCrawler, CrawlError, SourceNotFound, SourceUnavailable, WorkInfo


class SourceRegistry:
    """源注册表：维护 name -> 爬虫类 的有序映射"""

    def __init__(self) -> None:
        self._sources: Dict[str, Type[BaseCrawler]] = {}
        self._domains: Dict[str, str] = {}

    def register(self, crawler_cls: Type[BaseCrawler]) -> Type[BaseCrawler]:
        """注册一个爬虫源（装饰器用法），并登记其域名映射"""
        name = crawler_cls.name
        if not name or name == "base":
            raise ValueError(f"爬虫 {crawler_cls.__name__} 必须声明 name")
        self._sources[name] = crawler_cls
        for domain in crawler_cls.domains or []:
            self._domains[domain.lower()] = name
        return crawler_cls

    # ------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------
    def list_sources(self) -> List[str]:
        """返回所有已注册源的名字（按注册顺序）"""
        return list(self._sources.keys())

    def get(self, name: str) -> Optional[Type[BaseCrawler]]:
        """按名字获取爬虫类，未注册返回 None"""
        return self._sources.get(name)

    def resolve_url(self, url: str) -> Optional[str]:
        """根据 URL 的域名反查源名字，未匹配返回 None"""
        host = url.split("/", 3)[2].lower()
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


REGISTRY = SourceRegistry()


# ------------------------------------------------------------
# 公共接口
# ------------------------------------------------------------
def list_sources() -> List[str]:
    """列出所有可用源名字"""
    return REGISTRY.list_sources()


def get_crawler(name: str, source: str, title: str = "", category: str = "", cover: str = "") -> BaseCrawler:
    """构造指定源的爬虫实例"""
    return REGISTRY.build_crawler(name, source, title=title, category=category, cover=cover)


def source_for_url(url: str) -> Optional[str]:
    """根据 URL 匹配源名字（godamh.com -> godamh），未匹配返回 None"""
    return REGISTRY.resolve_url(url)


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
        prio = cfg_module.get("source_priority", [])
        if isinstance(prio, str):
            source_names = [s.strip() for s in prio.split(",") if s.strip()]
        elif isinstance(prio, (list, tuple)):
            source_names = [str(s).strip() for s in prio if str(s).strip()]
        else:
            source_names = []
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
            except Exception:
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
