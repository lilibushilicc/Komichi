"""暂存数据转换工具

将爬虫产出的 WorkInfo 转换为可序列化的本地暂存字典，
以及构建与 Worker API 对齐的请求体。这些函数被多个 commands 子模块复用，
独立成模块以避免循环 import。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import config
from .api.client import APIError, NetworkError
from .crawler import WorkInfo
from .theme import console
from .uploader import R2Uploader


def work_to_staging(work: WorkInfo, source: str = "") -> Dict[str, Any]:
    """将 WorkInfo 转换为可序列化的本地暂存字典"""
    return {
        "slug": config.slugify(work.title),
        "work_id": None,
        "title": work.title,
        "category": work.category,
        "description": work.description,
        "source": source or "",
        "source_url": work.source_url,
        "cover_path": work.cover_path,
        "cover_r2_path": work.cover_r2_path,
        "status": work.status,
        "chapters": [
            {
                "chapter_num": c.chapter_num,
                "chapter_title": c.chapter_title,
            }
            for c in work.chapters
        ],
    }


def build_work_payload(
    staging: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """根据本地暂存数据构建 /api/work/update 的请求体（章节不含图片）"""
    chapters = staging.get("chapters", [])
    nums = [c.get("chapter_num", 0) for c in chapters if c.get("chapter_num") is not None]
    latest = max(nums) if nums else 0

    work = {
        "id": staging.get("work_id"),
        "title": staging.get("title", ""),
        "category": staging.get("category", ""),
        "description": staging.get("description", ""),
        "source": staging.get("source", ""),
        "cover_r2_path": staging.get("cover_r2_path") or "",
        "source_url": staging.get("source_url", ""),
        "latest_chapter_num": latest,
        "status": staging.get("status", "ongoing"),
    }
    chapter_list = [
        {
            "work_id": staging.get("work_id"),
            "chapter_num": c.get("chapter_num"),
            "chapter_title": c.get("chapter_title", ""),
            "images": [],
        }
        for c in chapters
    ]
    return work, chapter_list


def extract_work_id(data: Any) -> Optional[int]:
    """从响应数据中提取作品 ID"""
    if isinstance(data, dict):
        for k in ("id", "work_id", "workId"):
            v = data.get(k)
            if isinstance(v, int):
                return v
            if isinstance(v, str) and v.isdigit():
                return int(v)
        nested = data.get("work")
        if isinstance(nested, dict):
            return extract_work_id(nested)
    return None


def upload_missing_images(
    staging: Dict[str, Any],
    work_id: int,
    uploader: R2Uploader,
    only_chapter: Optional[int] = None,
) -> None:
    """上传尚未上传的封面，结果回填到 staging"""
    if staging.get("cover_path") and not staging.get("cover_r2_path"):
        try:
            with console.status("[info]上传封面...[/info]"):
                r2 = uploader.upload_cover(work_id, staging["cover_path"])
            staging["cover_r2_path"] = r2
            console.print(f"  [success]封面上传成功: {r2}[/success]")
        except (APIError, NetworkError) as e:
            console.print(f"  [error]封面上传失败: {e}[/error]")
