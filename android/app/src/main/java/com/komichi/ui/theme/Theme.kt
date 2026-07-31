package com.komichi.ui.theme

import android.app.Activity
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val CgDarkColorScheme = darkColorScheme(
    primary = CgPrimary,
    onPrimary = CgOnPrimary,
    primaryContainer = CgPrimaryContainer,
    onPrimaryContainer = CgOnPrimaryContainer,
    secondary = CgSecondary,
    onSecondary = CgOnSecondary,
    secondaryContainer = CgSecondaryContainer,
    onSecondaryContainer = CgOnBackground,
    tertiary = CgAccent,
    onTertiary = CgBlack,
    error = CgError,
    onError = CgOnError,
    background = CgBackground,
    onBackground = CgOnBackground,
    surface = CgSurface,
    onSurface = CgOnSurface,
    surfaceVariant = CgSurfaceVariant,
    onSurfaceVariant = CgOnSurfaceVariant,
    surfaceTint = CgPrimary,
    outline = CgOutline,
    outlineVariant = CgOutlineVariant,
    scrim = CgBlack,
)

/**
 * 应用主题：强制暗色阅读风格，沉浸式状态/导航栏。
 */
@Composable
fun KomichiTheme(
    darkTheme: Boolean = true,
    content: @Composable () -> Unit,
) {
    val colorScheme = CgDarkColorScheme
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = CgBackground.toArgb()
            window.navigationBarColor = CgBackground.toArgb()
            val controller = WindowCompat.getInsetsController(window, view)
            controller.isAppearanceLightStatusBars = false
            controller.isAppearanceLightNavigationBars = false
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = CgTypography,
        shapes = CgShapes,
        content = content,
    )
}
