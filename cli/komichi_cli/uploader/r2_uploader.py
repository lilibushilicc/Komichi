"""R2 上传器（仅处理封面上传）

本地路径直传 / 远程 URL 下载后上传，具体实现位于共享客户端
komichi_crawler.worker_api.WorkerAPI（upload_image / upload_image_from_url）。
"""
from __future__ import annotations

from ..api import APIClient


def _is_url(path: str) -> bool:
    return bool(path) and path.lower().startswith(("http://", "https://"))


class R2Uploader:
    """R2 上传器：上传作品封面到 R2（通过 Worker /api/r2/upload）"""

    def __init__(self, client: APIClient):
        self.client = client

    def upload_cover(self, work_id, cover_path: str) -> str:
        if not cover_path:
            return ""
        key = self.client.cover_key(work_id, cover_path)
        if _is_url(cover_path):
            return self.client.upload_image_from_url(cover_path, key)
        return self.client.upload_image(cover_path, key)
