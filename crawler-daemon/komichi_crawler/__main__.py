"""命令行入口

用法:
    python -m komichi_crawler refresh              # 追更所有 VPS 源作品（cron 调用）
    python -m komichi_crawler import <url>         # 导入新作品（自动识别源）
    python -m komichi_crawler list                 # 列出 Worker 上的 VPS 源作品
    python -m komichi_crawler sources              # 列出支持的源
    python -m komichi_crawler check-playwright     # 检查 Playwright/Chromium 是否就绪
    python -m komichi_crawler serve [--host 0.0.0.0] [--port 8788]  # 启动 HTTP 服务
"""
from __future__ import annotations

import argparse
import sys

from . import __version__
from . import config as cfg_module
from . import registry
from .runner import setup_logging, refresh_all, import_work, list_vps_works, search_works


def _check_playwright() -> int:
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("[X] playwright 未安装")
        print("    pip install playwright && python -m playwright install chromium")
        return 1

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            b.close()
        print("[OK] Playwright + Chromium 就绪")
        return 0
    except Exception as e:
        print(f"[X] Chromium 启动失败: {e}")
        print("    请执行: python -m playwright install chromium")
        print("    ARM 平台还需: python -m playwright install-deps chromium")
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="komichi_crawler",
        description="Komichi 远程爬虫 — 把 bilibili/godamh 等源回写到 Cloudflare",
    )
    parser.add_argument("--version", action="version", version=f"komichi_crawler {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("refresh", help="追更所有 VPS 源作品（cron 调用）")
    sub.add_parser("list", help="列出 Worker 上的 VPS 源作品")
    sub.add_parser("sources", help="列出支持的源")
    sub.add_parser("check-playwright", help="检查 Playwright/Chromium 是否就绪")

    p_serve = sub.add_parser("serve", help="启动 HTTP 服务（供 Worker 调用）")
    p_serve.add_argument("--host", default="0.0.0.0", help="监听地址（默认 0.0.0.0）")
    p_serve.add_argument("--port", type=int, default=8788, help="监听端口（默认 8788）")

    p_search = sub.add_parser("search", help="搜索源站找新作品")
    p_search.add_argument("keyword", help="搜索关键词")
    p_search.add_argument("--import-first", action="store_true", help="搜到第一个直接导入")

    p_import = sub.add_parser("import", help="导入新作品（自动识别源）")
    p_import.add_argument("url", help="源站作品 URL (bilibili/godamh)")

    args = parser.parse_args(argv)

    # 不需要 Worker 配置的命令提前返回
    if args.command == "check-playwright":
        return _check_playwright()

    if args.command == "sources":
        print("VPS 支持的源:")
        for name in registry.supported_names():
            src = registry.get_source(name)
            print(f"  - {name}  (domains: {', '.join(src.DOMAINS)})")
        return 0

    if args.command == "serve":
        setup_logging()
        try:
            import uvicorn
            from .server import app
        except ImportError as e:
            print(f"[X] 依赖缺失: {e}")
            print("    pip install fastapi uvicorn")
            return 1
        print(f"[Komichi Crawler] 启动 HTTP 服务: http://{args.host}:{args.port}")
        print(f"  GET  /ping            - 健康检查")
        print(f"  GET  /api/sources     - 支持的源列表")
        print(f"  GET  /api/search      - 搜索源站")
        print(f"  POST /api/import      - 导入新作品")
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    # 其余命令需要日志 + Worker 配置
    setup_logging()

    conf = cfg_module.load_config()
    if not conf.get("worker_url"):
        print("[X] 未配置 worker_url，请设置环境变量 KOMICHI_WORKER_URL 或编辑 config.json")
        print("    参考 config.example.json")
        return 1

    try:
        if args.command == "refresh":
            result = refresh_all()
            print(f"\n追更完成: 共 {result['total']} 作品, "
                  f"更新 {result['updated']}, 新增 {result['new_chapters']} 章, "
                  f"错误 {result['errors']}")
            if result["errors"]:
                print("\n失败作品:")
                for d in result["details"]:
                    if d.get("error"):
                        print(f"  [{d['id']}] {d.get('source', '?')} {d['title']}: {d['error']}")
            return 0 if result["errors"] == 0 else 1

        elif args.command == "import":
            result = import_work(args.url)
            print(f"\n导入完成: 「{result['title']}」 work_id={result['work_id']}, "
                  f"源: {result.get('source', '?')}, {result['chapter_count']} 章")
            return 0

        elif args.command == "list":
            works = list_vps_works()
            if not works:
                print("Worker 上暂无 VPS 源作品")
                return 0
            print(f"\n共 {len(works)} 个 VPS 源作品:")
            for w in works:
                print(f"  [{w.get('id')}] [{w.get('source', '?')}] {w.get('title')} "
                      f"(最新: 第{w.get('latest_chapter_num', 0)}话, "
                      f"状态: {w.get('status', '?')})")
            return 0

        elif args.command == "search":
            results = search_works(args.keyword)
            if not any(results.values()):
                print(f"搜索「{args.keyword}」无结果")
                return 0
            idx = 0
            first_url = None
            for src_name, items in results.items():
                if not items:
                    continue
                print(f"\n[{src_name}] ({len(items)} 条)")
                for it in items:
                    print(f"  {idx}: {it['title']}")
                    print(f"     {it['url']}")
                    if first_url is None:
                        first_url = it["url"]
                    idx += 1
            if args.import_first and first_url:
                print(f"\n导入第一个结果...")
                result = import_work(first_url)
                print(f"导入完成: 「{result['title']}」 work_id={result['work_id']}")
            return 0

    except Exception as e:
        print(f"[X] 执行失败: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
