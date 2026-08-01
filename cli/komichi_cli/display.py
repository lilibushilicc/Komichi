"""导入结果展示与确认逻辑

打印导入结果面板、章节表格，保存本地暂存，
以及构造关键词导入时的交互式确认回调。供 import_cmd 复用。
"""
from __future__ import annotations

import sys
from typing import Any, Optional

import click
from rich.panel import Panel
from rich.table import Table

from . import config
from .crawler import WorkInfo
from .staging import work_to_staging
from .theme import console, status_badge

# ============================================================
# 统一渲染函数（供各命令模块复用，避免重复代码）
# ============================================================


def render_work_panel(work: WorkInfo, source: str = "", title: str = "导入结果") -> None:
    """渲染作品信息面板（统一风格）"""
    desc = work.description.strip()
    desc_block = (
        f"简介: {desc[:200]}{'...' if len(desc) > 200 else ''}\n" if desc else ""
    )
    console.print(
        Panel.fit(
            f"[bold]{work.title}[/bold]\n"
            f"来源: {source or '(未设置)'}\n"
            f"分类: {work.category or '(未设置)'}    "
            f"状态: {status_badge(work.status)}\n"
            f"{desc_block}"
            f"封面: {work.cover_path or '(无)'}\n"
            f"章节数: {len(work.chapters)}\n"
            f"链接: {work.source_url or '(无)'}",
            title=title,
        )
    )


def render_chapter_table(chapters: list, max_rows: int = 10) -> None:
    """渲染章节列表表格（统一风格）

    chapters 可为 WorkInfo.chapters (ChapterInfo 列表) 或 staging dict 列表。
    """
    if not chapters:
        return
    table = Table(title="章节列表", show_lines=False)
    table.add_column("章节号", justify="right", style="cyan")
    table.add_column("标题")
    for c in chapters[:max_rows]:
        num = getattr(c, "chapter_num", None) or c.get("chapter_num", "")
        title_val = getattr(c, "chapter_title", None) or c.get("chapter_title", "")
        table.add_row(str(num), str(title_val))
    console.print(table)
    if len(chapters) > max_rows:
        console.print(f"[dim]...共 {len(chapters)} 话，仅显示前 {max_rows} 话[/dim]")


# ============================================================
# 导入结果展示与保存
# ============================================================


def _show_import_result(work: WorkInfo, source: str = "") -> None:
    """打印导入结果面板 + 章节表格"""
    render_work_panel(work, source=source, title="导入结果")
    render_chapter_table(work.chapters)


def _save_import_result(work: WorkInfo, source: str = "") -> None:
    """保存导入结果到本地暂存，返回 (out_path, slug)"""
    staging = work_to_staging(work, source=source)
    out, slug = config.save_staging(staging)
    console.print(f"[success]已保存本地暂存: {slug}[/success]")
    console.print(f"[dim]暂存文件: {out}[/dim]")
    console.print(
        "[dim]下一步: komichi-cli sync work <slug>  同步到 Worker（将自动下载封面上传到 R2）[/dim]"
    )


def _build_confirm(keyword: str, assume_yes: bool) -> Optional[Any]:
    """构造抓取结果确认回调。

    仅对关键词导入、且终端为交互式（stdin 为 TTY）且未加 --yes 时启用。
    """
    if assume_yes:
        return None
    try:
        interactive = sys.stdin.isatty()
    except (AttributeError, OSError):
        interactive = False
    if not interactive:
        return None

    def confirm(name: str, work: WorkInfo) -> bool:
        render_work_panel(work, source=name, title=f"关键词「{keyword}」匹配结果")
        return click.confirm("就是这个作品？", default=True)

    return confirm
