"""爬虫公共 HTTP 常量

各站点爬虫共享的浏览器请求头、状态映射与超时配置。
集中定义避免散落硬编码，便于统一升级 UA / 补充状态词。
"""
from __future__ import annotations

# Chrome 桌面版 UA（各站点爬虫共用，避免各自硬编码）
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)

# 各站点共用的基础请求头（UA + Accept + Accept-Language）
# 各源可在此基础上追加自身特有的 Referer / Accept 等。
BROWSER_HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 中文作品状态 -> 系统 status（ongoing / completed）
# 合并各源历史上出现过的所有写法，新增源直接复用。
STATUS_MAP = {
    # 连载中
    "连载中": "ongoing",
    "连载": "ongoing",
    "更新中": "ongoing",
    "连载数": "ongoing",
    # 完结
    "完结": "completed",
    "已完结": "completed",
    "全本": "completed",
    "完结啦": "completed",
}

# 爬取默认超时（毫秒）
DEFAULT_TIMEOUT = 45000
