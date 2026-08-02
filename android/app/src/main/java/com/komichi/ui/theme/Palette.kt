package com.komichi.ui.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.lerp

/**
 * 运行时可切换的配色体系（单一事实来源）。
 * 每套配色定义完整的 Material3 深色角色色；浅色由 [deriveLight] 统一派生。
 * 通过 [KomichiPalette.toColorScheme] 生成 ColorScheme 交给 MaterialTheme。
 *
 * 当前内置：薄荷青 / 午夜蓝 / 樱夜紫 / 暖橙 / 极简灰青，默认薄荷青。
 */

/** 一套配色在 Material3 中的全部角色色（深色）。 */
data class PaletteRoleColors(
    val primary: Color,
    val onPrimary: Color,
    val primaryContainer: Color,
    val onPrimaryContainer: Color,
    val secondary: Color,
    val onSecondary: Color,
    val secondaryContainer: Color,
    val onSecondaryContainer: Color,
    val tertiary: Color,
    val onTertiary: Color,
    val error: Color,
    val onError: Color,
    val background: Color,
    val onBackground: Color,
    val surface: Color,
    val onSurface: Color,
    val surfaceVariant: Color,
    val onSurfaceVariant: Color,
    val outline: Color,
    val outlineVariant: Color,
    val surfaceTint: Color,
    val scrim: Color,
)

/** 一个可切换的配色方案。 */
data class KomichiPalette(
    val id: String,
    val name: String,
    val dark: PaletteRoleColors,
) {
    /** 由深色派生出的浅色角色色（统一算法，保证各配色浅色一致可控）。 */
    fun light(): PaletteRoleColors = deriveLight(dark)

    /** 生成 Material3 ColorScheme。 */
    fun toColorScheme(dark: Boolean): ColorScheme {
        val c = if (dark) this.dark else light()
        return if (dark) {
            darkColorScheme(
                primary = c.primary,
                onPrimary = c.onPrimary,
                primaryContainer = c.primaryContainer,
                onPrimaryContainer = c.onPrimaryContainer,
                secondary = c.secondary,
                onSecondary = c.onSecondary,
                secondaryContainer = c.secondaryContainer,
                onSecondaryContainer = c.onSecondaryContainer,
                tertiary = c.tertiary,
                onTertiary = c.onTertiary,
                error = c.error,
                onError = c.onError,
                background = c.background,
                onBackground = c.onBackground,
                surface = c.surface,
                onSurface = c.onSurface,
                surfaceVariant = c.surfaceVariant,
                onSurfaceVariant = c.onSurfaceVariant,
                surfaceTint = c.surfaceTint,
                outline = c.outline,
                outlineVariant = c.outlineVariant,
                scrim = c.scrim,
            )
        } else {
            lightColorScheme(
                primary = c.primary,
                onPrimary = c.onPrimary,
                primaryContainer = c.primaryContainer,
                onPrimaryContainer = c.onPrimaryContainer,
                secondary = c.secondary,
                onSecondary = c.onSecondary,
                secondaryContainer = c.secondaryContainer,
                onSecondaryContainer = c.onSecondaryContainer,
                tertiary = c.tertiary,
                onTertiary = c.onTertiary,
                error = c.error,
                onError = c.onError,
                background = c.background,
                onBackground = c.onBackground,
                surface = c.surface,
                onSurface = c.onSurface,
                surfaceVariant = c.surfaceVariant,
                onSurfaceVariant = c.onSurfaceVariant,
                surfaceTint = c.surfaceTint,
                outline = c.outline,
                outlineVariant = c.outlineVariant,
                scrim = c.scrim,
            )
        }
    }
}

/** 主题明暗模式。 */
enum class ThemeMode(val id: String) {
    SYSTEM("system"),
    LIGHT("light"),
    DARK("dark");

    companion object {
        fun fromId(id: String): ThemeMode = entries.firstOrNull { it.id == id } ?: SYSTEM
    }
}

private val WHITE = Color(0xFFFFFFFF)
private val BLACK = Color(0xFF000000)
private val NEUTRAL_ON_LIGHT = Color(0xFF16191A)

