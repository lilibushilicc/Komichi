"""Komichi CLI 主入口

定义所有命令行命令，使用 click 实现，使用 rich 美化输出。

命令总览：
    komichi-cli init                       初始化配置
    komichi-cli config show                显示当前配置
    komichi-cli config set <key> <value>   设置配置项
    komichi-cli import local <path>        从本地文件夹导入漫画
    komichi-cli import url <work_url>      从 URL 导入漫画（预留接口）
    komichi-cli upload images <work_dir>   上传指定作品的图片到 R2
    komichi-cli sync work <work_id>        同步作品数据到 Worker
    komichi-cli sync all                   同步所有本地数据
    komichi-cli list works                 列出 Worker 上的所有作品
    komichi-cli check <work_id>            检查作品更新状态
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from . import config
from .api import APIClient
from .api.client import APIError, NetworkError
from .crawler import GodamhCrawler, LocalCrawler, UrlCrawler, WorkInfo
from .uploader import R2Uploader

console = Console()


# ============================================================
# 数据转换工具函数
# ============================================================
def work_to_staging(work: WorkInfo) -> Dict[str, Any]:
    """将 WorkInfo 转换为可序列化的本地暂存字典"""
    return {
        "slug": config.slugify(work.title),
        "work_id": None,
        "title": work.title,
        "category": work.category,
        "source_url": work.source_url,
        "cover_path": work.cover_path,
        "cover_r2_path": work.cover_r2_path,
        "status": work.status,
        "chapters": [
            {
                "chapter_num": c.chapter_num,
                "chapter_title": c.chapter_title,
            }
            for c in work.chapters
        ],
    }


def build_work_payload(
    staging: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """根据本地暂存数据构建 /api/work/update 的请求体（章节不含图片）"""
    chapters = staging.get("chapters", [])
    nums = [c.get("chapter_num", 0) for c in chapters if c.get("chapter_num") is not None]
    latest = max(nums) if nums else 0

    work = {
        "id": staging.get("work_id"),
        "title": staging.get("title", ""),
        "category": staging.get("category", ""),
        "cover_r2_path": staging.get("cover_r2_path") or "",
        "source_url": staging.get("source_url", ""),
        "latest_chapter_num": latest,
        "status": staging.get("status", "ongoing"),
    }
    chapter_list = [
        {
            "work_id": staging.get("work_id"),
            "chapter_num": c.get("chapter_num"),
            "chapter_title": c.get("chapter_title", ""),
            "images": [],
        }
        for c in chapters
    ]
    return work, chapter_list


def extract_work_id(data: Any) -> Optional[int]:
    """从响应数据中提取作品 ID"""
    if isinstance(data, dict):
        for k in ("id", "work_id", "workId"):
            v = data.get(k)
            if isinstance(v, int):
                return v
            if isinstance(v, str) and v.isdigit():
                return int(v)
        nested = data.get("work")
        if isinstance(nested, dict):
            return extract_work_id(nested)
    return None


def upload_missing_images(
    staging: Dict[str, Any],
    work_id: int,
    uploader: R2Uploader,
    only_chapter: Optional[int] = None,
) -> None:
    """上传尚未上传的封面，结果回填到 staging"""
    if staging.get("cover_path") and not staging.get("cover_r2_path"):
        try:
            r2 = uploader.upload_cover(work_id, staging["cover_path"])
            staging["cover_r2_path"] = r2
            console.print(f"  [green]封面上传成功: {r2}[/green]")
        except (APIError, NetworkError) as e:
            console.print(f"  [red]封面上传失败: {e}[/red]")


# ============================================================
# CLI 命令组
# ============================================================
@click.group()
@click.version_option(version="0.1.0", prog_name="komichi-cli")
def cli() -> None:
    """Komichi CLI - 漫画追更管理命令行工具"""
    pass


# -------------------- init --------------------
@cli.command()
def init() -> None:
    """初始化配置（设置 Worker 地址、用户名、密码）"""
    console.print(Panel.fit("Komichi CLI 初始化", style="bold cyan"))
    cfg = config.load_config()
    worker_url = Prompt.ask("Worker 地址", default=cfg.get("worker_url", "") or "")
    username = Prompt.ask("用户名", default=cfg.get("username", "") or "")
    password = Prompt.ask("密码", password=True, default=cfg.get("password", "") or "")

    config.set("worker_url", worker_url.strip().rstrip("/"))
    config.set("username", username)
    config.set("password", password)
    console.print(f"[green]配置已保存: {config.get_config_path()}[/green]")

    # 尝试登录验证配置
    try:
        client = APIClient()
        client.login()
        console.print("[green]登录成功，已获取 Token[/green]")
    except (APIError, NetworkError) as e:
        console.print(f"[yellow]登录失败（配置已保存）: {e}[/yellow]")


# -------------------- config --------------------
@cli.group(name="config")
def config_group() -> None:
    """配置管理"""
    pass


@config_group.command("show")
def config_show() -> None:
    """显示当前配置"""
    cfg = config.load_config()
    table = Table(title="Komichi 配置")
    table.add_column("键", style="cyan", no_wrap=True)
    table.add_column("值", style="white")
    for k, v in cfg.items():
        if k == "password":
            v = "***" if v else ""
        elif k == "token" and v:
            v = str(v)[:10] + "..."
        table.add_row(str(k), str(v))
    console.print(table)
    console.print(f"[dim]配置文件: {config.get_config_path()}[/dim]")


@config_group.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """设置配置项 KEY VALUE"""
    low = value.strip().lower()
    if low in ("true", "false"):
        val: Any = low == "true"
    else:
        try:
            val = int(value)
        except ValueError:
            try:
                val = float(value)
            except ValueError:
                val = value
    config.set(key, val)
    console.print(f"[green]已设置 {key} = {val}[/green]")


# -------------------- import --------------------
@cli.group(name="import")
def import_group() -> None:
    """导入漫画"""
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
    console.print(f"[cyan]扫描本地文件夹: {path}[/cyan]")
    try:
        crawler = LocalCrawler(
            source=path, title=title or "", category=category, cover=cover or ""
        )
        work = crawler.crawl()
    except (FileNotFoundError, NotADirectoryError, ValueError) as e:
        raise click.ClickException(str(e))

    console.print(
        Panel.fit(
            f"[bold]{work.title}[/bold]\n"
            f"分类: {work.category or '(未设置)'}\n"
            f"封面: {work.cover_path or '(无)'}\n"
            f"章节数: {len(work.chapters)}",
            title="导入结果",
        )
    )

    if work.chapters:
        table = Table(title="章节列表")
        table.add_column("章节号", justify="right", style="cyan")
        table.add_column("标题")
        for c in work.chapters:
            table.add_row(str(c.chapter_num), c.chapter_title)
        console.print(table)

    staging = work_to_staging(work)
    out, slug = config.save_staging(staging)
    console.print(f"[green]已保存本地暂存: {slug}[/green]")
    console.print(f"[dim]暂存文件: {out}[/dim]")
    console.print(
        "[dim]下一步: komichi-cli sync work <slug>  同步到 Worker[/dim]"
    )


@import_group.command("url")
@click.argument("work_url")
@click.option("--title", default=None, help="作品标题")
@click.option("--category", default="", help="作品分类")
def import_url(work_url: str, title: Optional[str], category: str) -> None:
    """从 URL 导入漫画（支持 .txt 图片URL列表 或 .json manifest）"""
    console.print(f"[cyan]尝试从 URL 导入: {work_url}[/cyan]")
    crawler = UrlCrawler(source=work_url, title=title or "", category=category)
    try:
        work = crawler.crawl()
    except NotImplementedError as e:
        console.print(f"[yellow]{e}[/yellow]")
        raise click.Abort()
    except NetworkError as e:
        raise click.ClickException(str(e))
    except (ValueError, json.JSONDecodeError) as e:
        raise click.ClickException(f"解析失败: {e}")

    console.print(
        f"[green]导入成功: {work.title} | 章节 {len(work.chapters)}[/green]"
    )
    staging = work_to_staging(work)
    out, slug = config.save_staging(staging)
    console.print(f"[green]已保存本地暂存: {slug}[/green]")
    console.print(f"[dim]暂存文件: {out}[/dim]")


@import_group.command("godamh")
@click.argument("keyword")
@click.option("--title", default=None, help="作品标题（默认从网页抓取）")
@click.option("--category", default="", help="作品分类")
@click.option("--cover", default=None, help="封面 URL（默认从网页抓取）")
def import_godamh(keyword: str, title: Optional[str], category: str, cover: Optional[str]) -> None:
    """从 godamh.com 导入漫画（爬取封面 URL + 章节名称，不下载图片）"""
    console.print(f"[cyan]在 godamh.com 搜索: {keyword}[/cyan]")
    crawler = GodamhCrawler(source=keyword, title=title or "", category=category, cover=cover or "")
    try:
        work = crawler.crawl()
    except ValueError as e:
        raise click.ClickException(str(e))
    except Exception as e:
        raise click.ClickException(f"爬取失败: {e}")

    console.print(
        Panel.fit(
            f"[bold]{work.title}[/bold]\n"
            f"分类: {work.category or '(未设置)'}\n"
            f"封面: {work.cover_path or '(无)'}\n"
            f"章节数: {len(work.chapters)}",
            title="导入结果",
        )
    )

    if work.chapters:
        table = Table(title="章节列表")
        table.add_column("章节号", justify="right", style="cyan")
        table.add_column("标题")
        for c in work.chapters[:10]:
            table.add_row(str(c.chapter_num), c.chapter_title)
        console.print(table)
        if len(work.chapters) > 10:
            console.print(f"[dim]...共 {len(work.chapters)} 话，仅显示前 10 话[/dim]")

    staging = work_to_staging(work)
    out, slug = config.save_staging(staging)
    console.print(f"[green]已保存本地暂存: {slug}[/green]")
    console.print(f"[dim]暂存文件: {out}[/dim]")
    console.print("[dim]下一步: komichi-cli sync work <slug>  同步到 Worker（将自动下载封面上传到 R2）[/dim]")


# -------------------- upload --------------------
@cli.group(name="upload")
def upload_group() -> None:
    """上传图片到 R2"""
    pass


@upload_group.command("images")
@click.argument("work_dir")
@click.option("--work-id", "work_id", required=True, type=int, help="作品 ID")
def upload_images(work_dir: str, work_id: int) -> None:
    """上传指定作品的封面到 R2

    WORK_DIR 可以是本地暂存 slug、暂存目录路径或数字作品 ID。
    """
    staging, slug = config.find_staging(work_dir)
    if not staging:
        raise click.ClickException(f"未找到本地暂存作品: {work_dir}")

    staging["work_id"] = work_id
    console.print(
        f"[cyan]上传作品封面: {staging.get('title')} (ID: {work_id})[/cyan]"
    )

    try:
        client = APIClient()
        uploader = R2Uploader(client)
        upload_missing_images(staging, work_id, uploader)
    except (APIError, NetworkError) as e:
        raise click.ClickException(str(e))

    config.save_staging(staging, slug=slug)
    console.print("[green]上传完成，已更新本地暂存[/green]")


# -------------------- sync --------------------
@cli.group(name="sync")
def sync_group() -> None:
    """同步数据到 Worker"""
    pass


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


@sync_group.command("all")
@click.option("--skip-upload", is_flag=True, help="跳过图片上传，仅同步元数据")
def sync_all(skip_upload: bool) -> None:
    """同步所有本地暂存作品"""
    items = config.list_staging()
    if not items:
        console.print("[yellow]没有本地暂存作品[/yellow]")
        return
    console.print(f"[cyan]共 {len(items)} 个作品待同步[/cyan]")
    ok, fail = 0, 0
    for item in items:
        slug = item.get("slug")
        try:
            console.print(
                f"\n[cyan]同步: {item.get('title')} ({slug})[/cyan]"
            )
            _sync_one(item, slug, skip_upload)
            ok += 1
        except (APIError, NetworkError, click.ClickException) as e:
            console.print(f"[red]同步失败 {slug}: {e}[/red]")
            fail += 1
    console.print(f"\n[green]成功 {ok}[/green]    [red]失败 {fail}[/red]")


def _sync_one(
    staging: Dict[str, Any], slug: Optional[str], skip_upload: bool
) -> None:
    """单个作品的完整同步流程：创建/更新记录 -> 上传图片 -> 回传图片路径"""
    client = APIClient()
    uploader = R2Uploader(client)

    # 阶段1：确保远程作品记录存在（获取 work_id）
    if not staging.get("work_id"):
        console.print("[cyan]首次同步，创建作品记录...[/cyan]")
        work, chapters = build_work_payload(staging)
        data = client.update_work(work, chapters)
        new_id = extract_work_id(data)
        if not new_id:
            raise APIError(-1, f"创建作品未返回 ID，响应: {data}")
        staging["work_id"] = new_id
        config.save_staging(staging, slug=slug)
        console.print(f"[green]作品已创建，远程 ID: {new_id}[/green]")
    else:
        console.print(
            f"[cyan]更新作品记录 (ID: {staging['work_id']})...[/cyan]"
        )

    work_id = staging["work_id"]

    # 阶段2：上传图片（如未跳过）
    if not skip_upload:
        upload_missing_images(staging, work_id, uploader)
        config.save_staging(staging, slug=slug)

    # 阶段3：完整同步元数据 + 图片路径
    work, chapters = build_work_payload(staging)
    client.update_work(work, chapters)
    console.print(f"[green]同步完成: {work['title']} (ID: {work_id})[/green]")


# -------------------- list --------------------
@cli.group(name="list")
def list_group() -> None:
    """查询作品"""
    pass


@list_group.command("works")
def list_works() -> None:
    """列出 Worker 上的所有作品"""
    try:
        client = APIClient()
        works = client.list_works()
    except (APIError, NetworkError) as e:
        raise click.ClickException(str(e))

    if not works:
        console.print("[yellow]Worker 上暂无作品[/yellow]")
        return

    table = Table(title=f"作品列表 (共 {len(works)} 个)")
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("标题")
    table.add_column("分类")
    table.add_column("最新章节", justify="right")
    table.add_column("状态")
    table.add_column("来源")
    for w in works:
        table.add_row(
            str(w.get("id", "")),
            str(w.get("title", "")),
            str(w.get("category", "")),
            str(w.get("latest_chapter_num", "")),
            str(w.get("status", "")),
            str(w.get("source_url", "")),
        )
    console.print(table)


# -------------------- check --------------------
@cli.command()
@click.argument("work_id")
def check(work_id: str) -> None:
    """检查作品更新状态（对比本地暂存与 Worker 远程数据）"""
    try:
        client = APIClient()
        remote = client.get_work(work_id)
    except (APIError, NetworkError) as e:
        raise click.ClickException(str(e))

    if not remote:
        console.print(f"[yellow]Worker 上未找到作品: {work_id}[/yellow]")
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
            f"最新章节: {rwork.get('latest_chapter_num', '?')}    状态: {rwork.get('status', '')}\n"
            f"封面: {rwork.get('cover_r2_path', '(无)')}",
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
            f"[cyan]本地暂存: {local.get('title')} | "
            f"本地章节 {len(local_nums)} | 远程章节 {len(remote_nums)}[/cyan]"
        )
        new_nums = sorted(local_nums - remote_nums)
        if new_nums:
            console.print(f"[green]待同步新章节: {new_nums}[/green]")
        elif local_nums == remote_nums:
            console.print("[yellow]本地与远程章节一致，无新增[/yellow]")
        else:
            missing = sorted(remote_nums - local_nums)
            if missing:
                console.print(f"[yellow]远程多出章节: {missing}[/yellow]")
    else:
        console.print("[dim]未找到对应本地暂存作品，无法对比更新[/dim]")


if __name__ == "__main__":
    cli()
