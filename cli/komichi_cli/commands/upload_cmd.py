"""upload 命令组：图片上传到 R2"""
from __future__ import annotations

import click

from .. import config
from ..api import APIClient
from ..api.client import APIError, NetworkError
from ..groups import DefaultGroup
from ..staging import upload_missing_images
from ..theme import console, print_interrupted
from ..uploader import R2Uploader


@click.group(name="upload", cls=DefaultGroup, default_cmd="images")
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
        f"[info]上传作品封面: {staging.get('title')} (ID: {work_id})[/info]"
    )

    try:
        client = APIClient()
        uploader = R2Uploader(client)
        upload_missing_images(staging, work_id, uploader)
    except (APIError, NetworkError) as e:
        raise click.ClickException(str(e))
    except KeyboardInterrupt:
        print_interrupted()
        raise click.Abort()

    config.save_staging(staging, slug=slug)
    console.print("[success]上传完成，已更新本地暂存[/success]")
