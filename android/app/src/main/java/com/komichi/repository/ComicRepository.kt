@file:OptIn(kotlinx.serialization.ExperimentalSerializationApi::class)

package com.komichi.repository

import com.komichi.api.ApiClient
import com.komichi.api.ApiService
import com.komichi.api.unwrap
import com.komichi.data.Bookmark
import com.komichi.data.LoginRequest
import com.komichi.data.SaveBookmarkRequest
import com.komichi.data.StoreManager
import com.komichi.data.Work
import com.komichi.data.WorkDetail
import kotlinx.coroutines.flow.first
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ComicRepository @Inject constructor(
    private val apiService: ApiService,
    private val apiClient: ApiClient,
    private val storeManager: StoreManager,
) {
    private val json: Json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        coerceInputValues = true
        explicitNulls = false
    }

    // ---------- 认证 ----------

    suspend fun testConnection(workerUrl: String): Boolean {
        val base = normalizeUrl(workerUrl)
        if (base.isBlank()) return false
        return runCatching {
            val client = OkHttpClient.Builder()
                .connectTimeout(10, TimeUnit.SECONDS)
                .readTimeout(10, TimeUnit.SECONDS)
                .build()
            val tempApi = Retrofit.Builder()
                .baseUrl("$base/")
                .client(client)
                .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
                .build()
                .create(ApiService::class.java)
            tempApi.ping().isSuccess
        }.getOrDefault(false)
    }

    suspend fun login(username: String, password: String, workerUrl: String): String {
        storeManager.saveWorkerUrl(workerUrl)
        apiClient.refreshConfig()
        val resp = apiService.login(LoginRequest(username, password)).unwrap()
        storeManager.saveAuth(resp.token, username)
        apiClient.refreshToken()
        return resp.token
    }

    suspend fun logout() {
        storeManager.clearAuth()
        apiClient.refreshConfig()
    }

    // ---------- 作品 ----------

    suspend fun getWorkList(status: Int? = null): List<Work> {
        val statusStr = when (status) {
            1 -> "completed"
            else -> null
        }
        return apiService.getWorkList(page = 1, size = 500, status = statusStr).unwrap().list
    }

    suspend fun getWorkDetail(id: Long): WorkDetail =
        apiService.getWorkDetail(id).unwrap()

    suspend fun checkUpdate(id: Long): String =
        apiService.checkUpdate(id).unwrap().let { r ->
            if (r.hasUpdate) "发现新章节" else "已是最新"
        }

    // ---------- 书签 ----------

    suspend fun getBookmarks(): List<Bookmark> =
        apiService.getBookmarkList().unwrap().list

    suspend fun saveBookmark(workId: Long, chapterNum: Int, note: String = ""): Boolean =
        runCatching {
            apiService.saveBookmark(SaveBookmarkRequest(workId, chapterNum, note)).isSuccess
        }.getOrDefault(false)

    suspend fun deleteBookmark(workId: Long): Boolean =
        runCatching {
            apiService.deleteBookmark(mapOf("work_id" to workId)).isSuccess
        }.getOrDefault(false)

    suspend fun deleteWork(workId: Long): Boolean =
        runCatching {
            apiService.deleteWork(mapOf("id" to workId)).isSuccess
        }.getOrDefault(false)

    // ---------- 配置 ----------

    suspend fun currentWorkerUrl(): String = storeManager.workerUrl.first()
    suspend fun currentUsername(): String = storeManager.username.first()
    suspend fun isLoggedIn(): Boolean = storeManager.isLoggedIn.first()

    suspend fun refreshConfig() {
        apiClient.refreshConfig()
    }

    fun storeManager(): StoreManager = storeManager

    private fun normalizeUrl(url: String): String {
        var u = url.trim()
        while (u.endsWith("/")) u = u.dropLast(1)
        return u
    }
}
