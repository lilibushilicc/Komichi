package com.komichi.ui.theme

import android.app.Activity
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

/**
 * 应用主题。由 [palette]（可切换配色）与 [darkTheme]（明暗）共同决定 ColorScheme。
 * 默认强制暗色阅读风格；传入 darkTheme=false 即切换浅色（由 palette 派生）。
 * 沉浸式状态/导航栏颜色随主题切换。
 */
@Composable
fun KomichiTheme(
    palette: KomichiPalette = DEFAULT_PALETTE,
    darkTheme: Boolean = true,
    content: @Composable () -> Unit,
) {
    val colorScheme = palette.toColorScheme(darkTheme)
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.background.toArgb()
            window.navigationBarColor = colorScheme.background.toArgb()
            val controller = WindowCompat.getInsetsController(window, view)
            controller.isAppearanceLightStatusBars = !darkTheme
            controller.isAppearanceLightNavigationBars = !darkTheme
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = CgTypography,
        shapes = CgShapes,
        content = content,
    )
}
