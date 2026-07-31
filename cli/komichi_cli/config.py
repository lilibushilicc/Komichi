"""Komichi CLI 配置与本地数据管理

配置文件位置：~/.komichi/config.json
本地暂存位置：~/.komichi/staging/<slug>/work.json

本模块同时承担两件事：
1. 配置管理（Worker 地址、用户名、密码、Token 等）
2. 本地暂存数据管理（导入后尚未/已经同步到 Worker 的作品数据）
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ============================================================
# 路径常量
# ============================================================
CONFIG_DIR: Path = Path.home() / ".komichi"
CONFIG_FILE: Path = CONFIG_DIR / "config.json"
DEFAULT_STAGING_DIR: Path = CONFIG_DIR / "staging"

# ============================================================
# 默认配置
# ============================================================
DEFAULT_CONFIG: Dict[str, Any] = {
    "worker_url": "",          # Cloudflare Worker 地址
    "username": "",            # 登录用户名
    "password": "",            # 登录密码
    "token": "",               # 登录后获得的 Token（自动维护）
    "upload_path": "/api/r2/upload",  # 图片上传端点（通过 Worker 转存到 R2）
    "upload_concurrency": 4,   # 上传并发数（预留）
    "request_timeout": 30,     # 单次请求超时（秒）
    "max_retries": 3,          # 网络错误最大重试次数
    "staging_dir": "",         # 本地暂存目录（空=使用默认 ~/.komichi/staging/）
    "source_priority": ["godamh", "mh160mh", "guazi", "kuaikan", "tencent", "bilibili"],  # 站点源优先级（关键词导入时按序自动换备）
}


# ============================================================
# 配置文件读写
# ============================================================
def ensure_config_dir() -> Path:
    """确保配置目录存在"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def load_config() -> Dict[str, Any]:
    """加载配置，未初始化时写入默认配置"""
    ensure_config_dir()
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG.copy())
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
            cfg = json.load(f)
    except (json.JSONDecodeError, OSError):
        return DEFAULT_CONFIG.copy()
    merged = DEFAULT_CONFIG.copy()
    merged.update(cfg)
    return merged


def save_config(config: Dict[str, Any]) -> None:
    """保存配置到磁盘"""
    ensure_config_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get(key: str, default: Any = None) -> Any:
    """读取单个配置项"""
    return load_config().get(key, default)


def set(key: str, value: Any) -> None:
    """设置单个配置项并持久化"""
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)


def get_config_path() -> Path:
    """返回配置文件路径"""
    return CONFIG_FILE


# ============================================================
# 本地暂存（staging）管理
# ============================================================
def slugify(title: str) -> str:
    """将标题转换为安全的目录名（保留中文，仅清理非法字符）"""
    if not title:
        return "untitled"
    title = unicodedata.normalize("NFC", title)
    # 清理 Windows / 通用文件系统不允许的字符
    title = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", title)
    # 折叠连续空白
    title = re.sub(r"\s+", "_", title).strip("._")
    return title or "untitled"


def get_staging_root() -> Path:
    """返回暂存根目录，并确保其存在"""
    custom = get("staging_dir")
    if custom:
        root = Path(custom)
    else:
        ensure_config_dir()
        root = DEFAULT_STAGING_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def staging_dir(slug: str) -> Path:
    """根据 slug 返回对应暂存目录"""
    return get_staging_root() / slug


def save_staging(data: Dict[str, Any], slug: Optional[str] = None) -> Tuple[Path, str]:
    """保存一份暂存作品数据，返回 (文件路径, slug)"""
    slug = slug or data.get("slug") or slugify(data.get("title", "untitled"))
    target = staging_dir(slug)
    target.mkdir(parents=True, exist_ok=True)
    data["slug"] = slug
    out = target / "work.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return out, slug


def load_staging_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """根据 slug 读取暂存数据，不存在返回 None"""
    f = staging_dir(slug) / "work.json"
    if not f.exists():
        return None
    try:
        with open(f, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def list_staging() -> List[Dict[str, Any]]:
    """列出所有本地暂存作品"""
    root = get_staging_root()
    result: List[Dict[str, Any]] = []
    for d in root.iterdir():
        if not d.is_dir():
            continue
        wf = d / "work.json"
        if not wf.exists():
            continue
        try:
            with open(wf, "r", encoding="utf-8") as fh:
                result.append(json.load(fh))
        except (json.JSONDecodeError, OSError):
            continue
    return result


def find_staging(identifier: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """根据 slug / 数字 work_id / 暂存目录路径 / 源路径查找本地暂存作品

    返回 (data, slug)，未找到返回 (None, None)
    """
    if not identifier:
        return None, None

    # 1. 作为路径：暂存目录或 work.json 文件
    p = Path(identifier)
    candidate: Optional[Path] = None
    if p.is_dir():
        candidate = p / "work.json"
    elif p.is_file() and p.name == "work.json":
        candidate = p
    if candidate and candidate.exists():
        try:
            with open(candidate, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data, data.get("slug", p.name if p.is_dir() else p.parent.name)
        except (json.JSONDecodeError, OSError):
            pass

    # 2. 作为 slug 直接读取
    data = load_staging_by_slug(identifier)
    if data:
        return data, data.get("slug", identifier)

    # 3. 遍历匹配 work_id / slug / source_url
    try:
        numeric = int(identifier)
    except (ValueError, TypeError):
        numeric = None

    for item in list_staging():
        if numeric is not None and item.get("work_id") == numeric:
            return item, item.get("slug")
        if item.get("slug") == identifier:
            return item, item.get("slug")
        if item.get("source_url") == identifier:
            return item, item.get("slug")

    return None, None
