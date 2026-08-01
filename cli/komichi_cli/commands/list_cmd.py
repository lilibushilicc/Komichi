"""list 命令组 + check 命令：作品查询

- list works              列出 Worker 上的所有作品
- list staging            列出本地暂存作品
- check <work_id>         检查作品更新状态（对比本地暂存与 Worker 远程数据）
"""
from __future__ import annotations

from typing import Optional

import click
from rich.panel import Panel
from rich.table import Table

from .. import config
from ..api import APIClient
from ..api.client import APIError, NetworkError
from ..groups import DefaultGroup
from ..theme import console, status_badge
from ..utils import domain_of, format_chapter_range


@click.group(name="list", cls=DefaultGroup, default_cmd="works")
def list_group() -> None:
    """查询作品"""
    pass


@list_group.command("works")
@click.option("--category", default=None, help="按分类过滤（精确匹配）")
@click.option("--status", default=None, help="按状态过滤（ongoing/completed）")
@click.option("--search", default=None, help="按标题关键词模糊搜索")
def list_works(category: Optional[str], status: Optional[str], search: Optional[str]) -> None:
    """列出 Worker 上的所有作品"""
    try:
        client = APIClient()
        works = client.list_works()
    except (APIError, NetworkError) as e:
        raise click.ClickException(str(e))

    if not works:
        console.print("[warning]Worker 上暂无作品[/warning]")
        return

    # 客户端过滤
    filtered = works
    if category is not None:
        cat_q = category.strip().lower()
        filtered = [
            w for w in filtered
            if str(w.get("category", "")).strip().lower() == cat_q
        ]
    if status is not None:
        status_q = status.strip().lower()
        filtered = [
            w for w in filtered
            if str(w.get("status", "")).strip().lower() == status_q
        ]
    if search is not None:
        kw = search.strip().lower()
        filtered = [
            w for w in filtered
            if kw in str(w.get("title", "")).strip().lower()
        ]

    total = len(works)
    shown = len(filtered)
    header = f"作品列表 (共 {total} 个"
    if total != shown:
        header += f"，过滤后 {shown} 个"
    header += ")"

    if not filtered:
        console.print(f"[warning]{header}，但没有匹配过滤条件的作品[/warning]")
        return

    table = Table(title=header)
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("标题")
    table.add_column("分类")
    table.add_column("最新章节", justify="right")
    table.add_column("状态")
    table.add_column("来源")
    for w in filtered:
        table.add_row(
            str(w.get("id", "")),
            str(w.get("title", "")),
            str(w.get("category", "")),
            str(w.get("latest_chapter_num", "")),
            status_badge(str(w.get("status", ""))),
            domain_of(str(w.get("source_url", ""))),
        )
    console.print(table)


@list_group.command("staging")
def list_staging() -> None:
    """列出本地暂存作品（已导入但可能尚未同步到 Worker）"""
    items = config.list_staging()
    if not items:
        console.print("[warning]没有本地暂存作品[/warning]")
        return

    table = Table(title=f"本地暂存作品 (共 {len(items)} 个)")
    table.add_column("Slug", style="cyan", no_wrap=True)
    table.add_column("标题")
    table.add_column("来源")
    table.add_column("远程ID", justify="right")
    table.add_column("章节数", justify="right")
    table.add_column("同步状态")

    for item in items:
        work_id = item.get("work_id")
        sync_status = "[success]已同步[/success]" if work_id else "[warning]未同步[/warning]"
        table.add_row(
            str(item.get("slug", "")),
            str(item.get("title", "")),
            str(item.get("source", "") or "-"),
            str(work_id) if work_id else "-",
            str(len(item.get("chapters", []))),
            sync_status,
        )
    console.print(table)
    console.print(
        f"[dim]暂存目录: {config.get_staging_root()}[/dim]"
    )


def _list_checkable_works() -> None:
    """列出可 check 的作品（远程 + 本地暂存），供用户选择 ID"""
    rows: list[tuple[str, str, str]] = []  # (id, title, source)

    # 远程作品
    try:
        client = APIClient()
        works = client.list_works()
        for w in works:
            rows.append((
                str(w.get("id", "")),
                str(w.get("title", "")),
                f"远程 · {domain_of(str(w.get('source_url', '')))}",
            ))
    except (APIError, NetworkError) as e:
        console.print(f"[warning]无法获取远程作品列表: {e}[/warning]")

    # 本地暂存中未同步的
    for item in config.list_staging():
        wid = item.get("work_id")
        if not wid:
            rows.append((
                str(item.get("slug", "")),
                str(item.get("title", "")),
                f"本地暂存 · {item.get('source', '-')}",
            ))

    if not rows:
        console.print("[warning]没有可检查的作品（远程和本地均无数据）[/warning]")
        return

    table = Table(title=f"可检查作品 (共 {len(rows)} 个)")
    table.add_column("ID / Slug", style="cyan", no_wrap=True)
    table.add_column("标题")
    table.add_column("来源")
    for wid, title, src in rows:
        table.add_row(wid, title, src)
    console.print(table)
    console.print("[dim]用法: check <ID 或 Slug>[/dim]")


