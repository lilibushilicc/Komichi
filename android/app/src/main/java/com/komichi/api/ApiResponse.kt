package com.komichi.api

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * 统一响应包装：{ "code": 200, "msg": "success", "data": {} }
 */
@Serializable
data class ApiResponse<T>(
    @SerialName("code") val code: Int = 0,
    @SerialName("msg") val msg: String = "",
    @SerialName("data") val data: T? = null,
) {
    val isSuccess: Boolean get() = code == 200
}

/**
 * 业务异常：当 code != 200 时抛出。
 */
class ApiException(val code: Int, override val message: String) : Exception(message)

/**
 * 取出 data，若 code != 200 抛出 ApiException。
 */
fun <T> ApiResponse<T>.unwrap(): T {
    if (!isSuccess) throw ApiException(code, msg.ifBlank { "请求失败" })
    return data ?: throw ApiException(code, "数据为空")
}

/**
 * 取出可空 data，仅校验 code。
 */
fun <T> ApiResponse<T>.unwrapOrNull(): T? {
    if (!isSuccess) throw ApiException(code, msg.ifBlank { "请求失败" })
    return data
}
