package com.komichi

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.getValue
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.komichi.ui.navigation.KomichiNavHost
import com.komichi.ui.theme.KomichiTheme
import com.komichi.viewmodel.ThemeViewModel
import dagger.hilt.android.AndroidEntryPoint
import androidx.hilt.navigation.compose.hiltViewModel

/**
 * 应用入口 Activity，承载 Compose 导航宿主。
 */
@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val themeVm: ThemeViewModel = hiltViewModel()
            val palette by themeVm.palette.collectAsStateWithLifecycle()
            val mode by themeVm.themeMode.collectAsStateWithLifecycle()
            val isDark = when (mode) {
                com.komichi.ui.theme.ThemeMode.LIGHT -> false
                com.komichi.ui.theme.ThemeMode.DARK -> true
                else -> isSystemInDarkTheme()
            }
            KomichiTheme(palette = palette, darkTheme = isDark) {
                KomichiNavHost()
            }
        }
    }
}
