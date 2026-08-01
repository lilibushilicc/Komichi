"""import 命令组：多源漫画导入

子命令：
    import local <path>         从本地文件夹导入
    import url <work_url>       从 URL 导入（.txt/.json manifest）
    import godamh <keyword>     等价于 import from godamh
    import from <src> <query>   从指定源导入
    import auto <query>         自动识别源（URL 按域名 / 关键词按优先级换备，隐藏命令）
    import <URL|关键词>         ImportGroup 兜底，等价于 import auto
"""
from __future__ import annotations

import json
import sys
from typing import Optional, Tuple

import click
from rich.panel import Panel

from .. import config
from ..api import APIClient
from ..api.client import APIError, NetworkError
from ..crawler import (
    CrawlError,
    GodamhCrawler,
    LocalCrawler,
    SourceNotFound,
    SourceUnavailable,
    UrlCrawler,
    WorkInfo,
    crawl_with_fallback,
    get_crawler,
)
from ..display import (
    _build_confirm,
    _save_import_result,
    _show_import_result,
    render_chapter_table,
    render_work_panel,
)
from ..groups import DefaultGroup
from ..staging import work_to_staging
from ..theme import console, print_interrupted, status_badge


def _interactive() -> bool:
    """判断当前是否为交互式终端"""
    try:
        return sys.stdin.isatty()
    except (AttributeError, OSError):
        return False


def _confirm_import(work: WorkInfo, source: str, title: str = "确认导入这个作品？") -> bool:
    """展示作品信息并询问是否导入，返回 True 表示确认"""
    render_work_panel(work, source=source, title="导入预览")
    render_chapter_table(work.chapters)
    return click.confirm(title, default=True)


class ImportGroup(DefaultGroup):
    """import 命令组：支持 `import <URL|关键词>` 直接自动选择源

    首参不是已注册子命令（local/url/from/godamh）时，
    视为 URL 或关键词交给自动导入命令（按域名识别 / 按优先级换备）。
    无参时显示帮助（退出码 0）。
    """

    def get_command(self, ctx, cmd_name):
        cmd = super().get_command(ctx, cmd_name)
        if cmd is not None:
            return cmd
        ctx.meta.setdefault("auto_query", []).append(cmd_name)
        return import_auto


@click.group(name="import", cls=ImportGroup, default_cmd=None)
def import_group() -> None:
    """导入漫画（多源，URL 自动识别 / 关键词自动换备）"""
    pass


@import_group.command("local")
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=str),
)
@click.option("--title", default=None, help="作品标题（默认取文件夹名）")
@click.option("--category", default="", help="作品分类")
@click.option(
    "--cover",
    "cover",
    type=click.Path(exists=True, dir_okay=False, path_type=str),
    default=None,
    help="封面图片路径",
)
def import_local(path: str, title: Optional[str], category: str, cover: Optional[str]) -> None:
    """从本地文件夹导入漫画"""
    console.print(f"[info]扫描本地文件夹: {path}[/info]")
    try:
        with console.status("[info]扫描中...[/info]"):
            crawler = LocalCrawler(
                source=path, title=title or "", category=category, cover=cover or ""
            )
            work = crawler.crawl()
    except (FileNotFoundError, NotADirectoryError, ValueError) as e:
        raise click.ClickException(str(e))
    except KeyboardInterrupt:
        print_interrupted()
        raise click.Abort()

    _show_import_result(work, source="local")
    _save_import_result(work, source="local")


@import_group.command("url")
@click.argument("work_url")
@click.option("--title", default=None, help="作品标题")
@click.option("--category", default="", help="作品分类")
def import_url(work_url: str, title: Optional[str], category: str) -> None:
    """从 URL 导入漫画（支持 .txt 图片URL列表 或 .json manifest）"""
    console.print(f"[info]尝试从 URL 导入: {work_url}[/info]")
    crawler = UrlCrawler(source=work_url, title=title or "", category=category)
    try:
        with console.status("[info]正在抓取 URL 内容...[/info]"):
            work = crawler.crawl()
    except NotImplementedError as e:
        console.print(f"[warning]{e}[/warning]")
        raise click.Abort()
    except NetworkError as e:
        raise click.ClickException(str(e))
    except (ValueError, json.JSONDecodeError) as e:
        raise click.ClickException(f"解析失败: {e}")
    except KeyboardInterrupt:
        print_interrupted()
        raise click.Abort()

    console.print(
        f"[success]导入成功: {work.title} | 章节 {len(work.chapters)}[/success]"
    )
    staging = work_to_staging(work, source="url")
    out, slug = config.save_staging(staging)
    console.print(f"[success]已保存本地暂存: {slug}[/success]")
    console.print(f"[dim]暂存文件: {out}[/dim]")


