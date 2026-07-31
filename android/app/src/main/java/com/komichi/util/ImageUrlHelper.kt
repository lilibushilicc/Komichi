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
    override suspend fun intercept(chain: Interceptor.Chain): ImageResult {
        val data = chain.request.data
        if (data is String && ImageUrlHelper.needsSign(data)) {
            val signed = runCatching {
                apiService.signR2Url(ImageUrlHelper.normalizePath(data)).unwrap().url
            }.getOrNull()
            if (!signed.isNullOrBlank()) {
                val newRequest = chain.request.newBuilder().data(signed).build()
                return chain.proceed(newRequest)
            }
        }
        return chain.proceed(chain.request)
    }
}
