"""Komichi CLI 工具

基于 Cloudflare Serverless 架构的私有化漫画追更管理系统命令行工具。
负责重型任务：新增作品导入、首次章节抓取、图片下载、R2 上传、数据初始化。
"""
from __future__ import annotations

import sys
from pathlib import Path

__version__ = "0.1.0"

# 开发环境兼容：爬虫实现已合并至 crawler-daemon/komichi_crawler（单一事实来源），
# 此处将仓库内目录加入 sys.path 直接复用源码，无需单独安装 komichi-crawler 包；
# 正式安装（pip install komichi-cli）时回退到 site-packages 中的已安装包。
_REPO_CRAWLER = Path(__file__).resolve().parents[2] / "crawler-daemon"
if (_REPO_CRAWLER / "komichi_crawler").is_dir():
    if str(_REPO_CRAWLER) not in sys.path:
        sys.path.insert(0, str(_REPO_CRAWLER))
