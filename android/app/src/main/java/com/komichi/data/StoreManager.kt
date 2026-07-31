package com.komichi.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
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
    }

    val token: Flow<String> = context.dataStore.data.map { it[Keys.TOKEN] ?: "" }
    val workerUrl: Flow<String> = context.dataStore.data.map {
        normalizeUrl(it[Keys.WORKER_URL] ?: "")
    }
    val username: Flow<String> = context.dataStore.data.map { it[Keys.USERNAME] ?: "" }
    val isLoggedIn: Flow<Boolean> = context.dataStore.data.map { it[Keys.LOGGED_IN] ?: false }
    val shelfViewMode: Flow<Int> = context.dataStore.data.map { it[Keys.SHELF_VIEW_MODE] ?: 0 }

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
