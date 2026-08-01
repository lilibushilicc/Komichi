"""交互式 Shell 模式

在 Shell 中可以直接输入子命令（无需 komichi-cli 前缀），
支持快捷别名、命令组自动默认子命令和内嵌 help，大幅减少输入量。

用法:
    komichi-cli              # 无参数时自动进入 Shell
    komichi-cli shell        # 显式进入 Shell
"""
from __future__ import annotations

import sys
from difflib import get_close_matches

import click
from rich.panel import Panel

from ..theme import console

# ============================================================
# Shell 快捷别名：首词 -> 展开后的命令词列表（None 表示退出）
# ============================================================
_SHELL_ALIASES: dict[str, list[str] | None] = {
    "ls": ["list", "works"],
    "staging": ["list", "staging"],
    "show": ["config", "show"],
    "set": ["config", "set"],
    "get": ["config", "get"],
    "sources": ["source", "list"],
    "init": ["init"],
    "h": ["help"],
    "?": ["help"],
    "q": None,
    "exit": None,
    "quit": None,
}

# ============================================================
# 命令组默认子命令：输入组名时自动补上默认子命令
#
# 例如输入 "source" 自动变为 "source list"，
# 输入 "list" 自动变为 "list works"。
# 仅当第二个词不是该组的合法子命令时才补全。
# ============================================================
_GROUP_DEFAULTS: dict[str, str] = {
    "source": "list",
    "list": "works",
    "config": "show",
    "upload": "images",
    "sync": "all",
    "update": "all",
}


def _print_quick_start() -> None:
    """打印 Shell 快速入门面板"""
    console.print(
        Panel.fit(
            "[bold cyan]show[/bold cyan]              查看配置\n"
            "[bold cyan]set[/bold cyan] <k> <v>       设置配置项\n"
            "[bold cyan]get[/bold cyan] <k>           读取配置项\n"
            "[bold cyan]ls[/bold cyan]                列出作品\n"
            "[bold cyan]staging[/bold cyan]           列出本地暂存\n"
            "[bold cyan]sources[/bold cyan]           列出可用源\n"
            "[bold cyan]import[/bold cyan] <url>      导入漫画\n"
            "[bold cyan]sync work[/bold cyan] <id>    同步作品\n"
            "[bold cyan]update work[/bold cyan] <id>  检查更新\n"
            "[bold cyan]check[/bold cyan] <id>        检查状态\n"
            "[bold cyan]help[/bold cyan] [cmd]        查看帮助\n"
            "[bold cyan]exit[/bold cyan]              退出",
            title="快捷命令",
            border_style="cyan",
        )
    )


def _show_command_help(
    root_cmd: click.Group, ctx: click.Context, path: list[str]
) -> None:
    """递归查找命令并显示其帮助"""
    cmd: click.Command = root_cmd
    for part in path:
        if isinstance(cmd, click.Group):
            sub = cmd.get_command(ctx, part)
            if sub is None:
                console.print(f"[error]未知命令: {part}[/error]")
                return
            cmd = sub
        else:
            console.print(f"[error]'{cmd.name}' 没有子命令 '{part}'[/error]")
            return
    sub_ctx = click.Context(cmd, info_name=cmd.name, parent=ctx)
    click.echo(cmd.get_help(sub_ctx))


def _resolve_defaults(
    root_cmd: click.Group, ctx: click.Context, parts: list[str]
) -> list[str]:
    """自动补全命令组的默认子命令

    如果首词是带有默认子命令的 Group，且第二个词不是该 Group 的合法子命令，
    则在首词后插入默认子命令。

    例如: ["source"]            -> ["source", "list"]
          ["source", "list"]    -> ["source", "list"]  (不变)
          ["list", "--search"]  -> ["list", "works", "--search"]
          ["list", "staging"]   -> ["list", "staging"] (不变)
    """
    if not parts:
        return parts
    cmd_name = parts[0].lower()
    if cmd_name not in _GROUP_DEFAULTS:
        return parts

    group_cmd = root_cmd.get_command(ctx, cmd_name)
    if not isinstance(group_cmd, click.Group):
        return parts

    default_sub = _GROUP_DEFAULTS[cmd_name]

    # 没有后续参数 -> 补上默认子命令
    if len(parts) == 1:
        return [cmd_name, default_sub]

    # 第二个词是合法子命令 -> 不补
    second = parts[1]
    if group_cmd.get_command(ctx, second) is not None:
        return parts

    # 第二个词不是子命令（可能是选项或参数）-> 补上默认子命令
    return [cmd_name, default_sub] + parts[1:]


