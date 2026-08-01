package com.komichi.ui.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Settings

import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument

/**
 * 路由常量与构造器。
 */
object Routes {
    const val SPLASH = "splash"
    const val LOGIN = "login"
    const val MAIN = "main"

    const val DETAIL = "detail/{workId}"
    fun detail(workId: Long) = "detail/$workId"

    const val READER = "reader/{workId}/{chapterNum}"
    fun reader(workId: Long, chapterNum: Int) = "reader/$workId/$chapterNum"
}

/** 底部导航 Tab */
enum class BottomTab(val route: String, val labelRes: Int, val icon: androidx.compose.ui.graphics.vector.ImageVector) {
    Home("home", com.komichi.R.string.nav_home, Icons.Filled.Home),
    Shelf("shelf", com.komichi.R.string.nav_shelf, Icons.AutoMirrored.Filled.MenuBook),
    History("history", com.komichi.R.string.nav_history, Icons.Filled.History),
    Settings("settings", com.komichi.R.string.nav_settings, Icons.Filled.Settings),
}

/**
 * 顶层导航宿主：Splash → Login → Main → Detail。
 */
@androidx.compose.runtime.Composable
fun KomichiNavHost() {
    val navController = rememberNavController()

    NavHost(
        navController = navController,
        startDestination = Routes.SPLASH,
        enterTransition = { fadeIn(tween(220)) },
        exitTransition = { fadeOut(tween(180)) },
    ) {
        composable(Routes.SPLASH) {
            com.komichi.ui.screens.splash.SplashScreen(
                onNavigate = { dest ->
                    navController.navigate(dest) {
                        popUpTo(Routes.SPLASH) { inclusive = true }
                    }
                },
            )
        }

        composable(Routes.LOGIN) {
            com.komichi.ui.screens.login.LoginScreen(
                onLoginSuccess = {
                    navController.navigate(Routes.MAIN) {
                        popUpTo(Routes.LOGIN) { inclusive = true }
                    }
                },
            )
        }

        composable(Routes.MAIN) {
            com.komichi.ui.navigation.MainScreen(
                onOpenDetail = { workId -> navController.navigate(Routes.detail(workId)) },
            )
        }

        composable(
            route = Routes.DETAIL,
            arguments = listOf(navArgument("workId") { type = NavType.LongType }),
        ) { backStackEntry ->
            val workId = backStackEntry.arguments?.getLong("workId") ?: 0L
            com.komichi.ui.screens.detail.DetailScreen(
                onBack = { navController.popBackStack() },
                onOpenReader = { chapterNum -> navController.navigate(Routes.reader(workId, chapterNum)) },
            )
        }

        composable(
            route = Routes.READER,
            arguments = listOf(
                navArgument("workId") { type = NavType.LongType },
                navArgument("chapterNum") { type = NavType.IntType },
            ),
        ) {
            com.komichi.ui.screens.reader.ReaderScreen(
                onBack = { navController.popBackStack() },
            )
        }
    }
}
