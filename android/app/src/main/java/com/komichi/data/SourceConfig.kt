package com.komichi.data

/**
 * 漫画源配置：定义所有已知源及其显示名称。
 *
 * 与 crawler-daemon/registry.py 中的 SOURCES 列表保持一致。
 * 新增源时需同步更新此处。
 */
object SourceConfig {

    /** 所有已知源：name → 显示名称 */
    val ALL_SOURCES: List<SourceInfo> = listOf(
        SourceInfo("kuaikan", "快看漫画"),
        SourceInfo("tencent", "腾讯动漫"),
        SourceInfo("mh160mh", "漫画160"),
        SourceInfo("guazi", "瓜子漫画"),
        SourceInfo("godamh", "GoDa漫画"),
        SourceInfo("bilibili", "哔哩哔哩漫画"),
        SourceInfo("sfacg", "SF漫画"),
        SourceInfo("dongmanmanhua", "东漫漫画"),
        SourceInfo("18comic", "禁漫天堂"),
    )

    /** 所有源名列表 */
    val ALL_NAMES: List<String> = ALL_SOURCES.map { it.name }

    /** 根据源名获取显示名称，未知源返回源名本身 */
    fun displayName(name: String): String =
        ALL_SOURCES.find { it.name == name }?.displayName ?: name
}

/** 单个源信息 */
data class SourceInfo(
    val name: String,
    val displayName: String,
)
