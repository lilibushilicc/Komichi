package com.komichi.util

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.TimeUnit

private val INPUT_FORMATS = listOf(
    "yyyy-MM-dd HH:mm:ss",
    "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",
    "yyyy-MM-dd'T'HH:mm:ss'Z'",
    "yyyy-MM-dd'T'HH:mm:ss",
    "yyyy-MM-dd HH:mm",
    "yyyy-MM-dd",
)

private val OUTPUT_DATE = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault())
private val OUTPUT_DATETIME = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault())

/** 解析多种常见时间字符串为 Date */
fun parseDate(raw: String?): Date? {
    if (raw.isNullOrBlank()) return null
    for (pattern in INPUT_FORMATS) {
        runCatching {
            return SimpleDateFormat(pattern, Locale.getDefault()).parse(raw)
        }
        // 尝试秒级时间戳
        runCatching {
            val l = raw.trim().toLong()
            return Date(if (l > 1_000_000_000_000L) l else l * 1000)
        }
    }
    return null
}

/** 格式化为日期 yyyy-MM-dd，解析失败返回原值或空 */
fun formatDate(raw: String?): String {
    val d = parseDate(raw) ?: return raw?.take(10).orEmpty()
    return OUTPUT_DATE.format(d)
}

/** 格式化为日期时间 yyyy-MM-dd HH:mm */
fun formatDateTime(raw: String?): String {
    val d = parseDate(raw) ?: return raw.orEmpty()
    return OUTPUT_DATETIME.format(d)
}

/** 相对时间：刚刚 / x分钟前 / x小时前 / x天前 / 日期 */
fun formatRelative(raw: String?): String {
    val d = parseDate(raw) ?: return raw.orEmpty()
    val diff = System.currentTimeMillis() - d.time
    return when {
        diff < 0 -> formatDate(raw)
        diff < TimeUnit.MINUTES.toMillis(1) -> "刚刚"
        diff < TimeUnit.HOURS.toMillis(1) -> "${TimeUnit.MILLISECONDS.toMinutes(diff)}分钟前"
        diff < TimeUnit.DAYS.toMillis(1) -> "${TimeUnit.MILLISECONDS.toHours(diff)}小时前"
        diff < TimeUnit.DAYS.toMillis(30) -> "${TimeUnit.MILLISECONDS.toDays(diff)}天前"
        else -> formatDate(raw)
    }
}

/** 是否为今日更新 */
fun isToday(raw: String?): Boolean {
    val d = parseDate(raw) ?: return false
    val today = OUTPUT_DATE.format(Date())
    return OUTPUT_DATE.format(d) == today
}
