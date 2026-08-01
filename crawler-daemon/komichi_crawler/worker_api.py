"""Cloudflare Worker API 客户端（CLI 与 crawler-daemon 共用）

封装所有与 Komichi Worker 的 HTTP 交互：
    - 登录获取 Token（自动维护、过期自动重登）
    - 列出作品 / 查询作品详情
    - 上传图片到 R2（支持本地文件或远程 URL）
    - 新增/更新作品与章节数据
    - Worker 端爬取导入（--via worker 模式）与 VPS_URL 动态配置

配置来源默认走 komichi_crawler.config（环境变量 + config.json）；
CLI 侧通过 set_config_provider() 覆盖为 ~/.komichi/config.json。
"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlparse

import httpx

from . import config as cfg_module


class APIError(Exception):
    def __init__(self, code: int, msg: str, data: Any = None):
        self.code = code
        self.msg = msg
        self.data = data
        super().__init__(f"API错误 [{code}]: {msg}")


class NetworkError(Exception):
    pass


_MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def _guess_mime(path: Union[str, Path]) -> str:
    ext = Path(path).suffix.lower()
    return _MIME_MAP.get(ext, "application/octet-stream")


def _ext_of(path: str) -> str:
    ext = Path(path).suffix
    if not ext and path.lower().startswith(("http://", "https://")):
        ext = Path(urlparse(path).path).suffix
    return (ext or ".jpg").lower()


# 配置加载/保存钩子：默认使用本包 config（daemon 环境），CLI 侧可覆盖
_config_provider: Optional[Callable[[], Dict[str, Any]]] = None
_config_setter: Optional[Callable[[str, Any], None]] = None


def set_config_provider(
    load_fn: Optional[Callable[[], Dict[str, Any]]] = None,
    save_fn: Optional[Callable[[str, Any], None]] = None,
) -> None:
    """注册配置加载/保存器（CLI 兼容层调用，读写 ~/.komichi/config.json）"""
    global _config_provider, _config_setter
    _config_provider = load_fn
    _config_setter = save_fn


def load_conf() -> Dict[str, Any]:
    if _config_provider is not None:
        try:
            return _config_provider()
        except Exception:
            pass
    return cfg_module.load_config()


def save_conf(key: str, value: Any) -> None:
    """持久化单个配置项（优先走注册的保存器，回退本包 config）"""
    if _config_setter is not None:
        try:
            _config_setter(key, value)
            return
        except Exception:
            pass
    cfg_module.set(key, value)


class WorkerAPI:
    """Cloudflare Worker API 客户端"""

    def __init__(self, **overrides: Any):
        conf = load_conf()
        self.base_url: str = (overrides.get("worker_url") or conf.get("worker_url") or "").rstrip("/")
        self.username: str = overrides.get("username") or conf.get("username", "")
        self.password: str = overrides.get("password") or conf.get("password", "")
        self.token: str = overrides.get("token") or conf.get("token", "")
        self.upload_path: str = conf.get("upload_path", "/api/r2/upload")
        self.timeout: float = float(overrides.get("timeout") or conf.get("request_timeout", 60))
        self.max_retries: int = int(overrides.get("max_retries") or conf.get("max_retries", 3))
        if not self.base_url:
            raise APIError(-1, "未配置 Worker 地址，请设置 KOMICHI_WORKER_URL 或编辑 config.json")

    # ============================================================
    # Token 管理
    # ============================================================
    def login(self) -> str:
        if not self.username or not self.password:
            raise APIError(-1, "未配置用户名或密码")
        resp = self._request(
            "POST", "/api/auth/login",
            json={"username": self.username, "password": self.password},
            _auth=False,
        )
        data = resp.get("data") or {}
        token = data.get("token") or data.get("access_token") or ""
        if not token:
            raise APIError(resp.get("code", -1), "登录返回中未包含 token", data)
        self.token = token
        save_conf("token", token)
        return token

    def ensure_token(self) -> str:
        if not self.token:
            return self.login()
        return self.token

    def _clear_token(self) -> None:
        self.token = ""
        save_conf("token", "")

    # ============================================================
    # 核心请求（重试 + Token 刷新）
    # ============================================================
    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        _auth: bool = True,
        _attempt: int = 0,
    ) -> Dict[str, Any]:
        if files:
            for _, item in files.items():
                fobj = item[1] if isinstance(item, (tuple, list)) else item
                if hasattr(fobj, "seek"):
                    try:
                        fobj.seek(0)
                    except (OSError, ValueError):
                        pass

        url = f"{self.base_url}{path}"
        headers: Dict[str, str] = {}
        if _auth:
            headers["Authorization"] = f"Bearer {self.ensure_token()}"

        try:
            with httpx.Client(timeout=self.timeout, http2=False) as client:
                resp = client.request(method, url, json=json, params=params,
                                      files=files, data=data, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError) as e:
            if _attempt < self.max_retries:
                time.sleep(min(2 ** _attempt, 8))
                return self._request(method, path, json=json, params=params,
                                     files=files, data=data, _auth=_auth, _attempt=_attempt + 1)
            raise NetworkError(f"网络请求失败（已重试 {self.max_retries} 次）: {e}") from e

        if resp.status_code == 401 and _auth and _attempt < self.max_retries:
            self._clear_token()
            return self._request(method, path, json=json, params=params,
                                 files=files, data=data, _auth=_auth, _attempt=_attempt + 1)

        try:
            payload = resp.json()
        except Exception:
            raise NetworkError(f"响应解析失败 (HTTP {resp.status_code}): {resp.text[:300]}")

        code = payload.get("code", resp.status_code)
        if code != 200:
            if code in (401, 403) and _auth and _attempt < self.max_retries:
                self._clear_token()
                return self._request(method, path, json=json, params=params,
                                     files=files, data=data, _auth=_auth, _attempt=_attempt + 1)
            raise APIError(code, payload.get("msg", "未知错误"), payload.get("data"))
        return payload

    # ============================================================
    # 业务接口
    # ============================================================
    def list_works(self, source_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出 Worker 上的所有作品（自动翻页）。

        source_filter 为 None 时返回全部；指定如 "bilibili" 则只返回该源的作品。
        """
        all_works: List[Dict[str, Any]] = []
        page = 1
        size = 100
        while True:
            resp = self._request("GET", "/api/work/list", params={"page": page, "size": size})
            data = resp.get("data") or {}
            batch = data.get("list") or data.get("works") or []
            if not batch:
                break
            all_works.extend(batch)
            if len(all_works) >= (data.get("total") or 0):
                break
            page += 1

        if source_filter:
            all_works = [w for w in all_works if (w.get("source") or "") == source_filter]
        return all_works

    def get_work(self, work_id: Union[int, str]) -> Dict[str, Any]:
        resp = self._request("GET", f"/api/work/{work_id}")
        return resp.get("data") or {}

    def update_work(
        self, work: Dict[str, Any], chapters: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """新增/更新作品与章节数据。

        请求体使用扁平格式 { title, ..., chapters: [...] }，
        Worker 会基于 source_url 或 title 做 upsert（同时兼容 {work, chapters} 包装格式）。
        """
        payload = {**work, "chapters": chapters}
        resp = self._request("POST", "/api/work/update", json=payload)
        return resp.get("data") or {}

    def upload_image(self, file_path: str, r2_key: str) -> str:
        """上传本地图片文件到 R2"""
        p = Path(file_path)
        if not p.exists():
            raise APIError(-1, f"待上传文件不存在: {file_path}")
        mime = _guess_mime(p)
        with open(p, "rb") as f:
            files = {"file": (p.name, f, mime)}
            form = {"key": r2_key}
            resp = self._request("POST", self.upload_path, files=files, data=form)
        d = resp.get("data") or {}
        return d.get("r2_path") or d.get("path") or r2_key

    def upload_image_from_url(self, image_url: str, r2_key: str) -> str:
        """下载远程图片并上传到 R2。

        用于上传站点封面：先 HTTP 下载到临时文件，再 multipart 上传，
        上传完成后删除临时文件。
        """
        if not image_url:
            return ""
        try:
            with httpx.Client(timeout=60, follow_redirects=True) as dl:
                resp = dl.get(image_url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise NetworkError(f"下载图片失败 {image_url}: {e}") from e

        ext = _ext_of(image_url)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        try:
            tmp.write(resp.content)
            tmp.close()
            return self.upload_image(tmp.name, r2_key)
        finally:
            try:
                Path(tmp.name).unlink()
            except OSError:
                pass

    @staticmethod
    def cover_key(work_id: Union[int, str], cover_path: str) -> str:
        return f"komichi/covers/{work_id}{_ext_of(cover_path)}"

    # ============================================================
    # Worker 端爬取（CLI --via worker 模式）
    # ============================================================
    def import_via_worker(self, source_url: str) -> Dict[str, Any]:
        """让 Worker 自己爬取并导入作品（仅支持 4 个 HTTP 源）

        调用 POST /api/work/import，Worker 端爬取后直接写入 D1。
        CLI 不参与爬取，只发指令。
        """
        resp = self._request(
            "POST", "/api/work/import",
            json={"source_url": source_url},
        )
        return resp.get("data") or {}

    def force_check(self, work_id: Union[int, str]) -> Dict[str, Any]:
        """让 Worker 实时爬取源站检查更新（?force=true）

        返回 {work, latest_chapter, has_update, new_chapter_count, ...}
        """
        resp = self._request(
            "GET", f"/api/work/check/{work_id}",
            params={"force": "true"},
        )
        return resp.get("data") or {}

    def search_via_worker(self, keyword: str) -> Dict[str, Any]:
        """通过 Worker 代理搜索源站漫画（Worker 转发给 VPS）

        返回 {results: {源名: [{title, url}]}}
        """
        resp = self._request(
            "GET", "/api/work/search",
            params={"keyword": keyword},
        )
        return resp.get("data") or {}

    def get_vps_url(self) -> Dict[str, Any]:
        """获取 Worker 当前配置的 VPS_URL

        返回 {vps_url: str, source: 'database'|'env'|'unset'}
        """
        resp = self._request("GET", "/api/work/vps-url")
        return resp.get("data") or {}

    def set_vps_url(self, vps_url: str) -> Dict[str, Any]:
        """更新 Worker 的 VPS_URL 配置（写入 D1，无需重新部署）

        返回 {vps_url: str}
        """
        resp = self._request(
            "PUT", "/api/work/vps-url",
            json={"vps_url": vps_url},
        )
        return resp.get("data") or {}
