"""source 命令组：列出可用爬虫源"""
from __future__ import annotations

import click
from rich.table import Table

from .. import config
from ..crawler import describe_sources
from ..groups import DefaultGroup
from ..theme import console


@click.group(name="source", cls=DefaultGroup, default_cmd="list")
def source_group() -> None:
    """源管理（多源爬虫）"""
    pass


@source_group.command("list")
def source_list() -> None:
    """列出所有可用爬虫源及其域名"""
    items = describe_sources()
    if not items:
        console.print("[warning]暂无可用源[/warning]")
        return
    table = Table(title=f"可用源 (共 {len(items)} 个)")
    table.add_column("#", justify="right", style="dim")
    table.add_column("源名", style="cyan", no_wrap=True)
    table.add_column("展示名")
    table.add_column("域名")
    table.add_column("优先级", justify="center")
    prio = config.get("source_priority", [])
    if isinstance(prio, str):
        prio = [p.strip() for p in prio.split(",") if p.strip()]
    prio_list = list(prio) if isinstance(prio, (list, tuple)) else []
    for idx, (name, display, domains) in enumerate(items, 1):
        prio_mark = ""
        if name in prio_list:
            prio_mark = f"[bold]#{prio_list.index(name) + 1}[/bold]"
        table.add_row(
            str(idx),
            name,
            display,
            ", ".join(domains) or "-",
            prio_mark,
        )
    console.print(table)
    if prio_list:
        console.print(
            f"[dim]当前优先级: {', '.join(prio_list)}"
            f"（调整: komichi-cli config set source_priority {','.join(prio_list)}）[/dim]"
        )