/** 统一浅色派生：白底 + 品牌色加深以保证对比度。 */
private fun deriveLight(d: PaletteRoleColors): PaletteRoleColors {
    val darken = { c: Color -> lerp(c, BLACK, 0.40f) }
    return PaletteRoleColors(
        primary = darken(d.primary),
        onPrimary = WHITE,
        primaryContainer = lerp(d.primary, WHITE, 0.82f),
        onPrimaryContainer = lerp(d.primary, BLACK, 0.55f),
        secondary = lerp(d.secondary, BLACK, 0.30f),
        onSecondary = WHITE,
        secondaryContainer = lerp(d.secondary, WHITE, 0.80f),
        onSecondaryContainer = lerp(d.secondary, BLACK, 0.55f),
        tertiary = darken(d.tertiary),
        onTertiary = WHITE,
        error = lerp(d.error, BLACK, 0.30f),
        onError = WHITE,
        background = lerp(d.primary, WHITE, 0.94f),
        onBackground = NEUTRAL_ON_LIGHT,
        surface = WHITE,
        onSurface = NEUTRAL_ON_LIGHT,
        surfaceVariant = lerp(d.surfaceVariant, WHITE, 0.82f),
        onSurfaceVariant = lerp(d.onSurfaceVariant, BLACK, 0.30f),
        outline = lerp(d.outline, WHITE, 0.82f),
        outlineVariant = lerp(d.surfaceVariant, WHITE, 0.85f),
        surfaceTint = darken(d.primary),
        scrim = BLACK,
    )
}

// ── 内置配色 ───────────────────────────────────────────────

private val MINT_FROST = KomichiPalette(
    id = "mint",
    name = "薄荷青",
    dark = PaletteRoleColors(
        primary = Color(0xFF2DD4BF),
        onPrimary = Color(0xFF03201C),
        primaryContainer = Color(0xFF0E3D37),
        onPrimaryContainer = Color(0xFF9DF0E2),
        secondary = Color(0xFF8AA8A2),
        onSecondary = Color(0xFF03201C),
        secondaryContainer = Color(0xFF1C2E2B),
        onSecondaryContainer = Color(0xFFB6CFC9),
        tertiary = Color(0xFF5EEAD4),
        onTertiary = Color(0xFF03201C),
        error = Color(0xFFFB7185),
        onError = Color(0xFF2A0A12),
        background = Color(0xFF0D1413),
        onBackground = Color(0xFFD2E6E2),
        surface = Color(0xFF15211F),
        onSurface = Color(0xFFD2E6E2),
        surfaceVariant = Color(0xFF1C2E2B),
        onSurfaceVariant = Color(0xFF8AA8A2),
        outline = Color(0xFF233531),
        outlineVariant = Color(0xFF1C2E2B),
        surfaceTint = Color(0xFF2DD4BF),
        scrim = BLACK,
    ),
)

private val MIDNIGHT_AZURE = KomichiPalette(
    id = "azure",
    name = "午夜蓝",
    dark = PaletteRoleColors(
        primary = Color(0xFF7AA2F7),
        onPrimary = Color(0xFF0B0E14),
        primaryContainer = Color(0xFF1E2A45),
        onPrimaryContainer = Color(0xFFBCD4FF),
        secondary = Color(0xFF8B93A7),
        onSecondary = Color(0xFF0B0E14),
        secondaryContainer = Color(0xFF242831),
        onSecondaryContainer = Color(0xFFC8D0E0),
        tertiary = Color(0xFFE0AF68),
        onTertiary = Color(0xFF0B0E14),
        error = Color(0xFFF7768E),
        onError = Color(0xFF0B0E14),
        background = Color(0xFF0E0F14),
        onBackground = Color(0xFFC8D0E0),
        surface = Color(0xFF15171E),
        onSurface = Color(0xFFC8D0E0),
        surfaceVariant = Color(0xFF1E2129),
        onSurfaceVariant = Color(0xFF8B93A7),
        outline = Color(0xFF2A2E38),
        outlineVariant = Color(0xFF1E2129),
        surfaceTint = Color(0xFF7AA2F7),
        scrim = BLACK,
    ),
)

