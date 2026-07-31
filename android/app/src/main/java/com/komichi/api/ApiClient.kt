@file:OptIn(kotlinx.serialization.ExperimentalSerializationApi::class)

package com.komichi.api

import com.komichi.data.StoreManager
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Response
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 网络客户端：构建 OkHttp + Retrofit，并通过拦截器实现：
 * 1. 动态 Worker 基地址（运行时可切换）。
 * 2. 自动注入 JWT Token。
 * 3. 统一 JSON 解析（宽松模式，兼容后端字段差异）。
 */
@Singleton
class ApiClient @Inject constructor(
    private val storeManager: StoreManager,
) {
    @Volatile
    private var cachedBaseUrl: String = ""

    @Volatile
    private var cachedToken: String = ""

    val json: Json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        coerceInputValues = true
        explicitNulls = false
        encodeDefaults = true
    }

    private val okHttpClient: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .addInterceptor(::dynamicInterceptor)
            .addInterceptor(
                okhttp3.logging.HttpLoggingInterceptor().apply {
                    level = okhttp3.logging.HttpLoggingInterceptor.Level.BASIC
                }
            )
            .build()
    }

    val apiService: ApiService by lazy {
        Retrofit.Builder()
            // 占位 baseUrl，真实地址由拦截器动态替换
            .baseUrl("https://localhost/")
            .client(okHttpClient)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(ApiService::class.java)
    }

    /**
     * 在登录成功或服务器地址变更后调用，刷新缓存配置。
     */
    suspend fun refreshConfig() {
        cachedBaseUrl = storeManager.workerUrl.first()
        cachedToken = storeManager.token.first()
    }

    /** 仅刷新 token 缓存 */
    suspend fun refreshToken() {
        cachedToken = storeManager.token.first()
    }

    private fun ensureBaseUrl() {
        if (cachedBaseUrl.isBlank()) {
            runBlocking { cachedBaseUrl = storeManager.workerUrl.first() }
        }
    }

    private fun ensureToken() {
        if (cachedToken.isBlank()) {
            runBlocking { cachedToken = storeManager.token.first() }
        }
    }

    private fun dynamicInterceptor(chain: Interceptor.Chain): Response {
        ensureBaseUrl()
        ensureToken()
        val original = chain.request()
        val base = cachedBaseUrl.trimEnd('/')

        val path = original.url.encodedPath
        val query = original.url.encodedQuery
        val newHttpUrl = if (base.isNotBlank()) {
            val full = StringBuilder(base).append(path)
            if (!query.isNullOrBlank()) full.append('?').append(query)
            full.toString().toHttpUrl()
        } else {
            original.url
        }

        val requestBuilder = original.newBuilder().url(newHttpUrl)
        // 登录与健康检查不带 Token，其余请求自动携带
        val needAuth = !path.endsWith("/ping") && !path.endsWith("/api/auth/login")
        if (needAuth && cachedToken.isNotBlank()) {
            requestBuilder.addHeader("Authorization", "Bearer $cachedToken")
        }

        return chain.proceed(requestBuilder.build())
    }
}
