"""统一终端主题与输出工具

全模块共享同一个 Console 实例，避免多处创建导致风格不一致。
提供统一的颜色常量、输出辅助函数和 CLI 品牌标识。
"""
from __future__ import annotations

from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.theme import Theme

# ============================================================
# 统一 Console 实例（全模块共用）
# ============================================================
_THEME = Theme(
    {
        "info": "cyan",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "dim": "dim",
        "title": "bold cyan",
        "highlight": "bold magenta",
    }
)

console = Console(theme=_THEME)

# ============================================================
# 颜色 / 样式常量（供 Rich 标记字符串使用）
# ============================================================
SUCCESS = "green"
WARNING = "yellow"
ERROR = "red"
INFO = "cyan"
DIM = "dim"
BOLD = "bold"

# 状态徽章映射
STATUS_BADGE = {
    "ongoing": "[bold cyan]连载中[/bold cyan]",
    "completed": "[bold green]已完结[/bold green]",
}


def status_badge(status: str) -> str:
    """返回状态对应的彩色徽章文本"""
    return STATUS_BADGE.get(str(status).lower(), str(status))


# ============================================================
# 输出辅助函数
# ============================================================
def print_success(msg: str) -> None:
    """输出成功信息"""
    console.print(f"[success]{msg}[/success]")


def print_error(msg: str) -> None:
    """输出错误信息"""
    console.print(f"[error]{msg}[/error]")


def print_warning(msg: str) -> None:
    """输出警告信息"""
    console.print(f"[warning]{msg}[/warning]")


def print_info(msg: str) -> None:
    """输出提示信息"""
    console.print(f"[info]{msg}[/info]")


def print_dim(msg: str) -> None:
    """输出次要信息"""
    console.print(f"[dim]{msg}[/dim]")


def print_panel(msg: str, title: Optional[str] = None, style: str = "") -> None:
    """输出面板信息"""
    console.print(Panel.fit(msg, title=title, style=style))


def print_interrupted() -> None:
    """统一的 Ctrl+C 友好提示"""
    console.print("\n[warning]已中断[/warning]")


def print_banner() -> None:
    """输出 CLI 品牌 Logo"""
    console.print(
        "[title]Komichi CLI[/title] [dim]v0.2.0 - 漫画追更管理命令行工具[/dim]"
    )
