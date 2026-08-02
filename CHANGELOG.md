# Changelog

本项目各端版本号以 `worker/src/index.ts` 中 `/` 路由返回的 `version` 字段为权威来源（当前 2.0.0），
各端包内的 `version` 字段应与之保持一致。重大变更在此记录。

## [2.0.0] - 2026-08-02

### 安全
- 移除 `wrangler.toml` 中硬编码的真实 VPS 域名，改为部署期注入（`wrangler secret put VPS_URL` 或 `[vars]` 占位符）。
- 下线生产残留的 `GET /api/work/debug-fetch/:id` 调试端点。
- `GET /api/work/search`（VPS 搜索代理）由免鉴权改为需登录（`authMiddleware`）。
- CORS 收紧：新增 `CORS_ALLOW_ORIGIN` 环境变量（逗号分隔白名单），命中才反射 Origin；未配置回退 `*`（仅适合内网）。
- 新增速率限制中间件（KV 可选绑定，未配自动放行）：`/search` 代理限 60s/30 次、`/login` 限 60s/10 次，防代理滥用与登录爆破。

### 文档
- 校正文档与实现分叉：Worker 实际支持 **6 个** HTTP 源（mh160mh / tencent / guazi / kuaikan / dongmanmanhua / sfacg），此前文档误写为 4 个。
- `USAGE.md` 补充已实现但遗漏的端点：`search` / `import` / `import-via-vps` / `vps-url` / `refresh-all`。

### P2 / P3（可维护性 + 端覆盖）
- **cron 追更重构**：`worker/src/index.ts` 的 `refreshAllWorks` 改为分页游标（200/批）+ 并发预算（5）+ `settings` 表租约锁（10min 过期，防重叠写入）；保留逐章去重。
- **跨端 Design Token 单一源**：新增 `design-tokens.json`（三端当前色板 + 语义令牌）+ `DESIGN_TOKENS.md`。品牌色绿/蓝分裂标记为 `UNRESOLVED`，待决策后再应用。
- **Android release 混淆**：`android/app/build.gradle.kts` 开启 `isMinifyEnabled` + `isShrinkResources`，新增 `android/app/proguard-rules.pro`（Hilt / Retrofit / kotlinx.serialization / OkHttp / Coil / Compose 保留规则）。需本地跑 release 构建验证。

### Android 设计升级（Midnight Azure）
- **高级配色**：弃用平铺 `#8AB4F8`，改用 **Midnight Azure** 午夜蓝调——近黑冷调背景（`#0E0F14`/`#15171E`/`#1E2129` 分层）、精致天蓝品牌 `#7AA2F7`、玫瑰红错误色 `#F7768E`、冷调浅色文字 `#C8D0E0`。Compose 事实来源 `ui/theme/Color.kt`，资源 `res/values(-night)/colors.xml` 同步。
- **更舒展的圆角**：`ui/theme/Shape.kt` 改为 6/8/12/16/28dp（extraSmall→extraLarge），底部 Sheet 用 28dp 更柔和。
- **全新渐变自适应图标**：`drawable/ic_launcher_bg.xml`（近黑径向渐变背景，制造纵深）+ `drawable/ic_launcher_foreground.xml`（天蓝线性渐变书本字形 + 书脊分割线）；`mipmap-anydpi-v26/ic_launcher(_round).xml` 背景改为渐变 drawable。
- `design-tokens.json`：标记 Android 品牌色决议为 `#7AA2F7`（Midnight Azure），更新 android 端点值与图标说明。

### Android 主题切换（运行时可切换配色）
- **可切换调色板体系** `ui/theme/Palette.kt`：内置 5 套深色配色——薄荷青(mint,默认) / 午夜蓝(azure) / 樱夜紫(sakura) / 暖橙(amber) / 极简灰青(slate)；每套定义完整 Material3 角色色，浅色由统一 `deriveLight` 算法派生。`KomichiPalette.toColorScheme(dark)` 生成 `ColorScheme`。
- **明暗模式** `ThemeMode` 枚举：系统 / 浅色 / 深色（`isSystemInDarkTheme()` 解析系统模式）。
- **持久化** `StoreManager` 新增 `theme_palette`(默认 mint) 与 `theme_mode`(默认 system) 两个 DataStore 键；`ThemeViewModel`(@HiltViewModel) 暴露 `palette`/`themeMode` 状态与 setter。
- **接入**：`MainActivity` 读取 `ThemeViewModel` 并传给 `KomichiTheme(palette=, darkTheme=)`；`SettingsScreen` 新增「外观」区（配色色板 + 系统/浅色/深色三段选择）即时切换并持久化。
- `Color.kt` 默认静态常量同步为薄荷青，与默认主题一致；`Theme.kt` 改为 palette 驱动，移除硬编码 `Cg*` scheme。
- `design-tokens.json`：Android 品牌色决议为薄荷青 #2DD4BF，并标注支持运行时切换。

### 审计勘误
- 原审计称「无 `migrations/` 目录」「`schema.sql` 未建索引」两项已不适用：仓库现有 `worker/migrations/`（001-003）且 `schema.sql` 含完整索引，属审计误报（期间项目已有进展）。

