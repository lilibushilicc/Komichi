"""主运行逻辑

两个核心模式：
    refresh  — 追更：扫描 D1 中所有 VPS 支持源的作品，爬取最新章节，发现新章节则回写
    import   — 导入：给定源 URL，自动识别源并爬取注册为新作品（含封面上传）

支持多源（通过 registry 分发）：bilibili / godamh / 未来可扩展
数据流:
    源站 --爬取--> 章节列表+封面URL --WorkerAPI--> D1+R2
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config as cfg_module
from . import registry
from .worker_api import APIError, NetworkError, WorkerAPI

logger = logging.getLogger("komichi_crawler")


def setup_logging(log_file: Optional[str] = None) -> None:
    conf = cfg_module.load_config()
    log_path = log_file or conf.get("log_file", "logs/crawler.log")
    log_path_obj = Path(log_path)
    log_path_obj.parent.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)

    fh = logging.FileHandler(log_path_obj, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(ch)


def _load_state() -> Dict[str, Any]:
    conf = cfg_module.load_config()
    path = Path(conf.get("state_file", "logs/state.json"))
    if not path.exists():
        return {"last_run": None, "history": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"last_run": None, "history": []}


def _save_state(state: Dict[str, Any]) -> None:
    conf = cfg_module.load_config()
    path = Path(conf.get("state_file", "logs/state.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    state["history"] = state.get("history", [])[-20:]
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _record_run(mode: str, result: Dict[str, Any]) -> None:
    state = _load_state()
    now = datetime.now().isoformat(timespec="seconds")
    state["last_run"] = now
    entry = {"time": now, "mode": mode, **result}
    state.setdefault("history", []).append(entry)
    _save_state(state)


# ============================================================
# refresh — 追更所有 VPS 支持源的作品
# ============================================================
def refresh_all() -> Dict[str, Any]:
    """扫描 D1 中所有 VPS 支持源的作品，按 source 分发爬虫，回写新章节。

    返回统计:
        { total, refreshed, updated, new_chapters, errors, details: [...] }
    """
    api = WorkerAPI()
    timeout_ms = int(cfg_module.load_config().get("playwright_timeout", 45000))

    supported = set(registry.supported_names())
    all_works = api.list_works()
    works = [w for w in all_works if (w.get("source") or "") in supported]
    logger.info("找到 %d 个 VPS 源作品 (支持源: %s)",
                len(works), ", ".join(sorted(supported)))

    details: List[Dict[str, Any]] = []
    total_new = 0
    updated_count = 0
    error_count = 0

    for w in works:
        wid = w.get("id")
        title = w.get("title", "?")
        source_name = w.get("source") or ""
        source_url = w.get("source_url") or ""
        entry: Dict[str, Any] = {
            "id": wid, "title": title, "source": source_name,
            "new_chapters": 0, "updated": False, "error": None,
        }

        if not source_url:
            entry["error"] = "无 source_url"
            error_count += 1
            details.append(entry)
            continue

        src = registry.get_source(source_name)
        if not src:
            entry["error"] = f"无对应爬虫: {source_name}"
            error_count += 1
            details.append(entry)
            logger.error("[%s] %s — 无爬虫: %s", wid, title, source_name)
            continue

        try:
            # 1. 爬取源站最新数据
            crawled = src.crawl(source_url, timeout_ms=timeout_ms)

            # 2. 查 D1 已有章节
            work_detail = api.get_work(wid)
            existing_chapters = work_detail.get("chapters") or []
            existing_nums = {ch.get("chapter_num") for ch in existing_chapters}

            # 3. 找出新章节
            new_chapters = [
                ch for ch in crawled["chapters"]
                if ch["chapter_num"] not in existing_nums
            ]

            # 4. 检查封面是否需要补传
            existing_cover = (work_detail.get("cover_r2_path") or "").strip()
            need_cover = not existing_cover and bool(crawled.get("cover_url"))

            if not new_chapters and not need_cover:
                logger.info("[%s] %s (%s) — 无新章节，跳过", wid, title, source_name)
                details.append(entry)
                continue

            # 5. 上传封面（如果需要）
            cover_r2_path = existing_cover
            if need_cover:
                cover_url = crawled["cover_url"]
                cover_key = WorkerAPI.cover_key(wid, cover_url)
                try:
                    cover_r2_path = api.upload_image_from_url(cover_url, cover_key)
                    logger.info("[%s] %s — 封面上传成功: %s", wid, title, cover_r2_path)
                except (APIError, NetworkError) as e:
                    logger.warning("[%s] %s — 封面上传失败（继续更新元数据）: %s", wid, title, e)

            # 6. 回写元数据 + 章节列表（Worker upsert 会跳过已存在章节）
            work_payload = {
                "title": crawled["title"],
                "category": crawled.get("category") or w.get("category") or "",
                "description": crawled.get("description") or work_detail.get("description") or "",
                "cover_r2_path": cover_r2_path or None,
                "source": source_name,
                "source_url": source_url,
                "status": crawled.get("status", "ongoing"),
            }
            api.update_work(work_payload, crawled["chapters"])

            entry["new_chapters"] = len(new_chapters)
            entry["updated"] = True
            updated_count += 1
            total_new += len(new_chapters)

            if new_chapters:
                logger.info("[%s] %s (%s) — 新增 %d 章: %s",
                            wid, title, source_name, len(new_chapters),
                            ", ".join(ch["chapter_title"] for ch in new_chapters[:5])
                            + ("..." if len(new_chapters) > 5 else ""))
            else:
                logger.info("[%s] %s (%s) — 仅更新元数据/封面", wid, title, source_name)

        except src.CrawlError as e:
            entry["error"] = f"爬取失败: {e}"
            error_count += 1
            logger.error("[%s] %s (%s) — %s", wid, title, source_name, e)
        except (APIError, NetworkError) as e:
            entry["error"] = f"API错误: {e}"
            error_count += 1
            logger.error("[%s] %s (%s) — %s", wid, title, source_name, e)
        except Exception as e:
            entry["error"] = f"未知错误: {type(e).__name__}: {e}"
            error_count += 1
            logger.exception("[%s] %s (%s) — 未知错误", wid, title, source_name)

        details.append(entry)

    result = {
        "total": len(works),
        "refreshed": len(works) - error_count,
        "updated": updated_count,
        "new_chapters": total_new,
        "errors": error_count,
        "details": details,
    }
    _record_run("refresh", result)
    logger.info("追更完成: 共 %d 作品, 更新 %d, 新增 %d 章, 错误 %d",
                result["total"], result["updated"], result["new_chapters"], result["errors"])
    return result


# ============================================================
# import — 导入新作品（自动识别源）
# ============================================================
def import_work(source_url: str) -> Dict[str, Any]:
    """自动识别源并爬取注册为新作品。

    流程:
        1. registry 按 URL 域名匹配源模块
        2. 爬取作品信息 + 章节列表 + 封面 URL
        3. 调 update_work 创建作品记录（不含封面）→ 拿到 work_id
        4. 下载封面并上传到 R2 (komichi/covers/<work_id>.<ext>)
        5. 再次 update_work 回填 cover_r2_path
    """
    src = registry.resolve_source(source_url)
    if not src:
        raise ValueError(
            f"不支持的源 URL: {source_url}\n"
            f"VPS 支持的源: {', '.join(registry.supported_names())}"
        )

    api = WorkerAPI()
    timeout_ms = int(cfg_module.load_config().get("playwright_timeout", 45000))

    logger.info("开始爬取 [%s]: %s", src.NAME, source_url)
    crawled = src.crawl(source_url, timeout_ms=timeout_ms)
    logger.info("爬取成功: 「%s」 %d 章", crawled["title"], len(crawled["chapters"]))

    # 1. 先创建作品（不含封面），拿到 work_id
    work_payload = {
        "title": crawled["title"],
        "category": crawled.get("category", ""),
        "description": crawled.get("description", ""),
        "cover_r2_path": None,
        "source": src.NAME,
        "source_url": source_url,
        "status": crawled.get("status", "ongoing"),
    }
    created = api.update_work(work_payload, crawled["chapters"])
    work_id = created.get("work_id") or created.get("id") or created.get("workId")
    logger.info("作品已创建/更新: id=%s, 最新章节=%s",
                work_id, created.get("latest_chapter_num"))

    # 2. 上传封面
    cover_r2_path = ""
    if work_id and crawled.get("cover_url"):
        cover_key = WorkerAPI.cover_key(work_id, crawled["cover_url"])
        try:
            cover_r2_path = api.upload_image_from_url(crawled["cover_url"], cover_key)
            logger.info("封面上传成功: %s", cover_r2_path)
            api.update_work({**work_payload, "cover_r2_path": cover_r2_path}, [])
        except (APIError, NetworkError) as e:
            logger.warning("封面上传失败（作品元数据已写入）: %s", e)

    result = {
        "work_id": work_id,
        "title": crawled["title"],
        "source": src.NAME,
        "chapter_count": len(crawled["chapters"]),
        "cover_r2_path": cover_r2_path,
        "source_url": source_url,
    }
    _record_run("import", result)
    logger.info("导入完成: 「%s」 work_id=%s (源: %s)", crawled["title"], work_id, src.NAME)
    return result


# ============================================================
# list — 列出所有 VPS 支持源的作品
# ============================================================
def list_vps_works() -> List[Dict[str, Any]]:
    api = WorkerAPI()
    supported = set(registry.supported_names())
    all_works = api.list_works()
    works = [w for w in all_works if (w.get("source") or "") in supported]
    logger.info("共 %d 个 VPS 源作品 (源: %s)", len(works), ", ".join(sorted(supported)))
    return works


# ============================================================
# search — 搜索源站找新作品
# ============================================================
def search_works(keyword: str) -> Dict[str, List[Dict[str, str]]]:
    """搜索所有支持搜索的源，返回 {源名: [{title, url}]}"""
    timeout_ms = int(cfg_module.load_config().get("playwright_timeout", 45000))
    results = registry.search_all(keyword, timeout_ms=timeout_ms)
    total = sum(len(v) for v in results.values())
    logger.info("搜索「%s」: %d 条结果 (来自 %d 个源)",
                keyword, total, sum(1 for v in results.values() if v))
    return results
