package com.komichi.ui.theme

import androidx.compose.ui.graphics.Color

// ════════════════════════════════════════════════════════════════════════
// Komichi Design Tokens — Android (Compose) 默认配色
// 默认 = Mint Frost（薄荷青）#2DD4BF，与 design-tokens.json / Palette.kt 对齐。
// 运行时可切换的「配色方案」见 Palette.kt（KomichiPalette），此处保留为
// 各屏幕直接引用的便捷常量（默认主题下的取值）。切换配色后，MaterialTheme
// 驱动的组件会自动跟随；以下为默认主题静态值。
// ════════════════════════════════════════════════════════════════════════

// ── 背景层级（近黑青调） ──
val CgBlack = Color(0xFF06100E)
val CgBackground = Color(0xFF0D1413)        // bg-base-default
val CgSurface = Color(0xFF15211F)            // bg-base-secondary
val CgSurfaceVariant = Color(0xFF1C2E2B)     // bg-base-tertiary
val CgSurfaceElevated = Color(0xFF1E302C)    // 抬升层
val CgCard = Color(0xFF182420)
val CgMenu = Color(0xFF1A2A27)
val CgTooltip = Color(0xFF0D1413)

// ── 品牌色（Mint Frost 薄荷青 #2DD4BF） ──
val CgPrimary = Color(0xFF2DD4BF)
val CgPrimaryHover = Color(0xFF5EEAD4)
val CgOnPrimary = Color(0xFF03201C)
val CgPrimaryContainer = Color(0xFF0E3D37)
val CgOnPrimaryContainer = Color(0xFF9DF0E2)
val CgPrimaryDisabled = Color(0xFF2DD4BF)    // 透明度控制

// ── 次级/辅助 ──
val CgSecondary = Color(0xFF8AA8A2)
val CgOnSecondary = Color(0xFF03201C)
val CgSecondaryContainer = Color(0xFF1C2E2B)

// ── 强调色（功能色，非品牌） ──
val CgAccent = Color(0xFFE0AF68)            // amber
val CgTeal = Color(0xFF73DACA)               // teal
val CgCoral = Color(0xFFFB7185)              // coral/rose

// ── 状态色 ──
val CgError = Color(0xFFFB7185)              // 玫瑰红（高级感错误色）
val CgOnError = Color(0xFF2A0A12)
val CgStatusOngoing = Color(0xFF2DD4BF)      // 连载中 → 品牌青
val CgStatusCompleted = Color(0xFFE0AF68)   // 已完结 → amber
val CgChapterRead = Color(0xFF5C7070)        // 已读章节 → 文字三级

// ── 文字层级（冷调浅色，耐看） ──
val CgOnBackground = Color(0xFFD2E6E2)       // text-default
val CgOnSurface = Color(0xFFD2E6E2)
val CgOnSurfaceVariant = Color(0xFF8AA8A2)   // text-secondary
val CgOnSurfaceTertiary = Color(0xFF5C7070)  // text-tertiary

// ── 边框层级 ──
val CgOutline = Color(0xFF233531)            // border-l1
val CgOutlineMedium = Color(0xFF2F423D)      // border-l2
val CgOutlineStrong = Color(0xFF3C524C)      // border-l3
val CgOutlineVariant = Color(0xFF1C2E2B)
val CgBorderBrand = Color(0xFF2DD4BF)

// ── 骨架屏/加载 ──
val CgShimmerBase = Color(0xFF182420)
val CgShimmerHighlight = Color(0xFF233531)