@click.command()
@click.argument("work_id", required=False)
@click.option(
    "--via",
    type=click.Choice(["local", "worker"]),
    default="local",
    help="检查模式：local=对比本地暂存与远程（默认），worker=Worker实时爬取源站",
)
def check(work_id: Optional[str], via: str) -> None:
    """检查作品更新状态

    不带参数时列出可用作品 ID 供选择。
    --via worker 时让 Worker 实时爬取源站检查更新（需作品 ID）。
    """
    if not work_id:
        _list_checkable_works()
        return

    if via == "worker":
        _check_via_worker(work_id)
        return

    try:
        client = APIClient()
        remote = client.get_work(work_id)
    except (APIError, NetworkError) as e:
        raise click.ClickException(str(e))

    if not remote:
        console.print(f"[warning]Worker 上未找到作品: {work_id}[/warning]")
        return

    # 兼容 {work: {...}, chapters: [...]} 与直接返回作品对象两种结构
    if isinstance(remote, dict) and "work" in remote and isinstance(remote["work"], dict):
        rwork = remote["work"]
        rchapters = remote.get("chapters", []) or []
    else:
        rwork = remote if isinstance(remote, dict) else {}
        rchapters = remote.get("chapters", []) if isinstance(remote, dict) else []

    console.print(
        Panel.fit(
            f"[bold]{rwork.get('title', '')}[/bold]\n"
            f"ID: {rwork.get('id', work_id)}    分类: {rwork.get('category', '')}\n"
            f"最新章节: {rwork.get('latest_chapter_num', '?')}    "
            f"状态: {status_badge(str(rwork.get('status', '')))}\n"
            f"封面: {rwork.get('cover_r2_path', '(无)')}\n"
            f"简介: {(rwork.get('description', '') or '(无)')[:120]}",
            title="Worker 远程状态",
        )
    )

    # 本地对比
    local, _ = config.find_staging(work_id)
    if local:
        local_nums = {
            c.get("chapter_num") for c in local.get("chapters", []) if c.get("chapter_num") is not None
        }
        remote_nums = {
            c.get("chapter_num") for c in rchapters if c.get("chapter_num") is not None
        }
        console.print(
            f"[info]本地暂存: {local.get('title')} | "
            f"本地章节 {len(local_nums)} | 远程章节 {len(remote_nums)}[/info]"
        )
        new_nums = sorted(local_nums - remote_nums)
        if new_nums:
            console.print(
                f"[success]待同步新章节 ({len(new_nums)} 话): "
                f"{format_chapter_range(new_nums)}[/success]"
            )
        elif local_nums == remote_nums:
            console.print("[warning]本地与远程章节一致，无新增[/warning]")
        else:
            missing = sorted(remote_nums - local_nums)
            if missing:
                console.print(
                    f"[warning]远程多出章节 ({len(missing)} 话): "
                    f"{format_chapter_range(missing)}[/warning]"
                )
    else:
        console.print("[dim]未找到对应本地暂存作品，无法对比更新[/dim]")


def _check_via_worker(work_id: str) -> None:
    """通过 Worker 实时爬取源站检查更新（--via worker 模式）"""
    try:
        wid = int(work_id)
    except ValueError:
        raise click.ClickException(f"--via worker 模式下 WORK_ID 必须是数字 ID: {work_id}")

    try:
        client = APIClient()
        with console.status("[info]Worker 正在实时爬取源站...[/info]"):
            result = client.force_check(wid)
    except (APIError, NetworkError) as e:
        raise click.ClickException(str(e))

    work = result.get("work") or {}
    has_update = result.get("has_update", False)
    new_count = result.get("new_chapter_count", 0)
    force_error = result.get("force_error")
    latest_chapter = result.get("latest_chapter") or {}

    console.print(
        Panel.fit(
            f"[bold]{work.get('title', '?')}[/bold]\n"
            f"ID: {work.get('id', wid)}    来源: {work.get('source', '?')}\n"
            f"最新章节: {work.get('latest_chapter_num', '?')}    "
            f"状态: {status_badge(str(work.get('status', '')))}\n"
            f"来源 URL: {work.get('source_url', '(无)')}",
            title="Worker 实时检查结果",
        )
    )

    if force_error:
        console.print(f"[error]爬取失败: {force_error}[/error]")
    elif has_update:
        console.print(
            f"[success]发现 {new_count} 个新章节！[/success]\n"
            f"最新章节: 第{latest_chapter.get('chapter_num', '?')}话 "
            f"{latest_chapter.get('chapter_title', '')}"
        )
    else:
        console.print("[warning]已是最新，无新章节[/warning]")
