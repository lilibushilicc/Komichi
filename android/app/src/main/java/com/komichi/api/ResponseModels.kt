package com.komichi.api

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import com.komichi.data.Bookmark
import com.komichi.data.Chapter
import com.komichi.data.Work

@Serializable
data class LoginResponse(
    val token: String,
    val user: UserResponse,
)

@Serializable
data class UserResponse(
    val id: Long,
    val username: String,
    val role: String,
)

@Serializable
data class WorkListResponse(
    val list: List<Work>,
    val total: Int,
    val page: Int,
    val size: Int,
)

@Serializable
data class BookmarkListResponse(
    val list: List<Bookmark>,
)

@Serializable
data class SignUrlResponse(
    val url: String,
    val path: String,
    val expire: Int,
    @SerialName("expire_at") val expireAt: Long,
)

@Serializable
data class CheckUpdateResponse(
    val work: Work? = null,
    @SerialName("latest_chapter") val latestChapter: Chapter? = null,
    @SerialName("has_update") val hasUpdate: Boolean = false,
    @SerialName("new_chapter_count") val newChapterCount: Int = 0,
    @SerialName("force_error") val forceError: String? = null,
)

@Serializable
data class SaveBookmarkResponse(
    @SerialName("bookmark_id") val bookmarkId: Long = 0,
)

// ---------- 源站搜索 ----------

@Serializable
data class SourceSearchItem(
    val title: String = "",
    val url: String = "",
)

@Serializable
data class SourceSearchResponse(
    val results: Map<String, List<SourceSearchItem>> = emptyMap(),
)

@Serializable
data class ImportResponse(
    @SerialName("work_id") val workId: Long = 0,
    val title: String = "",
    val source: String = "",
    @SerialName("chapter_count") val chapterCount: Int = 0,
    @SerialName("new_chapters") val newChapters: Int = 0,
)
