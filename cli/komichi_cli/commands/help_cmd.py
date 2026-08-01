"""help 命令：支持 komichi-cli help [command] [subcommand]

与 --help 等效，但可作为独立命令使用，更符合直觉。
"""
from __future__ import annotations

import click

from ..theme import console


@click.command()
@click.argument("args", nargs=-1)
@click.pass_context
def help(ctx: click.Context, args: tuple[str, ...]) -> None:
    """显示帮助信息

    \b
    用法:
        komichi-cli help              显示总帮助
        komichi-cli help config       显示 config 命令帮助
        komichi-cli help config set   显示 config set 子命令帮助
        komichi-cli help import       显示 import 命令帮助
    """
    root = ctx.find_root()
    root_cmd = root.command

    if not args:
        click.echo(root_cmd.get_help(root))
        return

    cmd: click.Command = root_cmd
    for arg in args:
        if isinstance(cmd, click.Group):
            sub = cmd.get_command(root, arg)
            if sub is None:
                console.print(f"[error]未知命令: {arg}[/error]")
                console.print(
                    f"[dim]可用命令: {', '.join(cmd.list_commands(root))}[/dim]"
                )
                return
            cmd = sub
        else:
            console.print(f"[error]'{cmd.name}' 没有子命令 '{arg}'[/error]")
            return

    sub_ctx = click.Context(cmd, info_name=cmd.name, parent=root)
    click.echo(cmd.get_help(sub_ctx))
