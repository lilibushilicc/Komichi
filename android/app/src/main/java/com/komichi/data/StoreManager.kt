package com.komichi.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "komichi_prefs")

/**
 * 基于 DataStore 的本地持久化管理。
 * 保存登录态、Worker 地址、Token、默认阅读模式、用户名等。
 */
@Singleton
class StoreManager @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private object Keys {
        val TOKEN = stringPreferencesKey("token")
        val WORKER_URL = stringPreferencesKey("worker_url")
        val USERNAME = stringPreferencesKey("username")
        val LOGGED_IN = booleanPreferencesKey("logged_in")
        val SHELF_VIEW_MODE = intPreferencesKey("shelf_view_mode") // 0=grid 1=list
        val DISABLED_SOURCES = stringSetPreferencesKey("disabled_sources")
        val THEME_PALETTE = stringPreferencesKey("theme_palette") // 配色 id，默认 mint
        val THEME_MODE = stringPreferencesKey("theme_mode")       // system/light/dark
    }

    val token: Flow<String> = context.dataStore.data.map { it[Keys.TOKEN] ?: "" }
    val workerUrl: Flow<String> = context.dataStore.data.map {
        normalizeUrl(it[Keys.WORKER_URL] ?: "")
    }
    val username: Flow<String> = context.dataStore.data.map { it[Keys.USERNAME] ?: "" }
    val isLoggedIn: Flow<Boolean> = context.dataStore.data.map { it[Keys.LOGGED_IN] ?: false }
    val shelfViewMode: Flow<Int> = context.dataStore.data.map { it[Keys.SHELF_VIEW_MODE] ?: 0 }

    /** 当前配色 id（默认 mint） */
    val themePalette: Flow<String> = context.dataStore.data.map { it[Keys.THEME_PALETTE] ?: "mint" }

    /** 当前明暗模式（默认 system） */
    val themeMode: Flow<String> = context.dataStore.data.map { it[Keys.THEME_MODE] ?: "system" }

    /** 被禁用的源名集合（默认空 = 全部启用） */
    val disabledSources: Flow<Set<String>> = context.dataStore.data.map {
        it[Keys.DISABLED_SOURCES] ?: emptySet()
    }

    suspend fun saveAuth(token: String, username: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.TOKEN] = token
            prefs[Keys.USERNAME] = username
            prefs[Keys.LOGGED_IN] = true
        }
    }

    suspend fun saveWorkerUrl(url: String) {
        context.dataStore.edit { it[Keys.WORKER_URL] = normalizeUrl(url) }
    }

    suspend fun saveShelfViewMode(mode: Int) {
        context.dataStore.edit { it[Keys.SHELF_VIEW_MODE] = mode }
    }

    /** 设置当前配色 id（如 mint / azure / sakura / amber / slate） */
    suspend fun saveThemePalette(id: String) {
        context.dataStore.edit { it[Keys.THEME_PALETTE] = id }
    }

    /** 设置明暗模式（system / light / dark） */
    suspend fun saveThemeMode(mode: String) {
        context.dataStore.edit { it[Keys.THEME_MODE] = mode }
    }

    /** 启用或禁用某个源 */
    suspend fun setSourceEnabled(name: String, enabled: Boolean) {
        context.dataStore.edit { prefs ->
            val current = prefs[Keys.DISABLED_SOURCES] ?: emptySet()
            prefs[Keys.DISABLED_SOURCES] = if (enabled) {
                current - name
            } else {
                current + name
            }
        }
    }

    suspend fun clearAuth() {
        context.dataStore.edit { prefs ->
            prefs.remove(Keys.TOKEN)
            prefs.remove(Keys.USERNAME)
            prefs[Keys.LOGGED_IN] = false
        }
    }

    private fun normalizeUrl(url: String): String {
        var u = url.trim()
        while (u.endsWith("/")) u = u.dropLast(1)
        return u
    }
}
