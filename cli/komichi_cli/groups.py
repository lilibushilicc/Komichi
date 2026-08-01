"""自定义 Click Group：支持默认子命令自动补全

当用户输入命令组而不带子命令时，自动执行默认子命令，
而不是显示帮助并以非零退出码退出。

用法:
    @click.group(cls=DefaultGroup, default_cmd="list")
    def source_group():
        ...

效果:
    komichi-cli source    →  自动执行 source list
    komichi-cli config    →  自动执行 config show
"""
from __future__ import annotations

import click


class DefaultGroup(click.Group):
    """命令组：无子命令时自动执行默认子命令

    参数:
        default_cmd: 默认子命令名。为 None 时无子命令则显示帮助（退出码 0）。
    """

    def __init__(self, *args, default_cmd: str | None = None, **kwargs):
        kwargs.setdefault("invoke_without_command", True)
        super().__init__(*args, **kwargs)
        self.default_cmd_name = default_cmd

    def invoke(self, ctx: click.Context) -> None:
        """无子命令时自动执行默认子命令，无默认则显示帮助

        注意：Click 8.3+ 在 invoke_without_command=True 时，
        ctx.invoked_subcommand 在 invoke() 阶段尚未设置（仍为 None），
        子命令名实际存放在 ctx.protected_args 中。
        因此通过检查 protected_args/args 判断是否有子命令。
        """
        # 检查是否有子命令或剩余参数
        has_args = bool(getattr(ctx, "protected_args", None) or ctx.args)
        if not has_args:
            # 无子命令 → 执行默认子命令
            if self.default_cmd_name:
                cmd = self.get_command(ctx, self.default_cmd_name)
                if cmd is not None:
                    sub_ctx = cmd.make_context(
                        self.default_cmd_name, [], parent=ctx,
                    )
                    with sub_ctx:
                        cmd.invoke(sub_ctx)
                    return
            # 无默认子命令 → 显示帮助（退出码 0）
            click.echo(ctx.get_help())
        else:
            super().invoke(ctx)
