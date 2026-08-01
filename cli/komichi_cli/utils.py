"""共享工具函数

提供章节范围格式化、域名提取等跨模块复用的小工具，
避免命令模块之间的相互依赖。
"""
from __future__ import annotations

from typing import List
from urllib.parse import urlparse


def format_chapter_range(nums: List[int]) -> str:
    """将章节号列表格式化为紧凑展示（连续区间合并）

    [1,2,3,5,7,8,9] -> "1-3, 5, 7-9"
    """
    if not nums:
        return ""
    nums = sorted(nums)
    parts: List[str] = []
    start = prev = nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        parts.append(f"{start}-{prev}" if start != prev else str(start))
        start = prev = n
    parts.append(f"{start}-{prev}" if start != prev else str(start))
    return ", ".join(parts)


def domain_of(url: str) -> str:
    """从 source_url 提取域名展示（无协议时直接返回原值）"""
    if not url:
        return ""
    if "://" in url:
        try:
            parsed = urlparse(url)
            host = parsed.netloc or parsed.path
            return host or url
        except (ValueError, TypeError):
            return url
    # 无协议：取第一个 / 之前的部分
    return url.split("/", 1)[0] if "/" in url else url
