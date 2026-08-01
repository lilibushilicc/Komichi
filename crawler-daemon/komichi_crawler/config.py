"""配置管理

配置来源优先级（高 → 低）：
    环境变量 KOMICHI_*  >  配置文件  >  默认值

配置文件路径：
    $KOMICHI_CONFIG 指定的路径  >  ./config.json  >  ~/.komichi/crawler-config.json

支持的环境变量（方便 Docker / systemd 部署）：
    KOMICHI_WORKER_URL, KOMICHI_USERNAME, KOMICHI_PASSWORD, KOMICHI_TOKEN
    KOMICHI_TIMEOUT, KOMICHI_MAX_RETRIES, KOMICHI_PLAYWRIGHT_TIMEOUT
    KOMICHI_LOG_FILE, KOMICHI_STATE_FILE
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULTS: Dict[str, Any] = {
    "worker_url": "",
    "username": "",
    "password": "",
    "token": "",
    "request_timeout": 60,
    "max_retries": 3,
    "playwright_timeout": 45000,
    "log_file": "logs/crawler.log",
    "state_file": "logs/state.json",
}

# 环境变量名 → 配置键
_ENV_MAP = {
    "KOMICHI_WORKER_URL": ("worker_url", str),
    "KOMICHI_USERNAME": ("username", str),
    "KOMICHI_PASSWORD": ("password", str),
    "KOMICHI_TOKEN": ("token", str),
    "KOMICHI_TIMEOUT": ("request_timeout", int),
    "KOMICHI_MAX_RETRIES": ("max_retries", int),
    "KOMICHI_PLAYWRIGHT_TIMEOUT": ("playwright_timeout", int),
    "KOMICHI_LOG_FILE": ("log_file", str),
    "KOMICHI_STATE_FILE": ("state_file", str),
}


def _config_path() -> Optional[Path]:
    if p := os.environ.get("KOMICHI_CONFIG"):
        return Path(p)
    cwd_cfg = Path.cwd() / "config.json"
    if cwd_cfg.exists():
        return cwd_cfg
    home_cfg = Path.home() / ".komichi" / "crawler-config.json"
    if home_cfg.exists():
        return home_cfg
    return None


def load_config() -> Dict[str, Any]:
    """加载配置：默认值 ← 配置文件 ← 环境变量"""
    cfg = dict(DEFAULTS)

    path = _config_path()
    if path and path.exists():
        try:
            file_cfg = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(file_cfg, dict):
                cfg.update(file_cfg)
        except (json.JSONDecodeError, OSError):
            pass

    for env_key, (cfg_key, typ) in _ENV_MAP.items():
        val = os.environ.get(env_key)
        if val is None or val == "":
            continue
        try:
            cfg[cfg_key] = typ(val)
        except (ValueError, TypeError):
            pass

    return cfg


def save_config(updates: Dict[str, Any]) -> None:
    """持久化配置到文件（合并写回）"""
    path = Path(os.environ.get("KOMICHI_CONFIG", Path.cwd() / "config.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
    existing.update(updates)
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def get(key: str, default: Any = None) -> Any:
    return load_config().get(key, default)


def set(key: str, value: Any) -> None:
    save_config({key: value})
