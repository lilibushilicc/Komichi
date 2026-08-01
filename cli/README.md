# Komichi CLI

基于 Cloudflare Serverless 架构的私有化漫画追更管理系统的命令行工具，负责重型任务：新增作品导入、首次章节抓取、图片上传、数据初始化。运行于 Windows / Linux / macOS。

爬虫实现与 API 客户端**共用** `crawler-daemon/komichi_crawler/` 包（单一事实来源）：仓库开发环境自动复用该目录源码，本目录下 `crawler/` 与 `api/client.py` 只是兼容层（再导出 + 注入 CLI 配置）。**新增/修改爬虫请到 `crawler-daemon/komichi_crawler/`**。

## 技术栈

Python 3.9+ · click · httpx · rich · `komichi-crawler`（共享包，正式安装时为 PyPI 依赖）

## 安装

```bash
pip install -r requirements.txt
pip install -e .
# 注册命令 komichi-cli；也可 python -m komichi_cli.main
```

## 配置

`~/.komichi/config.json`（首次 `komichi-cli init` 自动创建）：

| 键 | 说明 | 默认值 |
| --- | --- | --- |
| `worker_url` | Cloudflare Worker 地址 | `""` |
| `username` / `password` | 登录账号（CRAWLER 角色） | `""` |
| `token` | 登录 Token（自动维护，过期自动重登） | `""` |
| `upload_path` | 图片上传端点 | `/api/r2/upload` |
| `request_timeout` / `max_retries` | 请求超时（秒）/ 重试次数 | `30` / `3` |
| `source_priority` | 关键词导入的源换备顺序 | `["godamh","mh160mh","guazi","kuaikan","tencent","bilibili"]` |

> 本地暂存数据位于 `~/.komichi/staging/<slug>/work.json`。

## 命令一览

```
komichi-cli init                        初始化配置（Worker 地址、账号）
komichi-cli config show|get|set         配置管理
komichi-cli source list                 列出可用源（8 个：local/url + 6 站点源）
komichi-cli import <URL|关键词>         自动导入：URL 按域名识别源 / 关键词按优先级换备
komichi-cli import from <src> <query>   指定源导入（godamh/mh160mh/guazi/kuaikan/tencent/bilibili）
komichi-cli import local <path>         从本地文件夹导入（章节=子文件夹）
komichi-cli import url <url|file>       从 URL 列表 / JSON manifest 导入
komichi-cli upload images <dir> --work-id <id>   上传封面到 R2
komichi-cli sync work <slug>            一键同步（创建作品 + 上传图片 + 回传路径）
komichi-cli sync all                    同步所有本地暂存
komichi-cli list works|staging          列出 Worker 作品 / 本地暂存
komichi-cli check <work_id>             检查更新状态
```

### 多源导入与自动换备

```bash
# URL 自动识别源
komichi-cli import https://www.mh160mh.com/kanmanhua/94/
# 关键词自动换备：按 source_priority 顺序逐个源搜索，预览确认（yes/no），no 则换下一源
komichi-cli import 海贼王 --yes          # 非交互/脚本环境跳过确认
# 显式指定源
komichi-cli import from tencent 斗罗大陆
# 调整换备顺序
komichi-cli config set source_priority mh160mh,godamh,guazi,kuaikan,tencent,bilibili
```

> 说明：mh160mh 站内搜索已关闭、guazi/kuaikan 无站内搜索，这三源仅支持 URL 导入（关键词导入会自动换备）；bilibili 源需 Playwright（`pip install playwright` + `python -m playwright install chromium`），未装时自动换备。

### 典型工作流

```bash
komichi-cli init
komichi-cli import local "D:/comics/某漫画" --category "动作"
komichi-cli sync work 某漫画      # 创建作品 + 上传图片一步完成
komichi-cli list works
```

## 后端 API 契约

统一响应：`{"code":200,"msg":"success","data":{}}`。CLI 使用 CRAWLER 权限 Token。

| 方法 | 端点 | 说明 |
| ---- | ---- | ---- |
| POST | `/api/auth/login` | 登录获取 token |
| POST | `/api/work/update` | 新增/更新作品与章节（扁平格式 `{title, ..., chapters:[]}`；也兼容 `{work, chapters}` 包装） |
| GET | `/api/work/list?page=&size=` | 查询作品（自动翻页） |
| GET | `/api/work/{id}` | 作品详情 |
| POST | `/api/r2/upload` | 图片上传（multipart: `file` + `key`，响应含 `r2_path`） |

`work.id` 为空视为新增，响应 `data` 返回新 ID；`chapters[].images` 可为空（首次建记录阶段）。

## 项目结构

```
cli/
├── komichi_cli/
│   ├── __init__.py       # sys.path 引导：开发环境复用 crawler-daemon/ 源码
│   ├── main.py           # 入口，注册各命令组
│   ├── config.py         # ~/.komichi/config.json + 本地暂存管理
│   ├── theme.py / utils.py / display.py / staging.py / groups.py
│   ├── api/client.py     # 兼容层：复用共享 WorkerAPI（komichi_crawler.worker_api）
│   ├── crawler/__init__.py   # 兼容层：从共享 komichi_crawler 再导出 + 注入 source_priority
│   ├── uploader/r2_uploader.py  # 薄封装（本地直传 / 远程 URL 下载后上传）
│   └── commands/         # config_cmd / import_cmd / source_cmd / upload_cmd / sync_cmd / update_cmd / list_cmd
├── setup.py              # 依赖 komichi-crawler>=1.1
└── README.md
```

错误处理：网络错误指数退避重试（`max_retries`）；Token 失效（401）自动重登；中文路径全程 UTF-8 兼容 Windows。
