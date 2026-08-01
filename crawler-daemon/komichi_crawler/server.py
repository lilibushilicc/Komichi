"""轻量 FastAPI HTTP 服务

供 Worker 作为搜索代理调用，统一响应格式与 Worker 保持一致:
    {"code": 200, "msg": "success", "data": {...}}

接口:
    GET  /ping            — 健康检查
    GET  /api/sources     — 支持的源列表
    GET  /api/search      — 搜索源站 (keyword)
    POST /api/import      — 导入新作品 (source_url)

启动:
    python -m komichi_crawler serve [--host 0.0.0.0] [--port 8788]
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import registry
from .runner import import_work

logger = logging.getLogger("komichi_crawler")

app = FastAPI(title="Komichi Crawler", version="1.0")

# CORS — 允许所有来源，和 Worker 一样
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 请求/响应模型
# ============================================================
class ImportRequest(BaseModel):
    source_url: str


def _ok(data: Any, msg: str = "success") -> Dict[str, Any]:
    """成功响应"""
    return {"code": 200, "msg": msg, "data": data}


def _err(msg: str) -> Dict[str, Any]:
    """错误响应"""
    return {"code": 500, "msg": msg, "data": None}


# ============================================================
# 路由
# ============================================================
@app.get("/ping")
def ping():
    """健康检查"""
    return _ok({"ping": "pong", "service": "komichi-crawler"})


@app.get("/api/sources")
def sources():
    """返回支持的源列表"""
    return _ok(registry.supported_names())


@app.get("/api/search")
def search(keyword: str):
    """搜索所有支持搜索的源站

    返回:
        {code:200, msg:"success", data:{results:{源名:[{title,url}]}}}
    """
    try:
        results = registry.search_all(keyword)
        return _ok({"results": results})
    except Exception as e:
        logger.exception("搜索失败: keyword=%s", keyword)
        return _err(f"搜索失败: {e}")


@app.post("/api/import")
def import_work_api(req: ImportRequest):
    """导入新作品（自动识别源）

    返回:
        {code:200, msg:"导入成功", data:{work_id,title,source,chapter_count}}
    """
    try:
        result = import_work(req.source_url)
        return _ok(
            {
                "work_id": result.get("work_id"),
                "title": result.get("title"),
                "source": result.get("source"),
                "chapter_count": result.get("chapter_count"),
            },
            msg="导入成功",
        )
    except Exception as e:
        logger.exception("导入失败: source_url=%s", req.source_url)
        return _err(f"导入失败: {e}")