@import_group.command("godamh")
@click.argument("keyword")
@click.option("--title", default=None, help="作品标题（默认从网页抓取）")
@click.option("--category", default="", help="作品分类")
@click.option("--cover", default=None, help="封面 URL（默认从网页抓取）")
def import_godamh(keyword: str, title: Optional[str], category: str, cover: Optional[str]) -> None:
    """从 godamh.com 导入漫画（等价于 `import from godamh <keyword>`）"""
    try:
        _import_from_source("godamh", keyword, title=title, category=category, cover=cover)
    except KeyboardInterrupt:
        print_interrupted()
        raise click.Abort()
    except SourceUnavailable as e:
        raise click.ClickException(str(e))


@import_group.command("from")
@click.argument("source")
@click.argument("query")
@click.option("--title", default=None, help="作品标题（默认从网页抓取）")
@click.option("--category", default="", help="作品分类")
@click.option("--cover", default=None, help="封面 URL（默认从网页抓取）")
def import_from(source: str, query: str, title: Optional[str], category: str, cover: Optional[str]) -> None:
    """从指定源导入漫画（SOURCE: godamh / mh160mh / ...）

    QUERY 为作品 URL 或关键词（取决于源是否支持站内搜索）。
    """
    try:
        _import_from_source(source, query, title=title, category=category, cover=cover)
    except KeyboardInterrupt:
        print_interrupted()
        raise click.Abort()
    except SourceUnavailable as e:
        raise click.ClickException(str(e))


@import_group.command("auto", hidden=True)
@click.option("--title", default=None, help="作品标题（默认从网页抓取）")
@click.option("--category", default="", help="作品分类")
@click.option("--cover", default=None, help="封面 URL（默认从网页抓取）")
@click.option(
    "--sources",
    default=None,
    help="指定源顺序，如 godamh,mh160mh（默认按配置 source_priority 自动换备）",
)
@click.option("--yes", "assume_yes", is_flag=True, help="跳过抓取结果确认（默认交互式确认）")
@click.option(
    "--via",
    type=click.Choice(["local", "worker"]),
    default="local",
    help="爬取模式：local=CLI本地爬取（默认），worker=Worker端爬取",
)
@click.argument("query", nargs=-1, required=False)
@click.pass_context
def import_auto(ctx: click.Context, query: Tuple[str, ...], title: Optional[str], category: str, cover: Optional[str], sources: Optional[str], assume_yes: bool, via: str) -> None:
    """自动导入：URL 按域名识别源，关键词按优先级换备（内部命令）"""
    extra = ctx.meta.get("auto_query", [])
    q = (" ".join(extra) + " " + " ".join(query)).strip()
    if not q:
        raise click.ClickException("缺少作品 URL 或关键词，例如: komichi-cli import https://xxx / komichi-cli import 海贼王")
    try:
        if via == "worker":
            _import_via_worker(q, assume_yes=assume_yes)
        else:
            _import_auto(q, title=title, category=category, cover=cover, sources=sources, assume_yes=assume_yes)
    except KeyboardInterrupt:
        print_interrupted()
        raise click.Abort()


def _import_auto(
    query: str,
    title: Optional[str] = None,
    category: str = "",
    cover: Optional[str] = None,
    sources: Optional[str] = None,
    assume_yes: bool = False,
) -> None:
    """自动导入：URL 域名识别 / 关键词按优先级换备（关键词时交互式确认）"""
    console.print(f"[info]自动导入: {query}[/info]")
    is_keyword = not query.strip().lower().startswith(("http://", "https://"))
    # 关键词导入：复用 _build_confirm 的逐源确认
    # URL 导入：抓取后单独弹一次确认（不参与换备，确认后保存）
    confirm = _build_confirm(query.strip(), assume_yes) if is_keyword else None
    try:
        with console.status("[info]正在抓取作品信息...[/info]"):
            work, source = crawl_with_fallback(
                query,
                sources=sources,
                title=title or "",
                category=category,
                cover=cover or "",
                confirm=confirm,
            )
    except SourceNotFound as e:
        raise click.ClickException(str(e))

    console.print(f"[success]来源: {source}[/success]")
    _show_import_result(work, source)

    # URL 导入（非关键词、非 --yes）在交互式终端下二次确认
    if not is_keyword and not assume_yes and _interactive():
        if not _confirm_import(work, source):
            console.print("[warning]已取消导入（未保存暂存）[/warning]")
            raise click.Abort()

    _save_import_result(work, source)


