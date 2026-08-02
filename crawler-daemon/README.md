# Komichi 远程爬虫守护进程（crawler-daemon）

部署在能跑 Chromium 的 Linux VPS / 容器上，处理 Worker 跑不了的源（**bilibili** Playwright 渲染、**godamh** TLS 指纹伪装），是 **Worker 爬虫的超集**：全 6 源支持 + 关键词搜索。数据通过 Worker API 全部回写到 Cloudflare（D1 + R2），**VPS 不存任何本地数据库，依赖 Worker，不可脱离运行**。

本包 `komichi_crawler` 与 CLI **共用**：所有站点爬虫（模块接口 + 类接口双形态）、Worker API 客户端、配置加载的单一事实来源。**新增/修改爬虫就在这里，CLI 侧无需改动。**

## 为什么需要

Worker 的 cron 已能追更 6 个纯 HTTP 源（mh160mh/tencent/guazi/kuaikan/dongmanmanhua/sfacg），但 bilibili（接口带 JS/WASM 加密，必须浏览器渲染）与 godamh（需 TLS 伪装）Worker 跑不了，由本模块在 VPS 上完成。

## 工作模式

```bash
python -m komichi_crawler refresh              # 追更所有 VPS 源作品（cron 调用）
python -m komichi_crawler import <url>         # 导入新作品（自动识别全 6 源）
python -m komichi_crawler search <关键词>      # 搜索 bilibili/godamh（--import-first 直接导入）
python -m komichi_crawler serve                # HTTP 服务（Worker 搜索代理转发）
python -m komichi_crawler list|sources         # 作品列表 / 源列表
python -m komichi_crawler check-playwright     # 检查 Chromium 是否就绪
```

## 快速开始

```bash
# 1. 配置（环境变量或 config.json 二选一）
cp config.example.json config.json            # 填 worker_url / username / password
# 或 export KOMICHI_WORKER_URL=... KOMICHI_USERNAME=crawler KOMICHI_PASSWORD=crawler123
#    账号需 CRAWLER 角色（Worker 端 init.sql 的 crawler/crawler123 默认即此角色）

# 2. 安装依赖
pip install -r requirements.txt
python -m playwright install chromium
python -m playwright install-deps chromium    # Linux 需 sudo

# 3. 验证 + 导入
python -m komichi_crawler check-playwright    # [OK] Playwright + Chromium 就绪
python -m komichi_crawler import "https://manga.bilibili.com/detail/mc24742"
```

导入成功后作品出现在 Worker 列表里，`refresh` 时自动追更。

## 配置项

| 配置键 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `worker_url` | `KOMICHI_WORKER_URL` | — | Worker 地址 |
| `username` / `password` | `KOMICHI_USERNAME` / `KOMICHI_PASSWORD` | — | CRAWLER 角色账号 |
| `token` | `KOMICHI_TOKEN` | `""` | 自动维护，过期自动重登 |
| `request_timeout` / `max_retries` | `KOMICHI_TIMEOUT` / `KOMICHI_MAX_RETRIES` | `60` / `3` | 请求超时（秒）/ 重试 |
| `playwright_timeout` | `KOMICHI_PLAYWRIGHT_TIMEOUT` | `45000` | 页面加载超时（毫秒） |
| `log_file` / `state_file` | `KOMICHI_LOG_FILE` / `KOMICHI_STATE_FILE` | `logs/*` | 日志 / 运行状态 |

优先级：环境变量 > `config.json` > 默认值。

## 部署

三选一（详见根目录 [DEPLOYMENT.md](../DEPLOYMENT.md)「VPS 爬虫节点」章节）：

- **systemd timer（推荐）**：`sudo bash deploy/install.sh` 一键安装 → `sudo systemctl enable --now komichi-crawler.timer`（每天 06:00 / 18:00）
- **cron**：`crontab deploy/crontab.example`（改路径）
- **Docker**：`docker compose up -d scheduler`（容器内 supercronic，适合无 root 平台）

平台要求：Linux + root + ≥2G 内存（Chromium 吃内存）；推荐阿里云轻量/ECS（x86_64）或 Oracle Cloud Always Free（ARM64 需 playwright ≥ 1.29）。

## 文件结构

```
crawler-daemon/
├── komichi_crawler/            # 共享爬虫运行时（CLI 与 daemon 共用）
│   ├── __init__.py             # 统一导出（类接口 + 模块接口 + WorkerAPI）
│   ├── __main__.py             # CLI 入口
│   ├── config.py               # 配置加载
│   ├── base.py                 # 数据模型 + 异常体系 + BaseCrawler + crawl_work 适配器
│   ├── _http.py                # 公共 HTTP 常量（UA / Headers / 状态词）
│   ├── registry.py             # 双接口源注册表 + URL 匹配 + 自动换备
│   ├── generic.py              # LocalCrawler（本地文件夹）/ UrlCrawler（URL 列表）
│   ├── guazi.py kuaikan.py tencent.py mh160mh.py   # 纯 HTTP 源
│   ├── godamh.py               # curl_cffi TLS 伪装
│   ├── bilibili.py             # Playwright 渲染
│   ├── worker_api.py           # Worker API 客户端（登录/列表/上传/更新）
│   ├── runner.py               # refresh/import/list 主逻辑
│   └── server.py               # HTTP 服务（Worker 搜索代理）
├── deploy/                     # install.sh + systemd service/timer + crontab 示例
├── Dockerfile / docker-compose.yml / .env.example / config.example.json
├── pyproject.toml              # 打包为 komichi-crawler（CLI 的安装依赖）
└── requirements.txt
```

## 扩展新源

在 `komichi_crawler/` 新建 `<source>.py`，**一个文件同时提供两种接口**（参考 `tencent.py`）：

1. **模块接口**（daemon 用）：`NAME` / `DOMAINS` / `HAS_SEARCH` / `is_supported(url)` / `crawl(url, timeout_ms)` / 可选 `search(keyword, timeout_ms)`
2. **类接口**（CLI 用）：同文件内 `@register_source class XxxCrawler(BaseCrawler)`，`crawl()` 调模块级 `crawl()`；异常统一用 `base.py` 的 `CrawlError/SourceNotFound/SourceUnavailable`，状态词用 `_http.STATUS_MAP`

然后在 `registry.py` 的 `DEFAULT_SOURCE_ORDER` 加入新源名即可（类注册自动登记对应模块）。无需改 runner、server 或 Worker。完整开发流程见根目录 [DEVELOPMENT.md](../DEVELOPMENT.md)。
