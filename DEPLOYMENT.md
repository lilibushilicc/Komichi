# 部署指南 · Komichi

Komichi 采用 **Worker + VPS 爬虫** 双架构：

- **Cloudflare Worker（核心服务，必部署）**：API + D1 数据库 + R2 图片存储，自带 cron 追更 6 个纯 HTTP 源，可单独运行。
- **VPS 爬虫节点（可选）**：crawler-daemon，全 6 源支持 + 关键词搜索（Worker 爬虫的超集），数据全部回写 Worker，**依赖 Worker、不可脱离运行**。

> 只部署 Worker 即可完整使用（6 源 + 阅读功能）；要 bilibili / godamh 源才需要加 VPS。

## 源支持一览

| 源 | 抓取方式 | Worker | VPS |
|----|----------|:------:|:---:|
| mh160mh | 纯 HTTP | ✅ | ✅ |
| tencent | 纯 HTTP | ✅ | ✅ |
| guazi | 纯 HTTP | ✅ | ✅ |
| kuaikan | 纯 HTTP | ✅ | ✅ |
| dongmanmanhua | 纯 HTTP | ✅ | ✅ |
| sfacg | 纯 HTTP | ✅ | ✅ |
| **bilibili** | Playwright 浏览器渲染 | ❌ | ✅ |
| **godamh** | TLS 指纹伪装 (curl_cffi) | ❌ | ✅ |

Worker cron 每 6 小时刷新 6 个 HTTP 源（mh160mh / tencent / guazi / kuaikan / dongmanmanhua / sfacg）；VPS cron（每天 06:00 / 18:00）刷新 bilibili + godamh，两边互不冲突。部署 VPS 后也可关掉 Worker 的爬虫 cron，由 VPS 统一爬。

---

## 一、Cloudflare Worker（核心服务）

### 前置要求

| 组件 | 要求 |
|------|------|
| Node.js | ≥ 18 |
| Cloudflare 账号 | 免费版即可 |
| wrangler | `npm install -g wrangler` 或用 npx |

### 部署步骤

```bash
cd worker
npm install

# 1. 创建云资源
npx wrangler d1 create komichi        # 输出 database_id，记下来
npx wrangler r2 bucket create komichi-images

# 2. 编辑 worker/wrangler.toml，把 database_id 替换为上一步的值

# 3. 初始化数据库（建表 + 默认账号 admin/admin123, crawler/crawler123）
npx wrangler d1 execute komichi --file=./schema.sql --remote
npx wrangler d1 execute komichi --file=./init.sql --remote

# 4. 部署
npx wrangler deploy
```

> ⚠️ 部署后立即修改默认密码。未跑 init.sql 时可 `curl -X POST <worker>/api/auth/init` 初始化管理员。

### 验证

```bash
curl https://<worker>.workers.dev/ping
# {"code":200,"msg":"success","data":{"ping":"pong","service":"komichi-worker",...}}
```

### cron 自动追更

`wrangler.toml` 的 `crons = ["0 */6 * * *"]` 让 Worker 每 6 小时刷新所有能匹配到 Worker 爬虫的作品（mh160mh/tencent/guazi/kuaikan），bilibili 源自动跳过。可手动触发：`curl -H "Authorization: Bearer <token>" <worker>/api/work/refresh-all`。

### 服务器端导入（不用本地 CLI）

```bash
TOKEN=$(curl -s -X POST <worker>/api/auth/login -H "Content-Type: application/json" \
  -d '{"username":"crawler","password":"crawler123"}' | jq -r .data.token)

curl -X POST <worker>/api/work/import -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_url":"https://www.mh160mh.com/kanmanhua/94/"}'
```

支持的 URL 示例：`mh160mh.com/kanmanhua/94/`、`ac.qq.com/Comic/comicInfo/id/505430`、`guazimanhua.com/comic.php?id=33993`、`kuaikanmanhua.com/web/comic/847609`。bilibili / godamh 的 URL 会返回 400，需走 VPS。

### 可选：Web UI / Android / CLI

- **Web UI**：`komichi-ui/` 纯静态，`npx wrangler pages deploy komichi-ui --project-name komichi-ui`，或本地 `python -m http.server 8080` 预览。
- **Android**：Android Studio 打开 `android/`，Gradle Sync 后 Build APK；首次打开在设置页填入 Worker URL。
- **CLI**：本地导入工具，`pip install -e cli/` 后 `komichi-cli init` 配置 Worker 地址与账号（详见 [cli/README.md](cli/README.md)）。

### 本地开发

```bash
cd worker && npx wrangler dev   # http://localhost:8787
```

### Worker 限制

1. **跑不了 Chromium** → bilibili 源无法在 Worker 抓取
2. **无 TLS 指纹伪装** → godamh 源无法在 Worker 抓取
3. **CPU 时间限制** → 免费版单次请求 10ms CPU，复杂解析需注意
4. **D1 写入限制** → 免费版每天 100K 行写入，大批量导入建议分批

---

## 二、VPS 爬虫节点（crawler-daemon，可选）

### 前置要求

