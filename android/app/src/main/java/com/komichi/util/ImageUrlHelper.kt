package com.komichi.util

import coil.intercept.Interceptor
import coil.request.ImageResult
import com.komichi.api.ApiService
import com.komichi.api.unwrap
import com.komichi.api.SignUrlResponse

object ImageUrlHelper {

    fun isAbsoluteUrl(s: String): Boolean =
        s.startsWith("http://", ignoreCase = true) || s.startsWith("https://", ignoreCase = true)

    fun normalizePath(path: String?): String {
        if (path.isNullOrBlank()) return ""
        val p = path.trim()
        if (isAbsoluteUrl(p)) return p
        return p.trimStart('/')
    }

    fun needsSign(s: String?): Boolean =
        !s.isNullOrBlank() && !isAbsoluteUrl(s.trim())
}

class R2SignInterceptor(
    private val apiService: ApiService,
) : Interceptor {

    /** path -> (过期时间秒, 签名URL)。签名 URL 在服务器端按天稳定，会话内复用可省去重复签名请求。 */
    private val signedUrlCache = java.util.concurrent.ConcurrentHashMap<String, Pair<Long, String>>()

    override suspend fun intercept(chain: Interceptor.Chain): ImageResult {
        val data = chain.request.data
        if (data is String && ImageUrlHelper.needsSign(data)) {
            val path = ImageUrlHelper.normalizePath(data)
            val nowSec = System.currentTimeMillis() / 1000

            val cached = signedUrlCache[path]
            val signedUrl = if (cached != null && cached.first > nowSec) {
                cached.second
            } else {
                runCatching { apiService.signR2Url(path).unwrap() }
                    .getOrNull()
                    ?.also {
                        if (it.expireAt > nowSec) {
                            signedUrlCache[path] = it.expireAt to it.url
                        }
                    }
                    ?.url
            }

            if (!signedUrl.isNullOrBlank()) {
                val newRequest = chain.request.newBuilder().data(signedUrl).build()
                return chain.proceed(newRequest)
            }
        }
        return chain.proceed(chain.request)
    }
}
