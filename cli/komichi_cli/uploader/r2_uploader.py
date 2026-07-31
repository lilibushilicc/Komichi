from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

import httpx

from ..api import APIClient
from ..api.client import NetworkError


def _is_url(path: str) -> bool:
    return bool(path) and path.lower().startswith(("http://", "https://"))


def _ext_of(path: str) -> str:
    ext = Path(path).suffix
    if not ext and _is_url(path):
        ext = Path(urlparse(path).path).suffix
    return (ext or ".jpg").lower()


class R2Uploader:
    """R2 上传器（仅处理封面上传）"""

    def __init__(self, client: APIClient):
        self.client = client

    @staticmethod
    def cover_key(work_id, cover_path: str) -> str:
        return f"komichi/covers/{work_id}{_ext_of(cover_path)}"

    def upload_cover(self, work_id, cover_path: str) -> str:
        if not cover_path:
            return ""
        local_path, is_temp = self._materialize(cover_path)
        try:
            key = self.cover_key(work_id, cover_path)
            return self.client.upload_image(local_path, key)
        finally:
            self._cleanup(local_path, is_temp)

    @staticmethod
    def _materialize(image_path: str) -> Tuple[str, bool]:
        if _is_url(image_path):
            try:
                with httpx.Client(timeout=60, http2=False) as dl_client:
                    resp = dl_client.get(image_path, follow_redirects=True)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                raise NetworkError(f"下载图片失败 {image_path}: {e}") from e
            ext = _ext_of(image_path)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            try:
                tmp.write(resp.content)
            finally:
                tmp.close()
            return tmp.name, True
        return image_path, False

    @staticmethod
    def _cleanup(path: Optional[str], is_temp: bool) -> None:
        if is_temp and path:
            try:
                Path(path).unlink()
            except OSError:
                pass
