"""sync 命令组：同步本地暂存数据到 Worker

包含单个作品同步流程 _sync_one 与源站更新检查流程 _update_one。
_update_one 被 update_cmd 复用。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

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
from ..crawler import (
    CrawlError,
    SourceNotFound,
    crawl_with_fallback,
    get_crawler,
)
from ..groups import DefaultGroup
from ..staging import build_work_payload, extract_work_id, upload_missing_images
from ..theme import console, print_interrupted
from ..uploader import R2Uploader
from ..utils import format_chapter_range


# ============================================================
# 向后兼容别名（其他模块通过 sync_cmd._interrupted / _format_chapter_range 引用）
# ============================================================
_interrupted = print_interrupted
_format_chapter_range = format_chapter_range


@click.group(name="sync", cls=DefaultGroup, default_cmd="all")
def sync_group() -> None:
    """同步数据到 Worker"""
    pass


def _make_progress() -> Progress:
    """构建统一风格的进度条"""
    return Progress(
        SpinnerColumn(),
        TextColumn("[info]{task.description}[/info]"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
        transient=True,
    )


@sync_group.command("work")
@click.argument("work_id")
@click.option(
    "--skip-upload", is_flag=True, help="跳过图片上传，仅同步元数据"
)
def sync_work(work_id: str, skip_upload: bool) -> None:
    """同步作品数据到 Worker（上传 works + chapters 数据）

    WORK_ID 可以是本地暂存 slug 或数字作品 ID。
    首次同步会自动在 Worker 创建作品并获取远程 ID，随后上传图片并回传图片路径。
    """
    staging, slug = config.find_staging(work_id)
    if not staging:
        raise click.ClickException(f"未找到本地暂存作品: {work_id}（请先 import）")

    try:
        _sync_one(staging, slug, skip_upload)
    except (APIError, NetworkError) as e:
        raise click.ClickException(str(e))
    except KeyboardInterrupt:
        print_interrupted()
        raise click.Abort()


@sync_group.command("all")
@click.option("--skip-upload", is_flag=True, help="跳过图片上传，仅同步元数据")
def sync_all(skip_upload: bool) -> None:
    """同步所有本地暂存作品"""
    items = config.list_staging()
    if not items:
        console.print("[warning]没有本地暂存作品[/warning]")
        return
    total = len(items)
    console.print(f"[info]共 {total} 个作品待同步[/info]")
    ok, fail = 0, 0
    try:
        with _make_progress() as progress:
            task = progress.add_task("同步", total=total)
            for i, item in enumerate(items, 1):
                slug = item.get("slug")
                progress.console.print(
                    f"\n[info][{i}/{total}] 同步: {item.get('title')} ({slug})[/info]"
                )
                try:
                    _sync_one(item, slug, skip_upload)
                    ok += 1
                except (APIError, NetworkError, click.ClickException) as e:
                    console.print(f"[error]同步失败 {slug}: {e}[/error]")
                    fail += 1
                progress.advance(task)
    except KeyboardInterrupt:
        print_interrupted()
        raise click.Abort()
    console.print(
        f"\n[success]成功 {ok}[/success]    [error]失败 {fail}[/error]"
    )


def _sync_one(
    staging: Dict[str, Any], slug: Optional[str], skip_upload: bool
) -> None:
    """单个作品的完整同步流程：创建/更新记录 -> 上传图片 -> 回传图片路径"""
    client = APIClient()
    uploader = R2Uploader(client)

    # 阶段1：确保远程作品记录存在（获取 work_id）
    if not staging.get("work_id"):
        with console.status("[info]创建作品记录...[/info]"):
            work, chapters = build_work_payload(staging)
            data = client.update_work(work, chapters)
            new_id = extract_work_id(data)
            if not new_id:
                raise APIError(-1, f"创建作品未返回 ID，响应: {data}")
            staging["work_id"] = new_id
            config.save_staging(staging, slug=slug)
        console.print(f"[success]作品已创建，远程 ID: {new_id}[/success]")
    else:
        console.print(
            f"[info]已存在作品记录 (ID: {staging['work_id']})，跳过创建[/info]"
        )

    work_id = staging["work_id"]

    # 阶段2：上传图片（如未跳过）
    if not skip_upload:
        upload_missing_images(staging, work_id, uploader)
        config.save_staging(staging, slug=slug)

    # 阶段3：完整同步元数据 + 图片路径
    with console.status("[info]回传元数据与图片路径...[/info]"):
        work, chapters = build_work_payload(staging)
        client.update_work(work, chapters)
    console.print(f"[success]同步完成: {work['title']} (ID: {work_id})[/success]")


def _update_one(staging: Dict[str, Any], slug: Optional[str], skip_upload: bool) -> bool:
    """检查单个作品的源站更新，拉取新章节并同步到 Worker

    返回 True 表示有新章节并已同步，False 表示无新章节或失败。
    """
    source = staging.get("source", "")
    source_url = staging.get("source_url", "")

    if not source_url:
        console.print("[warning]该作品没有 source_url，无法检查更新[/warning]")
        return False

    # 重新爬取源站最新数据
    console.print(f"[dim]从源站 {source or source_url} 重新爬取...[/dim]")
    try:
        with console.status("[info]正在抓取源站最新数据...[/info]"):
            if source and source not in ("local", "url"):
                crawler = get_crawler(source, source_url, title=staging.get("title", ""))
                fresh_work = crawler.crawl()
            else:
                # 对于 local/url 源，尝试按 URL 自动识别
                fresh_work, detected_source = crawl_with_fallback(
                    source_url, title=staging.get("title", "")
                )
                if detected_source:
                    staging["source"] = detected_source
    except (CrawlError, SourceNotFound) as e:
        console.print(f"[error]源站爬取失败: {e}[/error]")
        return False

    # 对比章节，找出新增
    existing_nums = {
        c.get("chapter_num")
        for c in staging.get("chapters", [])
        if c.get("chapter_num") is not None
    }
    fresh_nums = {c.chapter_num for c in fresh_work.chapters}
    new_nums = sorted(fresh_nums - existing_nums)

    if not new_nums:
        console.print("[warning]源站无新章节[/warning]")
        return False

    console.print(
        f"[success]发现 {len(new_nums)} 个新章节: "
        f"{format_chapter_range(new_nums)}[/success]"
    )

    # 合并新章节到 staging
    new_chapters = [
        {"chapter_num": c.chapter_num, "chapter_title": c.chapter_title}
        for c in fresh_work.chapters
        if c.chapter_num in new_nums
    ]
    staging["chapters"].extend(new_chapters)
    staging["chapters"].sort(key=lambda c: c.get("chapter_num", 0))

    # 更新作品元数据（如有变化）
    if fresh_work.description and not staging.get("description"):
        staging["description"] = fresh_work.description
    if fresh_work.cover_path and not staging.get("cover_path"):
        staging["cover_path"] = fresh_work.cover_path

    config.save_staging(staging, slug=slug)

    # 同步到 Worker
    _sync_one(staging, slug, skip_upload)
    return True