def _try_correct(
    root_cmd: click.Group, ctx: click.Context, cmd_name: str
) -> str | None:
    """模糊匹配纠正拼写错误，返回最接近的已知命令名

    匹配范围：根命令 + Shell 别名。无匹配时返回 None。
    """
    # 收集所有已知命令名
    known = set(root_cmd.list_commands(ctx))
    known.update(_SHELL_ALIASES.keys())
    known.update(_GROUP_DEFAULTS.keys())
    known.discard(cmd_name)  # 排除自身

    matches = get_close_matches(cmd_name, known, n=1, cutoff=0.6)
    return matches[0] if matches else None


def run_shell(root_cmd: click.Group) -> None:
    """启动交互式 Shell 主循环

    root_cmd 为 CLI 根 Group，用于分发命令和显示帮助。
    """
    console.print("[title]Komichi CLI Shell[/title] [dim]v0.2.0[/dim]")
    console.print(
        "[dim]直接输入命令即可执行，无需 komichi-cli 前缀。"
        "输入 help 查看帮助，输入 exit 退出。[/dim]"
    )
    _print_quick_start()
    console.print()

    root_ctx = click.Context(root_cmd, info_name="komichi-cli")

    while True:
        try:
            line = input("komichi> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]再见[/dim]")
            break

        if not line:
            continue

        parts = line.split()
        cmd_name = parts[0].lower()
        rest = parts[1:]

        # 退出
        if cmd_name in ("exit", "quit", "q"):
            console.print("[dim]再见[/dim]")
            break

        # help
        if cmd_name in ("help", "h", "?"):
            if not rest:
                click.echo(root_cmd.get_help(root_ctx))
            else:
                _show_command_help(root_cmd, root_ctx, rest)
            console.print()
            continue

        # 别名展开
        if cmd_name in _SHELL_ALIASES:
            mapped = _SHELL_ALIASES[cmd_name]
            if mapped is None:
                console.print("[dim]再见[/dim]")
                break
            parts = mapped + rest

        # 拼写纠正：首词既不是已知命令也不是别名时，尝试模糊匹配
        elif root_cmd.get_command(root_ctx, cmd_name) is None:
            corrected = _try_correct(root_cmd, root_ctx, cmd_name)
            if corrected:
                console.print(
                    f"[warning]未找到 '{cmd_name}'，"
                    f"已自动纠正为 '{corrected}'[/warning]"
                )
                parts = [corrected] + rest
            else:
                console.print(
                    f"[error]未知命令: {cmd_name}[/error]"
                )
                known_cmds = ", ".join(sorted(root_cmd.list_commands(root_ctx)))
                console.print(f"[dim]可用命令: {known_cmds}[/dim]")
                console.print()
                continue

        # 命令组自动默认子命令
        parts = _resolve_defaults(root_cmd, root_ctx, parts)

        # 分发到 CLI
        try:
            root_cmd.main(
                parts,
                standalone_mode=False,
                prog_name="komichi-cli",
            )
        except click.ClickException as e:
            e.show()
        except click.Abort:
            console.print("[warning]已取消[/warning]")
        except SystemExit:
            pass
        except Exception as e:
            console.print(f"[error]{type(e).__name__}: {e}[/error]")
        console.print()


@click.command()
@click.pass_context
def shell(ctx: click.Context) -> None:
    """进入交互式 Shell 模式（快捷命令输入）"""
    root = ctx.find_root()
    run_shell(root.command)