| 组件 | 要求 |
|------|------|
| 操作系统 | Linux（Ubuntu 22.04 LTS 推荐） |
| 权限 / 内存 | root 或免密 sudo；≥ 2G（Chromium 吃内存，1G 需加 swap） |
| Python | ≥ 3.9 |
| Worker | 已部署，有 CRAWLER 角色账号（默认 crawler/crawler123） |

平台推荐：**阿里云轻量/ECS**（x86_64，到 bilibili 网络稳定）★★★★★；Oracle Cloud Always Free ARM ★★★★（需 playwright ≥ 1.29）；任意 Linux VPS ★★★★。❌ AlwaysData 等共享主机（无 root，装不了 Chromium 系统库）。

### 部署方式（三选一）

**方式 A：systemd timer（推荐）**

```bash
scp -r crawler-daemon/ root@your-server:/opt/
ssh root@your-server
cd /opt/crawler-daemon
sudo bash deploy/install.sh        # 自动装 venv + 依赖 + Chromium + systemd

# 配置凭据（二选一）：
nano /opt/komichi-crawler/crawler.env     # KOMICHI_WORKER_URL / KOMICHI_USERNAME / KOMICHI_PASSWORD
# 或 nano /opt/komichi-crawler/config.json

sudo systemctl enable --now komichi-crawler.timer
systemctl list-timers | grep komichi      # 每天 06:00 / 18:00 各跑一次
journalctl -u komichi-crawler -f
```

**方式 B：cron（最简单）** — 装好依赖后 `crontab /opt/komichi-crawler/deploy/crontab.example`（改路径）。

**方式 C：Docker（无 root / 容器平台）**

```bash
cd crawler-daemon
cp .env.example .env && # 编辑 .env 填入凭据
docker compose build
docker compose up -d scheduler            # 容器内 supercronic 定时
docker compose logs -f scheduler
```

### 配置

必填三项（环境变量 > `config.json` > 默认值）：`KOMICHI_WORKER_URL`（Worker 地址）、`KOMICHI_USERNAME` / `KOMICHI_PASSWORD`（CRAWLER 角色）。完整配置项见 [crawler-daemon/README.md](crawler-daemon/README.md)。

### 验证与使用

```bash
python -m komichi_crawler check-playwright    # Chromium 就绪？
python -m komichi_crawler sources             # 全 6 源
python -m komichi_crawler search 海贼王 --import-first   # 搜索并导入
python -m komichi_crawler import "https://manga.bilibili.com/detail/mc24742"
python -m komichi_crawler list                # Worker 上的 VPS 源作品
```

| 命令 | 作用 | 触发 |
|------|------|------|
| `refresh` | 扫描 D1 中 VPS 源作品，爬最新章节回写，缺封面上传 R2 | cron / systemd |
| `import <url>` | 任意源 URL（自动识别）注册新作品 | 手动 |
| `search <关键词>` | 搜索 bilibili/godamh，`--import-first` 直接导入 | 手动 |
| `serve` | HTTP 服务（Worker 搜索代理转发目标） | 常驻 |
| `list` / `sources` | 查看作品 / 源列表 | 手动 |

### VPS 限制

1. 需要浏览器 → bilibili 必须 Playwright（6 个纯 HTTP 源不需要）
2. 吃内存 → Chromium 单实例约 300-500MB，建议 2G 起
3. 搜索仅 2 源 → 只有 bilibili/godamh 支持站内搜索
4. 风控 → 定时策略已错开（每天 2 次），高频可能被 bilibili 拦截

### 阿里云注意事项

- 安全组：出站放行 443，入站无需开端口
- 实例规格：最低 2C2G；1G 内存需加 2G swap
- 系统镜像：Ubuntu 22.04 LTS；ARM 实例需 playwright ≥ 1.29

---

## 常见问题

| 现象 | 处理 |
|------|------|
| Worker 返回 500 | 检查 `wrangler.toml` 的 `database_id` / `bucket_name`、确认 `schema.sql` 已执行、看 Cloudflare Dashboard 日志 |
| cron 没生效 | `[triggers] crons` 需重新 `wrangler deploy`；Dashboard → Triggers 确认已注册 |
| VPS 报 401/403 | 账号不是 CRAWLER 角色；Worker 端未初始化账号（跑 `init.sql` 或 `POST /api/auth/init`） |
| `check-playwright` 失败 | `python -m playwright install chromium` + `sudo python -m playwright install-deps chromium`；共享主机装不了就换平台 |
| 爬取报「作品页不存在」 | bilibili 改版检查 `crawler-daemon/komichi_crawler/bilibili.py` 选择器；IP 被风控换 IP；超时调大 `KOMICHI_PLAYWRIGHT_TIMEOUT` |
| 追更没发现新章节 | bilibili 章节分页，`PAGINATE_JS` 自动加载；200+ 章可能超时，调大 timeout |
| Android 图片不显示 | 设置页 Worker URL 是否正确；`curl <url>/ping`；看 Logcat 签名 URL 日志 |
| 日志在哪 | VPS systemd：`journalctl -u komichi-crawler -f`；cron/docker：`logs/crawler.log`；运行状态：`logs/state.json` |
