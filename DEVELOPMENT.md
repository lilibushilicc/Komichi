# 开发文档 · Komichi

本文档面向开发者：仓库结构、架构、代码组织约定、开发与验证流程。

## 仓库结构

| 目录 | 技术栈 | 职责 |
|------|--------|------|
| `worker/` | TypeScript + Hono | **核心服务**：API、D1 数据、R2 图片、cron 追更 4 个 HTTP 源、服务器端导入 |
| `crawler-daemon/` | Python (Playwright / curl_cffi / httpx) | **VPS 爬虫节点**：全 6 源 + 搜索，`komichi_crawler` 包为爬虫/API 客户端的**单一事实来源** |
| `cli/` | Python + Click | 本地命令行：导入/同步/上传；爬虫与 API 客户端均为对 `komichi_crawler` 的兼容层 |
| `android/` | Kotlin + Jetpack Compose | Android 客户端 |
| `windows/` | C# + WPF (.NET 8) | Windows 桌面客户端 |
| `komichi-ui/` | HTML + CSS | 网页端界面（可选） |
| 根目录文档 | Markdown | 汇总说明（`README.md`）、部署（`DEPLOYMENT.md`）、使用（`USAGE.md`）、开发（本文件） |

## 架构要点

```
客户端 (android / windows / komichi-ui / cli)  ──┐
                                                 ▼
                    ┌──────────────────────────────┐
                    │  Worker (Hono) + D1 + R2      │  ← 核心，必部署
                    │  · API /auth /work /r2        │
                    │  · cron 追更 4 源 (HTTP)      │
                    └──────────────────────────────┘
                        ▲ HTTPS + JWT
                        │ POST /api/work/update 等
        ┌───────────────┴───────────────┐
        │  VPS: crawler-daemon           │  ← 可选，Worker 爬虫的超集
        │  · bilibili (Playwright)       │     6 源全支持 + 搜索
        │  · godamh (curl_cffi TLS 伪装) │     不存数据，全部回写 Worker
        └───────────────────────────────┘
```

- **Worker 是核心**：全部数据（D1）+ API 在 Cloudflare，可单独运行（4 源）。
- **VPS 是增强节点**：只跑 Worker 跑不了的源（浏览器渲染 / TLS 伪装），数据回写 Worker，不可独立运行。
- **客户端全部只连 Worker API**，VPS 对客户端完全透明。

## 代码组织约定

### Python 爬虫：单一事实来源（`crawler-daemon/komichi_crawler/`）

CLI 与 crawler-daemon **共用**同一套爬虫与 Worker API 客户端：

- `base.py` — `WorkInfo/ChapterInfo` 数据模型、`CrawlError/SourceNotFound/SourceUnavailable` 异常、`BaseCrawler` 基类、`crawl_work()` 适配器
- `_http.py` — 公共 HTTP 常量（`BROWSER_UA` / `BROWSER_HEADERS` / `STATUS_MAP` / `DEFAULT_TIMEOUT`）
- `registry.py` — 双接口注册表：类接口（`register_source` / `get_crawler` / `crawl_with_fallback`）+ 模块接口（`get_source` / `resolve_source` / `search_all`）
- `<source>.py`（guazi/kuaikan/tencent/mh160mh/godamh/bilibili）— 每源一个文件，**同时提供**：
  - 模块接口：`NAME` / `DOMAINS` / `HAS_SEARCH` / `is_supported()` / `crawl()` / 可选 `search()`
  - 类接口：`@register_source class XxxCrawler(BaseCrawler)`，`crawl()` 内部调用模块级 `crawl()`
- `worker_api.py` — `WorkerAPI` 客户端（登录/列表/上传/更新/服务器端导入）；配置来源通过 `set_config_provider()` 注入（daemon 用 env+config.json，CLI 用 `~/.komichi/config.json`）
- `generic.py` — `LocalCrawler`（本地文件夹）/ `UrlCrawler`（URL 列表/manifest），仅 CLI 使用

