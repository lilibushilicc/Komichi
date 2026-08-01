"""Komichi CLI 主入口

仅负责命令组注册：声明 cli 根命令并挂载各子模块的命令组。
具体业务逻辑分布在：
    staging.py            暂存数据转换工具
    display.py            导入结果展示与确认
    theme.py              统一终端主题与输出工具
    utils.py              共享工具函数
    commands/help_cmd     help 命令（help [command]）
    commands/shell_cmd    交互式 Shell 模式
    commands/config_cmd   init + config 组（show / set / get）
    commands/import_cmd   import 组（多源导入）
    commands/source_cmd   source 组
    commands/upload_cmd   upload 组
    commands/sync_cmd     sync 组（含 _sync_one / _update_one）
    commands/update_cmd   update 组
    commands/list_cmd     list 组（works / staging）+ check

命令总览：
    komichi-cli                           进入交互式 Shell（无参数时）
    komichi-cli shell                     显式进入交互式 Shell
    komichi-cli help [command]            显示帮助（支持多级命令）
    komichi-cli init                      初始化配置
    komichi-cli config show               显示当前配置
    komichi-cli config get <key>          读取单个配置项
    komichi-cli config set <key> <value>  设置配置项
    komichi-cli source list               列出所有可用源
    komichi-cli import local <path>       从本地文件夹导入漫画
    komichi-cli import url <work_url>     从 URL 导入漫画（预留接口）
    komichi-cli import from <src> <query> 从指定源导入
    komichi-cli import <url|keyword>      自动识别源
    komichi-cli upload images <work_dir>  上传指定作品的图片到 R2
    komichi-cli sync work <work_id>       同步作品数据到 Worker
    komichi-cli sync all                  同步所有本地数据
    komichi-cli update work <work_id>     检查指定作品的源站更新
    komichi-cli update all                检查所有作品的源站更新
    komichi-cli list works                列出 Worker 上的所有作品
    komichi-cli list staging              列出本地暂存作品
    komichi-cli check <work_id>           检查作品更新状态
"""
from __future__ import annotations

import sys

import click

from .commands import (
    config_cmd,
    help_cmd,
    import_cmd,
    list_cmd,
    shell_cmd,
    source_cmd,
    sync_cmd,
    update_cmd,
    upload_cmd,
)

# 业务工具函数（保留 re-export，便于外部 `from komichi_cli.main import work_to_staging` 等旧用法）
from .staging import (  # noqa: F401
    build_work_payload,
    extract_work_id,
    upload_missing_images,
    work_to_staging,
)
from .theme import console


@click.group(invoke_without_command=True)
@click.version_option(version="0.2.0", prog_name="komichi-cli")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Komichi CLI - 漫画追更管理命令行工具"""
    if ctx.invoked_subcommand is None:
        # 无子命令时：交互式终端进入 Shell，非交互显示帮助
        try:
            is_tty = sys.stdin.isatty()
        except (AttributeError, OSError):
            is_tty = False
        if is_tty:
            shell_cmd.run_shell(cli)
        else:
            console.print(ctx.get_help())


# 注册各命令组 / 独立命令
cli.add_command(help_cmd.help)
cli.add_command(shell_cmd.shell)
cli.add_command(config_cmd.init)
cli.add_command(config_cmd.config_group)
cli.add_command(import_cmd.import_group)
cli.add_command(source_cmd.source_group)
cli.add_command(upload_cmd.upload_group)
cli.add_command(sync_cmd.sync_group)
cli.add_command(update_cmd.update_group)
cli.add_command(list_cmd.list_group)
cli.add_command(list_cmd.check)


if __name__ == "__main__":
    cli()
