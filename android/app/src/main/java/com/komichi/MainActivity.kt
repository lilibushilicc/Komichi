package com.komichi

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import com.komichi.ui.navigation.KomichiNavHost
import com.komichi.ui.theme.KomichiTheme
import dagger.hilt.android.AndroidEntryPoint

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
            KomichiTheme {
                KomichiNavHost()
            }
        }
    }
}
