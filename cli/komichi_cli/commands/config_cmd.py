"""config 命令组：init + config show/set/get"""
from __future__ import annotations

from typing import Any, Optional, Tuple
from urllib.parse import urlparse

import click
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from .. import config
from ..api import APIClient
from ..api.client import APIError, NetworkError
from ..crawler import list_sources
from ..groups import DefaultGroup
from ..theme import console


# ============================================================
# 配置项校验
# ============================================================
def _is_secret_key(key: str) -> bool:
    """判断是否为敏感配置项（密码/token 类，回显需隐藏）"""
    k = key.lower()
    return "password" in k or "token" in k or "secret" in k


def _validate_config_value(key: str, value: str) -> Tuple[Any, Optional[str]]:
    """校验已知配置项的值，返回 (转换后的值, 错误信息)

    错误信息非空表示校验失败；为 None 表示通过（含未知 key 的宽容通过）。
    """
    k = key.lower()
    if k == "worker_url":
        v = value.strip()
        if not (v.startswith("http://") or v.startswith("https://")):
            return value, "worker_url 必须以 http:// 或 https:// 开头"
        # 进一步用 urlparse 校验主机名
        parsed = urlparse(v)
        if not parsed.netloc:
            return value, f"worker_url 缺少主机名: {v}"
        return v.rstrip("/"), None

    if k in ("upload_concurrency", "max_retries", "request_timeout"):
        try:
            num = int(value)
        except ValueError:
            return value, f"{key} 必须是正整数（收到: {value!r}）"
        if num <= 0:
            return value, f"{key} 必须大于 0（收到: {num}）"
        return num, None

    if k == "source_priority":
        parts = [s.strip() for s in value.split(",") if s.strip()]
        if not parts:
            return value, "source_priority 至少需要一个源名（逗号分隔）"
        known = set(list_sources())
        unknown = [p for p in parts if p not in known]
        if unknown:
            return value, (
                f"source_priority 含未知源: {', '.join(unknown)}"
                f"（可用源: {', '.join(sorted(known))}）"
            )
        return parts, None

    if k in ("token", "password", "username", "staging_dir", "upload_path"):
        return value, None

    if k in ("status",):
        v = value.strip().lower()
        if v not in ("ongoing", "completed"):
            return value, f"status 必须是 ongoing 或 completed（收到: {value!r}）"
        return v, None

    # 未知 key：宽容通过，由调用方决定是否警告
    return value, None


# ============================================================
# init 命令
# ============================================================
def _classify_login_error(e: Exception) -> Tuple[str, str]:
    """将登录异常分类为 (友好提示, 错误类型标签)

    类型：network / worker_url / auth / other
    """
    if isinstance(e, NetworkError):
        msg = str(e)
        # 响应解析失败 + HTTP 4xx/5xx → Worker 地址错
        if "解析失败" in msg and ("HTTP 4" in msg or "HTTP 5" in msg):
            return (
                "Worker 地址可能错误，服务器返回了非 JSON 响应。"
                "请检查 worker_url 是否指向正确的 Komichi Worker。",
                "worker_url",
            )
        # 连接超时 / 连接拒绝 / DNS 失败
        return (
            "无法连接到 Worker（网络不通或地址不可达）。"
            "请检查网络、VPN 或 worker_url 是否正确。",
            "network",
        )
    if isinstance(e, APIError):
        if e.code == 401:
            return "用户名或密码错误。", "auth"
        if e.code == 403:
            return "账号无权限登录。", "auth"
        if e.code == 404 or "not found" in (e.msg or "").lower():
            return "Worker 端点不存在，worker_url 可能错误。", "worker_url"
        return f"Worker 返回业务错误: {e.msg} (code={e.code})", "other"
    return f"未知错误: {type(e).__name__}: {e}", "other"


def _ask_init_credentials(cfg: dict) -> Tuple[str, str, str]:
    """交互式询问 worker_url/username/password，含 URL 格式校验"""
    while True:
        worker_url = Prompt.ask(
            "Worker 地址",
            default=cfg.get("worker_url", "") or "",
        ).strip()
        if worker_url and not (
            worker_url.startswith("http://") or worker_url.startswith("https://")
        ):
            console.print(
                "[warning]worker_url 必须以 http:// 或 https:// 开头，请重新输入[/warning]"
            )
            continue
        break
    username = Prompt.ask("用户名", default=cfg.get("username", "") or "")
    password = Prompt.ask(
        "密码", password=True, default=cfg.get("password", "") or ""
    )
    return worker_url, username, password


