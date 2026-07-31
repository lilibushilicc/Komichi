# Komichi CLI

基于 Cloudflare Serverless 架构的私有化漫画追更管理系统的命令行工具。

CLI 负责重型任务：新增作品导入、首次章节抓取、图片下载、R2 上传、数据初始化。一次执行完成后关闭，运行于 Windows / Linux / macOS。

## 技术栈

- Python 3.9+
- [click](https://click.palletsprojects.com/) - 命令行框架
- [httpx](https://www.python-httpx.org/) - HTTP 客户端
- [rich](https://rich.readthedocs.io/) - 终端美化（进度条、表格、面板）
- `pathlib` - 路径处理（标准库）

## 安装

在 `cli/` 目录下执行：

```bash
pip install -r requirements.txt
pip install -e .
```

安装后会注册命令 `komichi-cli`。也可通过 `python -m komichi_cli.main` 调用。

验证安装：

```bash
komichi-cli --version
komichi-cli --help
```

## 配置

配置文件位于 `~/.komichi/config.json`（首次运行 `init` 时自动创建）。

| 键                  | 说明                                       | 默认值        |
| ------------------- | ------------------------------------------ | ------------- |
| `worker_url`        | Cloudflare Worker 地址                     | `""`          |
| `username`          | 登录用户名                                 | `""`          |
| `password`          | 登录密码                                   | `""`          |
| `token`             | 登录 Token（自动维护，过期自动重登）       | `""`          |
| `upload_path`       | 图片上传端点（通过 Worker 转存到 R2）      | `/api/r2/upload` |
| `upload_concurrency`| 上传并发数（预留）                         | `4`           |
| `request_timeout`   | 单次请求超时（秒）                         | `30`          |
| `max_retries`       | 网络错误最大重试次数                       | `3`           |
| `source_priority`   | 站点源优先级（关键词导入时按序自动换备）   | `["godamh", "mh160mh", "guazi", "kuaikan", "tencent", "bilibili"]` |

> 本地暂存数据位于 `~/.komichi/staging/<slug>/work.json`，用于保存已导入但尚未/已经同步到 Worker 的作品数据。

## 命令一览

```
komichi-cli init                       初始化配置（设置 Worker 地址、用户名、密码）
komichi-cli config show                显示当前配置
komichi-cli config set <key> <value>   设置配置项

komichi-cli source list                列出所有可用爬虫源

komichi-cli import local <path>        从本地文件夹导入漫画
komichi-cli import url <work_url>      从 URL 导入漫画（预留接口框架）
komichi-cli import from <src> <query>  从指定源导入（src: godamh / mh160mh / guazi / kuaikan / tencent / bilibili / ...）
komichi-cli import <url|keyword>       自动导入：URL 按域名识别源，关键词按优先级换备

komichi-cli upload images <work_dir>   上传指定作品的图片到 R2
komichi-cli sync work <work_id>        同步作品数据到 Worker
komichi-cli sync all                   同步所有本地数据

komichi-cli list works                 列出 Worker 上的所有作品
komichi-cli check <work_id>            检查作品更新状态
```

### init - 初始化

```bash
komichi-cli init
# 交互式输入 Worker 地址、用户名、密码，并尝试登录验证
```

### config - 配置管理

```bash
komichi-cli config show
komichi-cli config set worker_url https://komichi.example.workers.dev
komichi-cli config set max_retries 5
```

### import local - 本地文件夹导入

期望的文件夹结构（章节按子文件夹组织，文件名自然排序）：

```
漫画标题/
  cover.jpg            # 可选，根目录下的封面图片
  第一章/
    001.jpg
    002.jpg
  第二章/
    001.jpg
```

```bash
komichi-cli import local "D:/comics/某漫画" --title "某漫画" --category "动作" --cover "D:/comics/某漫画/cover.jpg"
```

- 标题缺省时取文件夹名；封面缺省时自动取根目录第一张图片。
- 章节号优先从子文件夹名中解析数字，无法解析则按顺序自增。
- 导入结果保存到本地暂存，输出暂存 `slug` 供后续命令使用。

### 多源导入与自动换备

可用源通过 `komichi-cli source list` 查看（当前内置：`godamh`、`mh160mh`、`guazi`、`kuaikan`、`tencent`、`bilibili`，另有 `local`/`url` 两个非站点源）。

```bash
# 1. URL 自动识别源（无需指定源名）
komichi-cli import https://www.mh160mh.com/kanmanhua/94/
komichi-cli import https://godamh.com/manga/xxx
komichi-cli import https://www.guazimanhua.com/comic.php?id=33993
komichi-cli import https://www.kuaikanmanhua.com/web/comic/847609
komichi-cli import https://ac.qq.com/Comic/comicInfo/id/505430
komichi-cli import https://manga.bilibili.com/detail/mc24742

# 2. 关键词自动换备：按配置 source_priority 顺序逐个尝试，
#    某个源找到结果后先展示预览并询问「是不是这个作品？」（yes/no），
#    确认后爬取；回答 no 则自动换下一个源；全部失败才报错
komichi-cli import 海贼王

# 非交互环境（管道/脚本）自动跳过确认；也可用 --yes 强制跳过：
komichi-cli import 海贼王 --yes

# 3. 显式指定源
komichi-cli import from godamh 海贼王
komichi-cli import from mh160mh https://www.mh160mh.com/kanmanhua/94/ --category 热血
komichi-cli import from tencent 斗罗大陆
komichi-cli import from bilibili 海贼王

# 4. 调整源优先级（关键词换备顺序）
komichi-cli config set source_priority mh160mh,godamh,guazi,kuaikan,tencent,bilibili
```

> 说明：mh160mh.com 站内搜索已关闭（搜索端点 404），guazimanhua.com 与 kuaikanmanhua.com
> 未提供可用站内搜索，这三个源仅支持 URL 导入；用关键词导入时会自动提示改用 URL，
> 并触发换备尝试下一个源。
> bilibili 源基于 Playwright（无头浏览器）抓取——因其数据接口带 JS/WASM 签名与加密，
> 纯 HTTP 无法访问。首次使用需安装：`pip install playwright` 与
> `python -m playwright install chromium`，未安装时该源会提示换备到其他源。
> 新增源只需在 `crawler/` 下实现 `BaseCrawler` 子类（声明 `name`/`domains`）并用
> `@register_source` 注册，再把它加进 `source_priority` 即可，无需改动其他代码。

### import url - URL 导入（预留接口框架）

支持三种来源：

1. 本地 `.txt` 文件：每行一个图片 URL，整体作为单章节。
2. 本地 `.json` 文件：manifest 格式。
3. `http(s)` 链接：指向上述 `.txt` / `.json` 资源。

manifest JSON 格式：

```json
{
  "title": "作品标题",
  "cover": "https://example.com/cover.jpg",
  "chapters": [
    { "title": "第1章", "chapter_num": 1, "images": ["https://...", "https://..."] },
    { "title": "第2章", "chapter_num": 2, "images": ["https://..."] }
  ]
}
```

```bash
komichi-cli import url https://example.com/manifest.json --title "某漫画"
```

> 其它漫画站点的页面解析逻辑需继承 `UrlCrawler` 并实现 `crawl()`。

### upload images - 上传图片到 R2

```bash
komichi-cli upload images <slug> --work-id 12
komichi-cli upload images <slug> --work-id 12 --chapter 2     # 只上传第 2 章
```

`work_dir` 可传：本地暂存 `slug`、暂存目录路径或数字作品 ID。上传后 R2 路径回填到本地暂存。

### sync work / sync all - 同步到 Worker

```bash
komichi-cli sync work <slug>            # 自动创建/更新作品并上传图片
komichi-cli sync work 12 --skip-upload  # 仅同步元数据，不上传图片
komichi-cli sync all                    # 同步所有本地暂存作品
```

`sync work` 的完整流程（三阶段，全自动）：

1. **创建/获取作品记录**：若本地暂存无 `work_id`，先调用 `POST /api/work/update`（不含图片）创建作品，保存返回的远程 ID。
2. **上传图片**：将尚未上传的封面与章节图片通过 Worker 上传到 R2，路径回填本地暂存。
3. **回传图片路径**：再次调用 `POST /api/work/update`，提交完整的作品/章节/图片路径信息。

> 因此推荐工作流：`import` -> `sync work <slug>` 一步完成创建与上传。`--skip-upload` 用于仅更新元数据（如修改标题/分类）。

### list works - 列出作品

```bash
komichi-cli list works
```

### check - 检查更新状态

```bash
komichi-cli check 12
```

对比本地暂存与 Worker 远程数据，显示待同步的新章节。

## 典型工作流

```bash
# 1. 初始化
komichi-cli init

# 2. 导入本地漫画
komichi-cli import local "D:/comics/某漫画" --category "动作"

# 3. 一键同步（创建作品 + 上传图片 + 回传路径）
komichi-cli sync work 某漫画

# 4. 查看与检查
komichi-cli list works
komichi-cli check 1

# 后续追更：把新章节图片放入对应文件夹后再次 import + sync 即可
```

## 后端 API 契约

CLI 通过 Cloudflare Worker API 操作，使用 CRAWLER 权限 Token。统一响应格式：

```json
{ "code": 200, "msg": "success", "data": {} }
```

| 方法 | 端点                 | 说明                                   |
| ---- | -------------------- | -------------------------------------- |
| POST | `/api/auth/login`    | 登录获取 token（用户名 + 密码）         |
| POST | `/api/work/update`   | 新增/更新作品和章节数据                 |
| GET  | `/api/work/list`     | 查询已有作品                           |
| GET  | `/api/work/{id}`     | 查询作品详情                           |
| POST | `/api/r2/upload`     | 图片上传（multipart，转存到 R2）        |

### POST /api/work/update 请求体

```json
{
  "work": {
    "id": 12,
    "title": "某漫画",
    "category": "动作",
    "description": "作品简介",
    "cover_r2_path": "komichi/covers/12.jpg",
    "source": "mh160mh",
    "source_url": "https://www.mh160mh.com/kanmanhua/94/",
    "latest_chapter_num": 2,
    "status": "ongoing"
  },
  "chapters": [
    {
      "work_id": 12,
      "chapter_num": 1,
      "chapter_title": "第一章",
      "images": [
        { "image_index": 0, "r2_path": "komichi/chapters/12/1/0000.jpg" },
        { "image_index": 1, "r2_path": "komichi/chapters/12/1/0001.jpg" }
      ]
    }
  ]
}
```

- `work.id` 为空时视为新增，Worker 应在 `data` 中返回新 ID（`id` / `work_id` / `workId` 任一均可）。
- `chapters[].images` 可为空数组（首次创建作品记录阶段）。

### POST /api/r2/upload 请求体

`multipart/form-data`：

- `file`：图片二进制
- `key`：目标 R2 对象键，如 `komichi/chapters/12/1/0000.jpg`

响应 `data` 应包含 `r2_path` 字段表示最终 R2 路径。

> 若 Worker 端上传端点路径不同，可通过 `komichi-cli config set upload_path /your/upload/endpoint` 调整。

## R2 存储结构

```
komichi/
  covers/                                   # 作品封面  covers/<work_id>.<ext>
  chapters/<work_id>/<chapter_num>/<index:04d>.<ext>   # 章节图片
  backup/                                   # 备份文件
```

## 数据库结构（Worker 侧）

- `works`: id, title, category, description, cover_r2_path, source_url, latest_chapter_num, status, create_time
- `chapters`: id, work_id, chapter_num, chapter_title, create_time
- `chapter_images`: id, chapter_id, image_index, r2_path

> 升级已有数据库：`npx wrangler d1 execute komichi --file=./migrations/003_add_work_description.sql`

## 项目结构

```
cli/
├── komichi_cli/
│   ├── __init__.py
│   ├── main.py           # CLI 入口，定义所有命令
│   ├── config.py         # 配置管理 + 本地暂存管理
│   ├── api/
│   │   ├── __init__.py
│   │   └── client.py     # API 客户端，封装所有 HTTP 请求
│   ├── crawler/
│   │   ├── __init__.py
│   │   ├── base.py       # 爬虫基类（接口定义）与数据模型 / 异常体系
│   │   ├── registry.py   # 源注册表 + URL 域名匹配 + 多源自动换备
│   │   ├── generic.py    # 通用爬虫（本地文件夹 / URL 列表）
│   │   ├── godamh.py     # godamh.com 站点爬虫
│   │   ├── mh160mh.py    # 漫画160 (mh160mh.com) 站点爬虫
│   │   ├── guazi.py      # 瓜子漫画 (guazimanhua.com) 站点爬虫
│   │   ├── kuaikan.py    # 快看漫画 (kuaikanmanhua.com) 站点爬虫
│   │   ├── tencent.py    # 腾讯动漫 (ac.qq.com) 站点爬虫
│   │   └── bilibili.py   # 哔哩哔哩漫画 (manga.bilibili.com) 站点爬虫（Playwright）
│   └── uploader/
│       ├── __init__.py
│       └── r2_uploader.py # R2 上传器（通过 Worker API 上传）
├── requirements.txt
├── setup.py
└── README.md
```

## 错误处理与重试

- 网络错误（超时、连接失败）采用指数退避重试，最大次数由 `max_retries` 控制。
- Token 失效（HTTP 401 或业务 code 401/403）自动清除并重新登录后重试。
- 文件上传重试时会重置文件指针，保证数据完整。
- 中文路径全程使用 UTF-8 与 `pathlib` 处理，兼容 Windows。
