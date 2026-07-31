package com.komichi.data

import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder

/**
 * 作品状态序列化器：Worker 返回 "ongoing"/"completed"（字符串），Android 用 Int（0/1）
 */
object StatusSerializer : KSerializer<Int> {
    override val descriptor: SerialDescriptor = PrimitiveSerialDescriptor("Status", PrimitiveKind.STRING)

    override fun serialize(encoder: Encoder, value: Int) {
        encoder.encodeString(if (value == WorkStatus.COMPLETED) "completed" else "ongoing")
    }

    override fun deserialize(decoder: Decoder): Int {
        return when (decoder.decodeString()) {
            "completed" -> WorkStatus.COMPLETED
            else -> WorkStatus.ONGOING
        }
    }
}

/**
 * 作品状态：0=连载中，1=已完结
 */
object WorkStatus {
    const val ONGOING = 0
    const val COMPLETED = 1

    fun isOngoing(status: Int): Boolean = status == ONGOING
}

/**
 * 作品数据模型
 */
@Serializable
data class Work(
    @SerialName("id") val id: Long = 0L,
    @SerialName("title") val title: String = "",
    @SerialName("category") val category: String = "",
    @SerialName("cover_r2_path") val coverR2Path: String = "",
    @SerialName("source_url") val sourceUrl: String = "",
    @SerialName("latest_chapter_num") val latestChapterNum: Int = 0,
    @SerialName("status") @Serializable(with = StatusSerializer::class) val status: Int = WorkStatus.ONGOING,
    @SerialName("create_time") val createTime: String = "",
    @SerialName("update_time") val updateTime: String = "",
    @SerialName("summary") val summary: String = "",
    @SerialName("last_read_chapter") val lastReadChapter: Int = 0,
    @SerialName("is_bookmarked") val isBookmarked: Boolean = false,
)

/**
 * 章节数据模型
 */
@Serializable
data class Chapter(
    @SerialName("id") val id: Long = 0L,
    @SerialName("work_id") val workId: Long = 0L,
    @SerialName("chapter_num") val chapterNum: Int = 0,
    @SerialName("chapter_title") val chapterTitle: String = "",
    @SerialName("create_time") val createTime: String = "",
)

/**
 * 作品详情：作品信息 + 章节列表
 * Worker 返回扁平格式：{ id, title, ..., chapters: [...] }
 */
@Serializable
data class WorkDetail(
    @SerialName("id") val id: Long = 0L,
    @SerialName("title") val title: String = "",
    @SerialName("category") val category: String? = null,
    @SerialName("cover_r2_path") val coverR2Path: String? = null,
    @SerialName("source_url") val sourceUrl: String? = null,
    @SerialName("latest_chapter_num") val latestChapterNum: Int = 0,
    @SerialName("status") @Serializable(with = StatusSerializer::class) val status: Int = WorkStatus.ONGOING,
    @SerialName("create_time") val createTime: String = "",
    @SerialName("summary") val summary: String? = null,
    @SerialName("chapters") val chapters: List<Chapter> = emptyList(),
) {
    fun toWork(): Work = Work(
        id = id,
        title = title,
        category = category ?: "",
        coverR2Path = coverR2Path ?: "",
        sourceUrl = sourceUrl ?: "",
        latestChapterNum = latestChapterNum,
        status = status,
        createTime = createTime,
        updateTime = "",
        summary = summary ?: "",
    )
}

/**
 * 阅读记录 / 书签
 * Worker 返回扁平联表字段（title, cover_r2_path, status 等），不嵌套 work 对象。
 */
@Serializable
data class Bookmark(
    @SerialName("id") val id: Long = 0L,
    @SerialName("user_id") val userId: Long = 0L,
    @SerialName("work_id") val workId: Long = 0L,
    @SerialName("chapter_num") val chapterNum: Int = 0,
    @SerialName("note") val note: String = "",
    @SerialName("last_read_time") val lastReadTime: String = "",
) {
    val work: Work? get() = null
}

/**
 * 登录请求体
 */
@Serializable
data class LoginRequest(
    @SerialName("username") val username: String,
    @SerialName("password") val password: String,
)

/**
 * 保存阅读进度请求体
 */
@Serializable
data class SaveBookmarkRequest(
    @SerialName("work_id") val workId: Long,
    @SerialName("chapter_num") val chapterNum: Int,
    @SerialName("note") val note: String = "",
)
