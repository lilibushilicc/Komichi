"""CLI API 客户端兼容层 → 共享包 komichi_crawler.worker_api"""
from __future__ import annotations

import komichi_crawler.worker_api as _wa

from komichi_crawler.worker_api import (  # noqa: F401,E402
    APIError,
    NetworkError,
    WorkerAPI,
)

from .. import config as _cfg

# 注册 CLI 配置（~/.komichi/config.json）作为共享客户端的配置来源，
# 登录 Token 也会写回该文件。
_wa.set_config_provider(_cfg.load_config, _cfg.set)


class APIClient(WorkerAPI):
    """CLI 客户端（共享 WorkerAPI 的别名，保留旧类名与构造签名）"""
