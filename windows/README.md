# Komichi Windows 桌面客户端

原生 Windows GUI（C# / WPF / .NET 8），连接 Komichi Worker API，功能对齐 Android 客户端。视觉风格与 Android 端一致（精致深色风 + 品牌绿 `#32F08C`）。

## 功能

- **登录** — Worker API 账号登录（admin/crawler），token 持久化到 `%AppData%\Komichi\config.json`，下次启动免登录
- **书架** — 作品列表（封面、状态徽章、更新话数），点击卡片进入详情
- **阅读记录** — 显示每部作品的阅读进度（读到第几话 / 共几话），点击卡片**直达阅读器续读**
- **作品详情** — 简介 + 完整章节列表，支持选中章节阅读
- **阅读器** — 章节导航（按钮 + ←/→ 方向键），打开章节即自动**同步阅读进度**到服务器，跨设备（Android/Web）继续
- **检查更新** — 实时爬取源站检查新章节（`force=true`）
- **导入作品** — 输入源站 URL 直接导入（Worker 爬虫/VPS 回退）

## 视觉设计

对齐 Android 端 CgDarkColorScheme 配色体系：

| 元素 | 值 |
|------|-----|
| 背景 / 卡片 / 浮层 | `#1A1B1D` / `#222427` / `#2A2D31` |
| 品牌绿（主操作） | `#32F08C`（容器 `#143D29`） |
| 强调色 | 琥珀 `#DCB364` / 青绿 `#2DD288` / 珊瑚 `#FF9392` |
| 文字层级 | `#D1D3DB` / `#9599A6` / `#666B75` |
| 边框层级 | `#383A40` / `#4A4D55` / `#5C5F68` |
| 错误 | `#FF5C5C` |

- 无边框圆角窗口（14px 登录 / 12px 其他），自绘标题栏（拖拽移动、双击最大化、悬浮关闭变红）
- 卡片悬浮：品牌绿描边 + 1.02 微放大 + 阴影
- 主按钮：品牌渐变 + 按下微缩（0.97）+ 发光投影；进度条呼吸动画

## 技术栈

| 组件 | 说明 |
|------|------|
| .NET 8 | LTS，`net8.0-windows` |
| WPF | XAML + MVVM（手写 ObservableObject/AsyncRelayCommand） |
| HttpClient | 无第三方依赖，仅 System.Text.Json |

## 运行

```bash
cd windows
dotnet run --project Komichi.Desktop
```

发布单文件：

```bash
cd windows
dotnet publish Komichi.Desktop -c Release -r win-x64 --self-contained -p:PublishSingleFile=true
# 产物: Komichi.Desktop/bin/Release/net8.0-windows/win-x64/publish/Komichi.Desktop.exe
```

> 自包含发布约 150MB（含 .NET 运行时）；如目标机器已装 .NET 8 可去掉 `--self-contained` 缩小到几 MB。

## 项目结构

```
windows/Komichi.Desktop/
├── App.xaml(.cs)          # 入口：配置判断 → 登录窗口/主窗口，全局异常兜底
├── Models/ApiModels.cs    # Worker API 响应模型（Work/Chapter/Bookmark/...）
├── Services/
│   ├── AppConfig.cs       # 本地配置（Worker 地址 + token + 用户）
│   ├── KomichiApiClient.cs# API 客户端（登录/列表/详情/书签/R2 签名/导入/检查更新）
│   └── WindowChromeHelper.cs # 无边框圆角窗口（拖拽/缩放/自绘标题栏）
├── ViewModels/            # MVVM：Login / Main(书架+记录) / Detail / Reader
├── Views/                 # 窗口：CustomTitleBar / Login / Main / Detail / Reader
└── Converters/            # XAML 转换器（可见性/状态徽章颜色/占位）
```

## API 连接

- 默认 Worker 地址：`https://komichi.270312.xyz`（登录页可改）
- 首次使用需在 Worker 上执行过 `/api/auth/init`（默认账号 admin/admin123）
- 阅读进度走 `/api/bookmark/save`，与 Android 端同一张 `user_bookmark` 表，实时互通

## 与 Android 端的差异

- 阅读器当前为**追踪模式**（记录进度，不渲染漫画图片）——与 Android 端当前行为一致
- 书架卡片点击行为：普通作品开详情；有阅读记录的作品直接续读