**CLI 兼容层**（`cli/komichi_cli/`）：
- `crawler/__init__.py` — 从共享包再导出，并注入 `source_priority` 配置
- `api/client.py` — `APIClient` 继承共享 `WorkerAPI`，注册 CLI 配置读写
- `uploader/r2_uploader.py` — 薄封装（本地直传 / 远程 URL 下载后上传）
- 仓库开发环境：`komichi_cli/__init__.py` 自动把 `crawler-daemon/` 加入 `sys.path`，无需安装；正式安装依赖 PyPI 的 `komichi-crawler`

> **改爬虫只改 `crawler-daemon/komichi_crawler/`**，CLI 侧无需改动。

### Worker (TypeScript) 侧约定

- `worker/src/crawler/` — 4 个 HTTP 源（mh160mh/tencent/guazi/kuaikan）的 TS 实现，与 Python 版接口对齐（`crawl()` → `WorkInfo` 结构）
- `worker/src/routes/work.ts` — 工作区路由：`update/list/{id}/check/import/search/vps-url`
- 新增 Worker 源时同步维护 `registry.ts` 的源表与 cron 逻辑

## 环境准备

```bash
# Worker
cd worker
npm install
npx wrangler login            # 或使用 CLOUDFLARE_API_TOKEN

# Python（VPS / CLI 共用）
pip install -r crawler-daemon/requirements.txt
python -m playwright install chromium     # 仅 bilibili 源需要

# CLI（开发模式，直接复用仓库内 komichi_crawler）
pip install -e cli/
```

## 开发验证流程

```bash
# 1. Python：编译 + 导入 + 命令入口
python -m compileall crawler-daemon/komichi_crawler cli/komichi_cli
cd cli && python -m komichi_cli.main --help          # CLI 入口
cd crawler-daemon && python -m komichi_crawler --help # daemon 入口
python -m komichi_crawler sources                     # 验证 6 源注册

# 2. Worker：类型检查 + 构建
cd worker
npm run typecheck        # tsc --noEmit
npm run build            # wrangler deploy 前必过

# 3. 本地 D1 联调（可选）
npx wrangler dev --local --persist-to ../.wrangler-dev
```

> 提交前确保：Python `compileall` 无错、Worker `typecheck` 无错；涉及 API 契约变更时同步更新 `cli/README.md` 的「后端 API 契约」章节。

## 常见开发任务

### 新增站点源（Python，CLI + VPS 同时生效）

1. 在 `crawler-daemon/komichi_crawler/` 新建 `<source>.py`（参考 `tencent.py`）：
   - 模块接口：`NAME` / `DOMAINS` / `is_supported()` / `crawl()`，支持搜索则加 `HAS_SEARCH = True` 与 `search()`
   - 类接口：`@register_source class XxxCrawler(BaseCrawler)`，`crawl()` 调模块级 `crawl()`
2. 在 `registry.py` 的 `DEFAULT_SOURCE_ORDER` 加入新源名
3. 如需 Worker cron 也支持（纯 HTTP 源）：在 `worker/src/crawler/` 实现 TS 版并注册
4. 验证：`python -m komichi_crawler sources`、`import from <src> <url>`、`npm run typecheck`

### 新增 Worker API 端点

1. 在 `worker/src/routes/` 添加路由并注册到 `index.ts`
2. 同步 D1 schema（`worker/schema.sql` + 增量 `migrations/`）
3. 更新 `cli/README.md` 的 API 契约表；CLI 侧在 `worker_api.py` 添加对应方法（VPS 同样受益）

### 改 Worker 与 Python 双端爬虫（同源）

保持两端 `crawl()` 返回结构一致（`{title, cover_url, description, category, status, chapters[]}`）与状态词一致（`_http.STATUS_MAP` / TS 侧 `STATUS_MAP`），避免双端数据格式分叉。
