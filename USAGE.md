# Komichi 使用与构建手册

---

## 目录

- [前置要求](#前置要求)
- [Worker 后端部署](#worker-后端部署)
- [CLI 工具使用](#cli-工具使用)
- [Android 客户端编译](#android-客户端编译)
- [API 接口文档](#api-接口文档)
- [项目约定](#项目约定)
- [常见问题](#常见问题)

---

## 前置要求

| 组件 | 要求 |
|------|------|
| Node.js | ≥ 18 |
| Python | ≥ 3.9 |
| Android Studio | Hedgehog+ |
| JDK | 17 |
| Cloudflare | 账号（免费版即可） |

---

## Worker 后端部署

### 1. 创建云资源

```bash
cd worker

# D1 数据库
npx wrangler d1 create komichi
# 输出示例：
# ✅ Successfully created DB 'komichi'
# database_id = "0510471d-bb41-4c64-b4f1-3bf589b85b97"

# R2 存储桶（免费额度：10GB 存储 + 100 万次读取/月）
npx wrangler r2 bucket create komichi-images
```

### 2. 配置 wrangler.toml

编辑 `worker/wrangler.toml`，填入上一步获取的 `database_id`：

```toml
[[d1_databases]]
binding = "DB"
database_name = "komichi"
database_id = "0510471d-bb41-4c64-b4f1-3bf589b85b97"   # ← 替换为你创建的

[[r2_buckets]]
binding = "BUCKET"
bucket_name = "komichi-images"
```

### 3. 初始化数据库

```bash
# 建表（--remote 写入远程库，不加则仅写入本地缓存）
npx wrangler d1 execute komichi --file=./schema.sql --remote

# 导入默认账号（可选，admin/admin123 + crawler/crawler123）
npx wrangler d1 execute komichi --file=./init.sql --remote
```

### 4. 部署

```bash
npm install
npx wrangler deploy
```

验证：

```bash
curl https://komichi-worker.xxx.workers.dev/ping
# {"code":200,"msg":"success","data":{"ping":"pong","service":"komichi-worker"}}
```

### 5. 初始化管理员账号

```bash
curl -X POST https://komichi-worker.xxx.workers.dev/api/auth/init
```

也可通过 `worker/init.sql` 导入（仅首次部署需要）。

### 6. 本地开发

```bash
npx wrangler dev
```

运行在 `http://localhost:8787`，自动使用 `[env.local]` 配置。

---

## CLI 工具使用

### 安装

```bash
cd cli
pip install -e .
```

验证：`komichi-cli --help`

### 配置

```bash
komichi-cli init
```

按提示输入 Worker URL、用户名、密码。配置保存在 `~/.komichi/config.json`：

```json
{
  "worker_url": "https://komichi-worker.xxx.workers.dev",
  "username": "admin",
  "password": "yourpassword",
  "upload_concurrency": 4,
  "request_timeout": 30,
  "max_retries": 3
}
```

### 导入漫画

文件夹结构要求：

```
漫画文件夹/
├── cover.jpg                    ← 封面（可选）
├── 第1话/
│   ├── 001.jpg
│   ├── 002.jpg
│   └── 003.jpg
├── 第2话/
│   ├── 001.jpg
│   └── 002.jpg
└── ...
```

- 每个子文件夹 = 一个章节，文件夹名 = 章节标题
- 支持格式：jpg / png / webp / gif

导入命令：

```bash
komichi-cli import local /path/to/comic/folder --title "作品名" --category "分类"
```

### 同步到服务器

```bash
komichi-cli sync work <slug>    # 同步指定作品
komichi-cli sync all             # 同步所有暂存作品
```

同步流程：上传图片到 R2 → 注册作品元数据到 D1。

> 注意：当前 CLI 仅上传**封面**；章节图片上传尚未实现。
> 章节图片需按 [R2 路径约定](#r2-路径) 手动上传（或用 Web 阅读器时留空），
> 例如 `komichi/chapters/<work_id>/<chapter_num>/0000.jpg`。

### 其他命令

```bash
komichi-cli config show          # 查看配置
komichi-cli config set <k> <v>   # 修改配置
komichi-cli list works           # 列出服务器作品
komichi-cli check <work_id>      # 检查更新状态
```

---

## Android 客户端编译

### 环境要求

- Android Studio Hedgehog+
- JDK 17
- Android SDK 34+
- Build-tools 35.0.0

### 编译步骤

1. `File → Open` 打开 `Komichi/android` 目录
2. 等待 Gradle Sync 完成
3. `Build → Build Bundle(s) / APK(s) → Build APK(s)`

APK 输出路径：

```
android/app/build/outputs/apk/debug/app-debug.apk
```

### 配置服务器地址

首次打开 App 后，进入 **设置** 页面，填入 Worker URL，点击保存。

---

## Web 端使用

`komichi-ui/` 是纯静态 Web 界面（无构建步骤），用任意静态服务器托管即可，在浏览器中完成全部阅读流程。

### 本地预览

```bash
cd komichi-ui
python -m http.server 8080
# 打开 http://localhost:8080/pages/login.html
```

### 部署

静态托管任意平台均可（Cloudflare Pages / GitHub Pages / nginx 等），将 `komichi-ui/` 目录设为站点根目录。

### 使用说明

1. **登录**：首次打开需在「服务器配置」中填写 Worker 地址（保存在浏览器 localStorage），再用账号密码登录
2. **首页**：最新作品 / 继续阅读（接续上次进度）/ 全部作品 / 搜索
3. **详情页**：章节列表、开始阅读、加入书架、检查更新
4. **阅读器**：支持上下滚动 / 左右翻页 / 长图三种模式，自动保存阅读进度
5. **书架 & 历史**：与阅读进度共用 `user_bookmark` 表，书架记录即阅读记录

> 注意：章节接口不返回图片清单，阅读器按
> `komichi/chapters/<work_id>/<chapter_num>/0000.jpg` 起逐张探测加载，
> 图片路径需符合 [R2 路径约定](#r2-路径)。

---

## API 接口文档

### 认证

所有 API（除登录/初始化外）需携带 JWT：

```http
Authorization: Bearer <token>
```

#### 登录

```http
POST /api/auth/login
Content-Type: application/json

{"username": "admin", "password": "admin123"}
```

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "token": "eyJ...",
    "user": { "id": 1, "username": "admin", "role": "CRAWLER" }
  }
}
```

### 核心接口

| 方法 | 路径 | 说明 | 角色 |
|------|------|------|------|
| POST | `/api/auth/init` | 初始化默认账号 | - |
| POST | `/api/auth/login` | 登录 | - |
| GET | `/api/work/list` | 作品列表（分页） | USER |
| GET | `/api/work/:id` | 作品详情（含章节） | USER |
| POST | `/api/work/update` | 新增/更新作品 | CRAWLER |
| GET | `/api/work/check/:id` | 检查更新 | USER |
| POST | `/api/bookmark/save` | 保存/更新阅读进度（书架+历史共用） | USER |
| GET | `/api/bookmark/list` | 书架/阅读记录列表 | USER |
| POST | `/api/bookmark/delete` | 删除阅读记录 | USER |
| GET | `/api/r2/sign?path=...` | 图片签名 URL | USER |
| GET | `/api/r2/proxy?path=...&token=...` | 代理读取 R2 图片（校验签名） | 签名 |
| POST | `/api/r2/upload` | 上传图片 | CRAWLER |
| GET | `/ping` | 健康检查 | - |

### 响应格式

```json
{ "code": 200, "msg": "success", "data": { ... } }
```

- `code`: 200 成功，非 200 错误（401/403 等，HTTP 状态码同步对应）
- `msg`: 提示信息
- `data`: 业务数据

### 作品新增/更新

```http
POST /api/work/update
{
  "title": "作品名",
  "category": "分类",
  "cover_r2_path": "komichi/covers/1.jpg",
  "status": "ongoing",
  "chapters": [
    {
      "chapter_num": 1,
      "chapter_title": "第1话",
      "images": ["komichi/chapters/1/1/0001.jpg"]
    }
  ]
}
```

---

## 项目约定

### R2 路径

```
komichi/
├── covers/<work_id>.<ext>
└── chapters/<work_id>/<chapter_num>/<index:04d>.<ext>
```

示例：`komichi/chapters/1/3/0001.jpg`

### 用户角色

| 角色 | 值 | 权限 |
|------|----|------|
| 普通用户 | USER | 浏览、阅读、书签 |
| 管理员 | CRAWLER | 上传、作品管理 |

### 作品状态

| 状态 | 说明 |
|------|------|
| `ongoing` | 连载中 |
| `completed` | 已完结 |

---

## 常见问题

### AAPT 编译失败

Maven 下载的 AAPT2 有 bug。编辑 `android/gradle.properties`，将 `android.aapt2FromMavenOverride` 指向本机 Build-tools 路径。

### Worker 返回 500

- 检查 `wrangler.toml` 中 `database_id` 和 `bucket_name` 是否正确
- 确认 D1 表已执行 `schema.sql`
- 检查 Cloudflare Dashboard 中 Worker 日志

### CLI 上传失败

- 检查 `~/.komichi/config.json` 中 `worker_url` 是否正确
- 确认账号角色为 CRAWLER
- 检查网络代理

### Android 图片不显示

- 确认设置页 Worker URL 正确
- 检查 Worker 是否运行正常（`curl <url>/ping`）
- 查看 Logcat 中签名 URL 获取日志
