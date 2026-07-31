# Komichi

[![GitHub](https://img.shields.io/badge/GitHub-lilibushilicc%2FKomichi-181717?logo=github&style=flat-square)](https://github.com/lilibushilicc/Komichi)

Komichi 是一个基于 Cloudflare Serverless 的漫画阅读追踪系统。

## 功能

- **漫画管理** — 多源爬取导入，作品/章节/图片结构化存储
- **阅读追踪** — 跨设备同步阅读进度，书架管理
- **图片加速** — R2 对象存储 + 签名 URL，全球 CDN 分发
- **多端覆盖** — Android 客户端（Jetpack Compose）+ Web UI

## 架构

```
┌─────────────┐     HTTPS/JWT     ┌──────────────────┐
│  Android     │ ──────────────▶  │  Cloudflare      │
│  (Compose)   │                  │  Worker (Hono)   │
│             │ ◀──────────────── │                  │
│  Web UI     │                  │  D1 + R2         │
└─────────────┘                  └───────┬──────────┘
                                         ▲
┌─────────────────────────────────────────┘
│  CLI (Python)
│  爬取 ▶ 暂存 ▶ 上传 R2 ▶ 注册作品
└─────────────────────────────────────────
```

| 组件 | 技术栈 | 说明 |
|------|--------|------|
| `worker/` | TypeScript + Hono | 后端 API，D1 数据库 + R2 存储 |
| `cli/` | Python + Click | 爬虫管理、漫画导入、图片上传 |
| `android/` | Kotlin + Jetpack Compose | Android 客户端 |
| `komichi-ui/` | HTML + CSS | 网页端界面（可选） |

## 快速开始

```bash
# 1. 部署后端
cd worker
npm install
npx wrangler d1 create komichi
npx wrangler r2 bucket create komichi-images
# 编辑 wrangler.toml 填入 database_id
npx wrangler d1 execute komichi --file=./schema.sql --remote
npx wrangler d1 execute komichi --file=./init.sql --remote
npx wrangler deploy

# 2. 安装 CLI
cd cli
pip install -e .
komichi-cli init

# 3. Android → 用 Android Studio 打开 android/ 目录编译运行
```

详见 [USAGE.md](USAGE.md) 完整部署和使用说明。

## 技术栈

| 组件 | 版本 |
|------|------|
| AGP | 8.7.3 |
| Kotlin | 2.0.0 |
| Compose BOM | 2024.06.00 |
| Hilt | 2.52 |
| Worker | Hono 4.6 + Wrangler 4.x |
| Python | ≥ 3.9 |
