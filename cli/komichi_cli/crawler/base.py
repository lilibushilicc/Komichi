"""爬虫基类与数据模型

定义所有爬虫的统一接口以及作品/章节的数据结构。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ChapterInfo:
    """章节数据

    image_paths: 图片来源（本地文件路径或远程图片 URL）
    r2_paths:    上传到 R2 后的对象路径（上传完成后回填）
    """

    chapter_num: int
    chapter_title: str
    image_paths: List[str] = field(default_factory=list)
    r2_paths: List[str] = field(default_factory=list)


@dataclass
class WorkInfo:
    """作品数据"""

    title: str
    category: str = ""
    cover_path: Optional[str] = None        # 封面来源（本地路径或 URL）
    cover_r2_path: Optional[str] = None     # 封面上传到 R2 后的路径
    source_url: str = ""                    # 作品来源（本地目录或抓取 URL）
    status: str = "ongoing"                 # 状态：ongoing / completed
    chapters: List[ChapterInfo] = field(default_factory=list)


class BaseCrawler(ABC):
    """爬虫抽象基类，定义统一抓取接口"""

    def __init__(
        self,
        source: str,
        title: str = "",
        category: str = "",
        cover: str = "",
    ):
        self.source = source
        self.title = title
        self.category = category
        self.cover = cover

    @abstractmethod
    def crawl(self) -> WorkInfo:
        """抓取作品信息及所有章节图片，返回 WorkInfo"""
        raise NotImplementedError
