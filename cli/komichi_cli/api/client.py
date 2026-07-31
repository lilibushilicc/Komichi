"""Cloudflare Worker API 客户端

封装所有与 Worker 的 HTTP 交互：
- 登录获取 Token（自动维护、过期自动重登）
- 作品/章节的新增与更新
- 作品列表与详情查询
- 图片上传（通过 Worker 转存到 R2）

统一响应格式：{ "code": 200, "msg": "success", "data": {} }
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx

from .. import config as cfg_module


class APIError(Exception):
    """API 业务错误（code != 200）"""

    def __init__(self, code: int, msg: str, data: Any = None):
        self.code = code
        self.msg = msg
        self.data = data
        super().__init__(f"API错误 [{code}]: {msg}")


class NetworkError(Exception):
    """网络层错误（超时、连接失败、响应解析失败）"""


# 图片扩展名 -> MIME 映射
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


class APIClient:
    """Cloudflare Worker API 客户端"""

    def __init__(
        self,
        worker_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ):
        conf = cfg_module.load_config()
        self.base_url: str = (worker_url or conf.get("worker_url") or "").rstrip("/")
        self.username: str = username or conf.get("username", "")
        self.password: str = password or conf.get("password", "")
        self.token: str = token or conf.get("token", "")
        self.upload_path: str = conf.get("upload_path", "/api/r2/upload")
        self.timeout: float = float(
            timeout if timeout is not None else conf.get("request_timeout", 30)
        )
        self.max_retries: int = int(
            max_retries if max_retries is not None else conf.get("max_retries", 3)
        )
        if not self.base_url:
            raise APIError(-1, "未配置 Worker 地址，请先执行 `komichi-cli init`")

    # ============================================================
    # Token 管理
    # ============================================================
    def login(self) -> str:
        """登录获取 Token 并持久化"""
        if not self.username or not self.password:
            raise APIError(-1, "未配置用户名或密码，请先执行 `komichi-cli init`")
        resp = self._request(
            "POST",
            "/api/auth/login",
            json={"username": self.username, "password": self.password},
            _auth=False,
        )
        data = resp.get("data") or {}
        token = data.get("token") or data.get("access_token") or ""
        if not token:
            raise APIError(resp.get("code", -1), "登录返回中未包含 token", data)
        self.token = token
        cfg_module.set("token", token)
        return token

    def ensure_token(self) -> str:
        """确保拥有可用 Token，没有则登录"""
        if not self.token:
            return self.login()
        return self.token

    def _clear_token(self) -> None:
        """清除本地 Token（用于过期后重登）"""
        self.token = ""
        cfg_module.set("token", "")

    # ============================================================
    # 核心请求（含重试与 Token 刷新）
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
        # 重置文件指针，保证重试时能重新读取文件内容
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
                resp = client.request(
                    method,
                    url,
                    json=json,
                    params=params,
                    files=files,
                    data=data,
                    headers=headers,
                )
        except (httpx.TimeoutException, httpx.TransportError) as e:
            # 网络错误：指数退避重试
            if _attempt < self.max_retries:
                time.sleep(min(2 ** _attempt, 8))
                return self._request(
                    method, path, json=json, params=params, files=files,
                    data=data, _auth=_auth, _attempt=_attempt + 1,
                )
            raise NetworkError(
                f"网络请求失败（已重试 {self.max_retries} 次）: {e}"
            ) from e

        # HTTP 401：Token 失效，清除后重试一次（会触发重新登录）
        if resp.status_code == 401 and _auth and _attempt < self.max_retries:
            self._clear_token()
            return self._request(
                method, path, json=json, params=params, files=files,
                data=data, _auth=_auth, _attempt=_attempt + 1,
            )

        # 解析 JSON
        try:
            payload = resp.json()
        except Exception:
            raise NetworkError(
                f"响应解析失败 (HTTP {resp.status_code}): {resp.text[:300]}"
            )

        code = payload.get("code", resp.status_code)
        if code != 200:
            # 业务层鉴权失败：刷新 Token 后重试
            if code in (401, 403) and _auth and _attempt < self.max_retries:
                self._clear_token()
                return self._request(
                    method, path, json=json, params=params, files=files,
                    data=data, _auth=_auth, _attempt=_attempt + 1,
                )
            raise APIError(code, payload.get("msg", "未知错误"), payload.get("data"))
        return payload

    # ============================================================
    # 业务接口
    # ============================================================
    def update_work(
        self, work: Dict[str, Any], chapters: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """新增/更新作品与章节数据

        请求体：{ "work": {...}, "chapters": [{...}, ...] }
        当 work.id 为空时视为新增，Worker 应返回新 ID。
        """
        payload = {"work": work, "chapters": chapters}
        resp = self._request("POST", "/api/work/update", json=payload)
        return resp.get("data") or {}

    def list_works(self) -> List[Dict[str, Any]]:
        """查询 Worker 上的所有作品"""
        resp = self._request("GET", "/api/work/list")
        data = resp.get("data")
        if isinstance(data, dict):
            # 兼容 {works: [...]} / {list: [...]} 两种包装
            return data.get("works") or data.get("list") or []
        if isinstance(data, list):
            return data
        return []

    def get_work(self, work_id: Union[int, str]) -> Dict[str, Any]:
        """查询作品详情"""
        resp = self._request("GET", f"/api/work/{work_id}")
        return resp.get("data") or {}

    def upload_image(self, file_path: str, r2_key: str) -> str:
        """上传单张图片到 R2（通过 Worker 转存）

        参数 file_path 可以是本地文件路径；r2_key 为目标 R2 对象键。
        返回 R2 存储路径。
        """
        p = Path(file_path)
        if not p.exists():
            raise APIError(-1, f"待上传文件不存在: {file_path}")
        mime = _guess_mime(p)
        with open(p, "rb") as f:
            files = {"file": (p.name, f, mime)}
            form = {"key": r2_key}
            resp = self._request(
                "POST", self.upload_path, files=files, data=form
            )
        d = resp.get("data") or {}
        return d.get("r2_path") or d.get("path") or r2_key