def _import_from_source(
    source: str,
    query: str,
    title: Optional[str] = None,
    category: str = "",
    cover: Optional[str] = None,
) -> None:
    """从指定源导入并保存暂存"""
    console.print(f"[info]从源 {source} 导入: {query}[/info]")
    try:
        with console.status("[info]正在抓取作品信息...[/info]"):
            crawler = get_crawler(
                source, query, title=title or "", category=category, cover=cover or ""
            )
            work = crawler.crawl()
    except (CrawlError, ValueError, NotImplementedError) as e:
        raise click.ClickException(str(e))
    except (OSError, RuntimeError) as e:
        # 收敛未预期的运行时异常为业务异常，保留原因链
        raise SourceUnavailable(f"爬取失败: {type(e).__name__}: {e}") from e
    _show_import_result(work, source)
    _save_import_result(work, source)


def _import_via_worker(query: str, assume_yes: bool = False) -> None:
    """通过 Worker 端爬取并导入（--via worker 模式）

    - URL：直接调用 Worker import 接口
    - 关键词：先搜索源站，选择后导入
    """
    is_url = query.strip().lower().startswith(("http://", "https://"))
    client = APIClient()

    if is_url:
        # URL 直接交给 Worker 导入
        console.print(f"[info]通过 Worker 导入: {query}[/info]")
        if not assume_yes and _interactive():
            if not click.confirm("确认通过 Worker 导入这个 URL？", default=True):
                console.print("[warning]已取消[/warning]")
                raise click.Abort()
        try:
            with console.status("[info]Worker 正在爬取并导入...[/info]"):
                result = client.import_via_worker(query)
        except (APIError, NetworkError) as e:
            raise click.ClickException(str(e))
        _show_worker_import_result(result)
    else:
        # 关键词：先搜索再选择
        console.print(f"[info]通过 Worker 搜索源站: {query}[/info]")
        try:
            with console.status("[info]正在搜索源站...[/info]"):
                data = client.search_via_worker(query)
        except (APIError, NetworkError) as e:
            raise click.ClickException(str(e))

        results = data.get("results") or {} if isinstance(data, dict) else {}
        if not results:
            console.print("[warning]未找到搜索结果[/warning]")
            return

        # 展示搜索结果
        from rich.table import Table
        table = Table(title=f"源站搜索结果: {query}")
        table.add_column("序号", justify="right", style="cyan")
        table.add_column("来源")
        table.add_column("标题")
        table.add_column("URL", overflow="fold")

        flat: list[tuple[str, str, str]] = []
        idx = 0
        for source, items in results.items():
            for item in items:
                flat.append((source, item.get("title", ""), item.get("url", "")))
                idx += 1
                table.add_row(str(idx), source, item.get("title", ""), item.get("url", ""))

        console.print(table)
        if not flat:
            console.print("[warning]搜索结果为空[/warning]")
            return

        # 选择
        choice = click.prompt("输入序号选择要导入的作品（0 取消）", type=int, default=0)
        if choice <= 0 or choice > len(flat):
            console.print("[warning]已取消[/warning]")
            raise click.Abort()

        _, title, url = flat[choice - 1]
        console.print(f"[info]选择: {title}[/info]")
        try:
            with console.status("[info]Worker 正在爬取并导入...[/info]"):
                result = client.import_via_worker(url)
        except (APIError, NetworkError) as e:
            raise click.ClickException(str(e))
        _show_worker_import_result(result)


def _show_worker_import_result(result: dict) -> None:
    """展示 Worker 导入结果"""
    if not result:
        console.print("[warning]Worker 返回空结果[/warning]")
        return
    work_id = result.get("work_id", "?")
    title = result.get("title", "?")
    source = result.get("source", "?")
    chapter_count = result.get("chapter_count", 0)
    new_chapters = result.get("new_chapters", 0)
    console.print(
        Panel.fit(
            f"[bold]{title}[/bold]\n"
            f"作品 ID: {work_id}    来源: {source}\n"
            f"总章节: {chapter_count}    新增: {new_chapters}",
            title="Worker 导入结果",
        )
    )
    console.print("[success]导入完成（数据已直接写入 Worker D1）[/success]")