private val SAKURA_DUSK = KomichiPalette(
    id = "sakura",
    name = "樱夜紫",
    dark = PaletteRoleColors(
        primary = Color(0xFFBB9AF7),
        onPrimary = Color(0xFF1A0F2E),
        primaryContainer = Color(0xFF2E2150),
        onPrimaryContainer = Color(0xFFE0D4FF),
        secondary = Color(0xFFC9B6E8),
        onSecondary = Color(0xFF1A0F2E),
        secondaryContainer = Color(0xFF2A2040),
        onSecondaryContainer = Color(0xFFE9DCF7),
        tertiary = Color(0xFFFF9EBD),
        onTertiary = Color(0xFF2A0F1E),
        error = Color(0xFFF7768E),
        onError = Color(0xFF2A0A12),
        background = Color(0xFF16131C),
        onBackground = Color(0xFFD6D0E8),
        surface = Color(0xFF221B2E),
        onSurface = Color(0xFFD6D0E8),
        surfaceVariant = Color(0xFF2A2040),
        onSurfaceVariant = Color(0xFFA99CC4),
        outline = Color(0xFF322A40),
        outlineVariant = Color(0xFF2A2040),
        surfaceTint = Color(0xFFBB9AF7),
        scrim = BLACK,
    ),
)

private val AMBER_EMBER = KomichiPalette(
    id = "amber",
    name = "暖橙",
    dark = PaletteRoleColors(
        primary = Color(0xFFF0B454),
        onPrimary = Color(0xFF2A1700),
        primaryContainer = Color(0xFF4A2F00),
        onPrimaryContainer = Color(0xFFFFD9A0),
        secondary = Color(0xFFD9A06A),
        onSecondary = Color(0xFF2A1700),
        secondaryContainer = Color(0xFF3A2613),
        onSecondaryContainer = Color(0xFFE8C9A0),
        tertiary = Color(0xFFFF9E64),
        onTertiary = Color(0xFF2A1700),
        error = Color(0xFFF2597C),
        onError = Color(0xFF2A0A12),
        background = Color(0xFF14110D),
        onBackground = Color(0xFFE8DFD2),
        surface = Color(0xFF201913),
        onSurface = Color(0xFFE8DFD2),
        surfaceVariant = Color(0xFF3A2F22),
        onSurfaceVariant = Color(0xFFB59A7E),
        outline = Color(0xFF3A2F22),
        outlineVariant = Color(0xFF3A2F22),
        surfaceTint = Color(0xFFF0B454),
        scrim = BLACK,
    ),
)

private val SLATE_MONO = KomichiPalette(
    id = "slate",
    name = "极简灰青",
    dark = PaletteRoleColors(
        primary = Color(0xFF7DD3FC),
        onPrimary = Color(0xFF04222E),
        primaryContainer = Color(0xFF0E3A47),
        onPrimaryContainer = Color(0xFFCDEAFB),
        secondary = Color(0xFF94A3B8),
        onSecondary = Color(0xFF04222E),
        secondaryContainer = Color(0xFF26303A),
        onSecondaryContainer = Color(0xFFD6E2F0),
        tertiary = Color(0xFF7DD3FC),
        onTertiary = Color(0xFF04222E),
        error = Color(0xFFF87171),
        onError = Color(0xFF2A0A0A),
        background = Color(0xFF121316),
        onBackground = Color(0xFFE2E8F0),
        surface = Color(0xFF1B1D22),
        onSurface = Color(0xFFE2E8F0),
        surfaceVariant = Color(0xFF26282E),
        onSurfaceVariant = Color(0xFF94A3B8),
        outline = Color(0xFF2C2F36),
        outlineVariant = Color(0xFF26282E),
        surfaceTint = Color(0xFF7DD3FC),
        scrim = BLACK,
    ),
)

/** 全部可切换配色（顺序即 UI 展示顺序）。 */
val AVAILABLE_PALETTES: List<KomichiPalette> =
    listOf(MINT_FROST, MIDNIGHT_AZURE, SAKURA_DUSK, AMBER_EMBER, SLATE_MONO)

/** 默认配色（薄荷青）。 */
val DEFAULT_PALETTE: KomichiPalette = MINT_FROST

/** 按 id 查找配色，找不到回退默认。 */
fun paletteById(id: String): KomichiPalette =
    AVAILABLE_PALETTES.firstOrNull { it.id == id } ?: DEFAULT_PALETTE
