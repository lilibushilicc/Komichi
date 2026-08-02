# Komichi Design Tokens

跨端设计令牌的**单一事实来源（single source of truth）**。

- 机器可读令牌：`design-tokens.json`
- 当前状态：**DRAFT**，尚未应用到所有端。各端仍直接硬编码自己的色值。

## 为什么需要它

三端（Web / Android / Windows）目前各自维护一套色板，且存在明显分歧：

| 语义色 | Web | Android | Windows |
|--------|-----|---------|---------|
| 品牌色 | `#32F08C`（绿） | `#8AB4F8`（蓝） | `#32F08C`（绿） |
| 背景 | `#1A1B1D` | `#101012` | `#1A1B1D` |
| 错误 | `#F65A5A` | `#CF6679` | `#FF5C5C` |
| 边框 | `rgba(...,0.1)` 发丝 | `#3A3A3F` 实色 | `#383A40` 实色 |

最关键的未决项：**品牌色绿 vs 蓝尚未统一**（`design-tokens.json` 中 `decisions.brandColor` 标记为 `UNRESOLVED`）。在定下之前，不要大规模应用令牌。

## 如何使用（目标形态）

1. **定品牌色**：先决定绿或蓝，写回 `decisions.brandColor` 与 `semantic.color.brand`。
2. **各端消费**：
   - Web：把 `komichi-ui/colors_and_type.css` 的硬编码值改为引用令牌（可经构建脚本从 JSON 生成 CSS 变量）。
   - Android：在 `colors.xml` 中以令牌值为准，删掉 Web/WPF 不一致的副本。
   - Windows：在 `App.xaml` 的 Brush 定义对齐令牌，并统一质感基线（圆角/阴影/边框强度）。
3. **图标**：Web 现有 `assets/icons/trae/` 是按颜色预烘焙的 SVG（`check.33c192.svg` 等），需改为 `currentColor` 单色集以便跟随主题。
4. **主题**：三端目前均 dark-only，浅色/护眼模式需另起令牌组。

## 改动纪律

- 改色只改 `design-tokens.json` 这一处，由各端构建/同步流程分发。
- 新增语义色先在此文件登记，再在各端落地。
- 不要在各端直接新增硬编码色值而不登记。