@click.command()
def init() -> None:
    """初始化配置（设置 Worker 地址、用户名、密码）"""
    console.print(Panel.fit("Komichi CLI 初始化", style="bold cyan"))
    cfg = config.load_config()

    while True:
        worker_url, username, password = _ask_init_credentials(cfg)

        config.set("worker_url", worker_url.rstrip("/"))
        config.set("username", username)
        config.set("password", password)
        console.print(f"[success]配置已保存: {config.get_config_path()}[/success]")

        # 尝试登录验证配置
        try:
            client = APIClient()
            client.login()
            console.print("[success]登录成功，已获取 Token[/success]")
            return
        except (APIError, NetworkError) as e:
            hint, kind = _classify_login_error(e)
            console.print(f"[warning]登录失败（配置已保存）[/warning]")
            console.print(f"[warning]原因: {hint}[/warning]")
            if kind == "auth":
                console.print("[dim]提示: 可重新输入用户名/密码[/dim]")
            elif kind == "worker_url":
                console.print("[dim]提示: 检查 worker_url 是否拼写正确、是否部署了 Komichi Worker[/dim]")
            elif kind == "network":
                console.print("[dim]提示: 检查网络/VPN 是否通畅，Worker 是否可达[/dim]")
            if not click.confirm("是否重新输入并重试？", default=True):
                console.print("[dim]已退出，可稍后重新执行 `komichi-cli init`[/dim]")
                return
            # 重新加载已保存的配置作为默认值
            cfg = config.load_config()


# ============================================================
# config 命令组
# ============================================================
@click.group(name="config", cls=DefaultGroup, default_cmd="show")
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
        if _is_secret_key(k):
            display_v = "***" if v else ""
        else:
            display_v = str(v)
        table.add_row(str(k), display_v)
    console.print(table)
    console.print(f"[dim]配置文件: {config.get_config_path()}[/dim]")


@config_group.command("get")
@click.argument("key")
def config_get(key: str) -> None:
    """读取单个配置项的值"""
    cfg = config.load_config()
    if key not in cfg:
        console.print(f"[warning]配置项 {key!r} 不存在[/warning]")
        return
    v = cfg[key]
    if _is_secret_key(key):
        display_v = "***" if v else "(空)"
    else:
        display_v = str(v)
    console.print(f"[cyan]{key}[/cyan] = {display_v}")


@config_group.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """设置配置项 KEY VALUE"""
    known_keys = {
        "worker_url", "username", "password", "token",
        "upload_path", "upload_concurrency", "request_timeout",
        "max_retries", "staging_dir", "source_priority", "status",
    }
    if key.lower() not in known_keys:
        if not click.confirm(
            f"未知配置项 {key!r}，是否继续设置？",
            default=False,
        ):
            console.print("[warning]已取消[/warning]")
            return

    val, err = _validate_config_value(key, value)
    if err:
        raise click.ClickException(err)

    config.set(key, val)
    if _is_secret_key(key):
        console.print(f"[success]已设置 {key} (已隐藏)[/success]")
    else:
        console.print(f"[success]已设置 {key} = {val}[/success]")


# ============================================================
# config set-vps-url / get-vps-url — 远程管理 Worker 的 VPS_URL
# ============================================================
@config_group.command("set-vps-url")
@click.argument("vps_url")
def config_set_vps_url(vps_url: str) -> None:
    """更新 Worker 的 VPS_URL（写入 D1，无需重新部署）

    当 Cloudflare Tunnel 地址变更时，用此命令一键更新：

    \b
    komichi-cli config set-vps-url https://xxx.trycloudflare.com
    """
    url = vps_url.strip().rstrip("/")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise click.ClickException("VPS_URL 必须以 http:// 或 https:// 开头")

    try:
        client = APIClient()
        result = client.set_vps_url(url)
        console.print(f"[success]VPS_URL 已更新: {result.get('vps_url', url)}[/success]")
        console.print("[dim]Worker 后续搜索/导入将使用新地址，无需重新部署[/dim]")
    except (APIError, NetworkError) as e:
        raise click.ClickException(f"更新 VPS_URL 失败: {e}")


@config_group.command("get-vps-url")
def config_get_vps_url() -> None:
    """查看 Worker 当前配置的 VPS_URL"""
    try:
        client = APIClient()
        result = client.get_vps_url()
        url = result.get("vps_url", "")
        source = result.get("source", "unknown")
        if url:
            console.print(f"[cyan]VPS_URL[/cyan] = {url}")
            console.print(f"[dim]来源: {source}[/dim]")
        else:
            console.print("[warning]VPS_URL 未配置[/warning]")
            console.print("[dim]提示: 执行 `komichi-cli config set-vps-url <url>` 设置[/dim]")
    except (APIError, NetworkError) as e:
        raise click.ClickException(f"获取 VPS_URL 失败: {e}")
