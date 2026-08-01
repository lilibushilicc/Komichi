"""update 命令组：从源站检查并拉取最新章节

复用 sync_cmd._update_one 实现单作品/全量更新检查。
--via worker 时跳过本地爬取，改由 Worker 实时爬取源站（?force=true）。
"""
from __future__ import annotations

import click
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

from .. import config
from ..api import APIClient
from ..api.client import APIError, NetworkError
from ..groups import DefaultGroup
from ..theme import console, print_interrupted, status_badge
from ..utils import format_chapter_range
from .sync_cmd import _make_progress, _update_one


@click.group(name="update", cls=DefaultGroup, default_cmd="all")
def update_group() -> None:
    """从源站检查并拉取最新章节"""
    pass


@update_group.command("work")
@click.argument("work_id")
@click.option("--skip-upload", is_flag=True, help="跳过图片上传，仅同步元数据")
@click.option(
    "--via",
    type=click.Choice(["local", "worker"]),
    default="local",
    help="爬取模式：local=CLI本地爬取（默认），worker=Worker端实时爬取",
)
def update_work_cmd(work_id: str, skip_upload: bool, via: str) -> None:
    """检查指定作品的源站更新，拉取新章节并同步到 Worker

    WORK_ID 可以是本地暂存 slug 或数字作品 ID。
    --via worker 时 WORK_ID 必须是 Worker 上的数字 ID。
    """
    if via == "worker":
        _update_via_worker(work_id)
        return

    staging, slug = config.find_staging(work_id)
    if not staging:
        raise click.ClickException(f"未找到本地暂存作品: {work_id}")

    try:
        has_new = _update_one(staging, slug, skip_upload)
        if not has_new:
            console.print("[warning]没有需要更新的内容[/warning]")
    except (APIError, NetworkError) as e:
        raise click.ClickException(str(e))
    except KeyboardInterrupt:
        print_interrupted()
        raise click.Abort()


@update_group.command("all")
@click.option("--skip-upload", is_flag=True, help="跳过图片上传，仅同步元数据")
@click.option(
    "--via",
    type=click.Choice(["local", "worker"]),
    default="local",
    help="爬取模式：local=CLI本地爬取（默认），worker=Worker端实时爬取",
)
def update_all(skip_upload: bool, via: str) -> None:
    """检查所有作品的源站更新"""
    if via == "worker":
        _update_all_via_worker()
        return

    items = config.list_staging()
    if not items:
        console.print("[warning]没有本地暂存作品[/warning]")
        return

    total = len(items)
    console.print(f"[info]共 {total} 个作品待检查更新[/info]")
    ok, fail, no_update = 0, 0, 0
    try:
        with _make_progress() as progress:
            task = progress.add_task("检查更新", total=total)
            for i, item in enumerate(items, 1):
                slug = item.get("slug")
                progress.console.print(
                    f"\n[info][{i}/{total}] 检查更新: {item.get('title')} ({slug})[/info]"
                )
                try:
                    result = _update_one(item, slug, skip_upload)
                    if result:
                        ok += 1
                    else:
                        no_update += 1
                except (APIError, NetworkError, click.ClickException) as e:
                    console.print(f"[error]更新失败 {slug}: {e}[/error]")
                    fail += 1
                progress.advance(task)
    except KeyboardInterrupt:
        print_interrupted()
        raise click.Abort()

    console.print(
        f"\n[success]有更新 {ok}[/success]    "
        f"[warning]无更新 {no_update}[/warning]    "
        f"[error]失败 {fail}[/error]"
    )


def _update_via_worker(work_id: str) -> None:
    """通过 Worker 端实时爬取检查更新（--via worker 模式）"""
    try:
        wid = int(work_id)
    except ValueError:
        raise click.ClickException(f"--via worker 模式下 WORK_ID 必须是数字 ID: {work_id}")

    console.print(f"[info]通过 Worker 实时检查更新: 作品 ID {wid}[/info]")
    try:
        client = APIClient()
        with console.status("[info]Worker 正在爬取源站检查更新...[/info]"):
            result = client.force_check(wid)
    except (APIError, NetworkError) as e:
        raise click.ClickException(str(e))
    except KeyboardInterrupt:
        print_interrupted()
        raise click.Abort()

    work = result.get("work") or {}
    has_update = result.get("has_update", False)
    new_count = result.get("new_chapter_count", 0)
    force_error = result.get("force_error")

    console.print(
        f"\n[bold]{work.get('title', '?')}[/bold]  "
        f"ID: {work.get('id', wid)}  "
        f"来源: {work.get('source', '?')}"
    )

    if force_error:
        console.print(f"[error]爬取失败: {force_error}[/error]")
    elif has_update:
        console.print(f"[success]发现 {new_count} 个新章节[/success]")
    else:
        console.print("[warning]已是最新[/warning]")


def _update_all_via_worker() -> None:
    """通过 Worker 端实时爬取检查所有作品更新（--via worker 模式）"""
    try:
        client = APIClient()
        works = client.list_works()
    except (APIError, NetworkError) as e:
        raise click.ClickException(str(e))

    # 只检查有 source_url 的作品
    checkable = [w for w in works if w.get("source_url")]
    if not checkable:
        console.print("[warning]没有可检查的作品（远程无 source_url）[/warning]")
        return

    total = len(checkable)
    console.print(f"[info]共 {total} 个作品待通过 Worker 检查更新[/info]")
    ok, fail, no_update = 0, 0, 0

    try:
        with _make_progress() as progress:
            task = progress.add_task("Worker 检查更新", total=total)
            for i, w in enumerate(checkable, 1):
                wid = w.get("id")
                title = w.get("title", "?")
                progress.console.print(f"\n[info][{i}/{total}] {title} (ID:{wid})[/info]")
                try:
                    result = client.force_check(wid)
                    if result.get("has_update"):
                        new_count = result.get("new_chapter_count", 0)
                        progress.console.print(f"  [success]发现 {new_count} 个新章节[/success]")
                        ok += 1
                    else:
                        progress.console.print("  [dim]已是最新[/dim]")
                        no_update += 1
                except (APIError, NetworkError) as e:
                    progress.console.print(f"  [error]失败: {e}[/error]")
                    fail += 1
                progress.advance(task)
    except KeyboardInterrupt:
        print_interrupted()
        raise click.Abort()

    console.print(
        f"\n[success]有更新 {ok}[/success]    "
        f"[warning]无更新 {no_update}[/warning]    "
        f"[error]失败 {fail}[/error]"
    )
