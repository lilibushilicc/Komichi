# Komichi

[![GitHub](https://img.shields.io/badge/GitHub-lilibushilicc%2FKomichi-181717?logo=github&style=flat-square)](https://github.com/lilibushilicc/Komichi)

Komichi 是一个漫画阅读追踪系统，采用 **Worker + VPS 爬虫** 架构：核心服务（API + 数据库 + 图片存储）跑在 Cloudflare Worker 上，需要浏览器渲染或 TLS 伪装的爬虫源由 VPS 爬虫节点处理，VPS 抓到数据后通过 Worker API 回写，**VPS 依赖 Worker、不可脱离 Worker 独立运行**。

## 功能

- **漫画管理** — 多源爬取导入，作品/章节/图片结构化存储
- **阅读追踪** — 跨设备同步阅读进度，书架管理
- **图片加速** — R2 对象存储 + 签名 URL，全球 CDN 分发
- **多端覆盖** — Android 客户端（Jetpack Compose）+ Windows 桌面客户端（WPF）+ Web UI
- **Worker + VPS 爬虫** — Worker 是核心服务可单独运行；VPS 是可选的爬虫增强节点，依赖 Worker 存储

## 架构：Worker + VPS 爬虫

```
┌─────────────────────────────────┐       ┌─────────────────────────────┐
│  Worker · Cloudflare (核心)      │       │  VPS · 爬虫节点 (可选)        │
│                                  │       │                              │
│  Worker (Hono) + D1 + R2         │ ◀──── │  crawler-daemon              │
│  ├ 4 源 cron 自动追更 (HTTP)      │ HTTPS │  ├ Playwright + Chromium     │
│  ├ komichi-ui / android / cli    │ +JWT  │  ├ bilibili 源 (浏览器渲染)   │
│  └ 全部数据存储 + API 服务        │       │  └ cron / systemd 定时       │
│                                  │       │                              │
│  可单独运行, 不依赖 VPS           │       │  依赖 Worker, 不存任何数据     │
│  部署: wrangler deploy           │       │  部署: install.sh / Docker   │
└─────────────────────────────────┘       └─────────────────────────────┘
```

**Worker 是核心，VPS 是辅助爬虫节点**：Worker 包含全部数据存储（D1）和 API 服务，可单独部署运行；VPS 只负责跑 Worker 跑不了的爬虫源（bilibili 浏览器渲染、godamh TLS 伪装），抓到数据后通过 Worker API 回写到 D1 + R2，本身不存任何数据库，**不能脱离 Worker 独立工作**。CLI、安卓端、Web UI 全部只连 Worker API，VPS 对客户端完全透明。

### 为什么需要 VPS 爬虫节点

| 源 | 抓取方式 | Worker 能跑 | VPS 能跑 | 归属 |
|----|----------|:----------:|:--------:|:----:|
| mh160mh / tencent / guazi / kuaikan | 纯 HTTP | 能 | **能** | Worker 或 VPS |
| **bilibili** | Playwright 浏览器渲染 | **不能** | 能 | **仅 VPS** |
| **godamh** | TLS 指纹伪装 (curl_cffi) | **不能** | 能 | **仅 VPS** |

**VPS 是 Worker 爬虫的超集**：6 源全支持 + 关键词搜索；Worker 只支持 4 个 HTTP 源。只部署 Worker 可用 4 源；加部署 VPS 获得全 6 源 + 搜索。Worker 跑不了 Chromium/TLS 伪装，所以 bilibili/godamh 只能 VPS 爬。VPS 抓到的数据全部回写 Worker，不本地存储。

## Worker · Cloudflare（核心服务）

核心服务，包含后端 API、数据存储和所有客户端。**必须部署**，可单独运行。

| 组件 | 技术栈 | 说明 |
|------|--------|------|
| `worker/` | TypeScript + Hono | 后端 API，D1 + R2，cron 刷新 4 源，支持 `POST /api/work/import` 服务器端导入 |
| `cli/` | Python + Click | 爬虫管理、漫画导入、图片上传（本地运行，可选；爬虫实现与 crawler-daemon 共用 `komichi_crawler`） |
| `android/` | Kotlin + Jetpack Compose | Android 客户端 |
| `windows/` | C# + WPF (.NET 8) | Windows 桌面客户端 |
| `komichi-ui/` | HTML + CSS | 网页端界面（可选） |

部署：
```bash
cd worker
npm install
npx wrangler d1 create komichi
npx wrangler r2 bucket create komichi-images
# 编辑 wrangler.toml 填入 database_id
npx wrangler d1 execute komichi --file=./schema.sql --remote
npx wrangler d1 execute komichi --file=./init.sql --remote
npx wrangler deploy
```

部署后可用 `curl` 直接导入 4 源作品，**不用本地电脑跑 CLI**（见 DEPLOYMENT.md "服务器端导入"）。

**完整部署步骤见 [DEPLOYMENT.md](DEPLOYMENT.md)。** 综合使用手册见 [USAGE.md](USAGE.md)。

## VPS · crawler-daemon（可选爬虫节点）

部署在能跑 Chromium 的 Linux VPS 上（阿里云轻量/ECS、Oracle Cloud 等），**是 Worker 爬虫的超集**：全 6 源支持 + 关键词搜索，Worker 能做的它都能做。**依赖 Worker API 存储，不可脱离 Worker 独立运行。**

| 组件 | 技术栈 | 说明 |
|------|--------|------|
| `crawler-daemon/` | Python + Playwright/curl_cffi/httpx | 全 6 源爬虫（bilibili/godamh/mh160mh/tencent/guazi/kuaikan）+ 搜索，通过 Worker API 回写；与 CLI 共用同一 `komichi_crawler` 包 |

工作模式：
```bash
python -m komichi_crawler refresh              # 追更所有 VPS 源作品（cron 调用）
python -m komichi_crawler import <url>         # 导入新作品（自动识别全 6 源）
python -m komichi_crawler search <关键词>      # 搜索 bilibili/godamh 找新作品
python -m komichi_crawler list                 # 列出 Worker 上的 VPS 源作品
python -m komichi_crawler sources              # 列出支持的源
```

**完整部署步骤见 [DEPLOYMENT.md](DEPLOYMENT.md)（VPS 章节）。** 模块技术细节（架构/数据流/扩展新源）见 [crawler-daemon/README.md](crawler-daemon/README.md)。

> 注意：VPS 不是必需的。如果不用 bilibili/godamh 源，只部署 Worker 即可完整使用其他 4 个源 + 阅读功能。Worker 和 VPS 都支持服务器端导入，本地电脑完全不用动。但 VPS 必须配合 Worker 使用，不能替代 Worker。

## 技术栈

| 组件 | 版本 |
|------|------|
| AGP | 8.7.3 |
| Kotlin | 2.0.0 |
| Compose BOM | 2024.06.00 |
| Hilt | 2.52 |
| Worker | Hono 4.6 + Wrangler 4.x |
| Python | ≥ 3.9 |
| Playwright | ≥ 1.29 (VPS 爬虫节点) |
