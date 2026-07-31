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
)

@Serializable
data class SaveBookmarkResponse(
    @SerialName("bookmark_id") val bookmarkId: Long = 0,
)
